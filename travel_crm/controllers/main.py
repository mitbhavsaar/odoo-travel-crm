import json

from odoo import SUPERUSER_ID, fields, http
from odoo.http import request


class TravelCrmApiController(http.Controller):
    """Lightweight inbound webhook endpoints.

    These exist to close two of the gaps found while replicating TeleCRM:

    * SIM-based call-log sync: TeleCRM's Android companion app reads the
      phone's native call log (with the user's permission) and pushes each
      call up to the CRM. Building that Android app is outside what this
      sandbox can do, but `/travel_crm/api/call_log` is the Odoo-side
      receiver such an app (or Odoo's own mobile app + a small shortcut/
      Tasker automation, as a low-cost interim option) would POST to.

    * Third-party lead-source integrations (portals, ad platforms):
      `/travel_crm/api/lead` is a generic webhook a travel portal, or a
      Meta/Google Lead Ads -> Zapier/Make/n8n bridge, can POST to instead
      of needing a bespoke connector per source.

    Both are secured with a shared-secret API key stored in
    ir.config_parameter under 'travel_crm.api_key' - set it from
    Settings > Technical > System Parameters before exposing these
    endpoints publicly, and put them behind HTTPS.
    """

    def _check_api_key(self, payload):
        expected = request.env['ir.config_parameter'].sudo().get_str('travel_crm.api_key', 'my_secret_key_123') or 'my_secret_key_123'
        provided = request.httprequest.headers.get('X-Api-Key') or payload.get('api_key')
        return bool(expected) and provided == expected

    def _json_response(self, data, status=200):
        return request.make_response(
            json.dumps(data), status=status,
            headers=[('Content-Type', 'application/json')])

    def _parse_payload(self, kwargs=None):
        if hasattr(request, '_cached_payload'):
            payload = dict(request._cached_payload)
            if kwargs:
                payload.update(kwargs)
            return payload

        payload = {}
        if kwargs:
            payload.update(kwargs)
        if hasattr(request, 'httprequest'):
            try:
                raw_data = request.httprequest.get_data()
                if raw_data:
                    parsed = json.loads(raw_data.decode('utf-8'))
                    if isinstance(parsed, dict):
                        payload.update(parsed)
            except Exception:
                pass
        request._cached_payload = payload
        return payload

    @http.route('/travel_crm/api/call_log', type='http', auth='none', csrf=False, methods=['POST'])
    def create_call_log(self, **kwargs):
        payload = self._parse_payload(kwargs)
        if not self._check_api_key(payload):
            return self._json_response({'success': False, 'error': 'invalid or missing api_key'}, status=401)

        # auth='none' routes have no request user, so message_post/mail-thread
        # logic (which needs a real res.users record) would crash under an
        # empty/public user. update_env() (rather than a bare
        # request.env(user=..., su=True)) also repoints the transaction's
        # default_env, which some ORM internals read directly.
        request.update_env(user=SUPERUSER_ID, su=True)
        env = request.env
        lead = env['crm.lead']
        lead_phone = payload.get('lead_phone')
        if lead_phone:
            lead = env['crm.lead'].search([
                '|', ('phone', '=', lead_phone), ('mobile', '=', lead_phone),
            ], limit=1)
            if not lead:
                travel_team = env.ref('travel_crm.crm_team_travel_desk', raise_if_not_found=False)
                lead = env['crm.lead'].create({
                    'name': payload.get('lead_name') or 'Inbound call: %s' % lead_phone,
                    'phone': lead_phone,
                    'team_id': travel_team.id if travel_team else False,
                    'type': 'opportunity',
                })

        agent = env['res.users']
        if payload.get('agent_email'):
            agent = env['res.users'].search([('login', '=', payload['agent_email'])], limit=1)

        vals = {
            'lead_id': lead.id if lead else False,
            'agent_id': agent.id if agent else env.uid,
            'caller_number': payload.get('caller_number') or lead_phone or 'unknown',
            'call_type': payload.get('call_type', 'outgoing'),
            'call_datetime': payload.get('call_datetime') or fields.Datetime.now(),
            'duration_seconds': payload.get('duration_seconds', 0),
            'sim_line': payload.get('sim_line', 'sim1'),
            'campaign_name': payload.get('campaign_name'),
            'note': payload.get('note'),
            'recording_url': payload.get('recording_url'),
        }
        call_log = env['travel.call.log'].create(vals)
        return self._json_response({'success': True, 'id': call_log.id, 'lead_id': lead.id if lead else False})

    @http.route('/travel_crm/api/lead', type='http', auth='none', csrf=False, methods=['POST'])
    def create_lead(self, **kwargs):
        payload = self._parse_payload(kwargs)
        if not self._check_api_key(payload):
            return self._json_response({'success': False, 'error': 'invalid or missing api_key'}, status=401)

        # See create_call_log() above for why update_env() (not a bare
        # request.env(user=..., su=True)) is required here.
        request.update_env(user=SUPERUSER_ID, su=True)
        env = request.env
        travel_team = env.ref('travel_crm.crm_team_travel_desk', raise_if_not_found=False)
        inquiry_stage = env.ref('travel_crm.stage_travel_inquiry', raise_if_not_found=False)
        source_name = payload.get('source') or 'Website Enquiry'
        source = False
        if source_name:
            source = env['utm.source'].search([('name', '=', source_name)], limit=1) \
                or env['utm.source'].create({'name': source_name})

        loc_vals = env['crm.lead']._detect_location_from_payload(payload)

        dest_name = payload.get('destination') or payload.get('package_name')
        destination_rec = False
        if dest_name:
            destination_rec = env['travel.destination'].search([('name', 'ilike', str(dest_name).strip())], limit=1) \
                or env['travel.destination'].create({'name': str(dest_name).strip()})

        lead_vals = {
            'name': payload.get('name') or (f"Website Inquiry - {dest_name}" if dest_name else "Web Enquiry"),
            'contact_name': payload.get('contact_name') or payload.get('full_name'),
            'phone': payload.get('phone') or payload.get('mobile'),
            'email_from': payload.get('email') or payload.get('email_address'),
            'description': payload.get('description') or payload.get('message'),
            'team_id': travel_team.id if travel_team else False,
            'stage_id': inquiry_stage.id if inquiry_stage else False,
            'x_destination_id': destination_rec.id if destination_rec else False,
            'x_is_travel_lead': True,
            'type': 'opportunity',
            'source_id': source.id if source else False,
        }
        if payload.get('adults') or payload.get('pax_adults'):
            try:
                lead_vals['x_pax_adults'] = int(payload.get('adults') or payload.get('pax_adults'))
            except (ValueError, TypeError):
                pass
        if payload.get('children') or payload.get('pax_children'):
            try:
                lead_vals['x_pax_children'] = int(payload.get('children') or payload.get('pax_children'))
            except (ValueError, TypeError):
                pass
        if payload.get('price') or payload.get('calculated_price') or payload.get('expected_revenue'):
            try:
                raw_price = str(payload.get('price') or payload.get('calculated_price') or payload.get('expected_revenue')).replace('$', '').replace(',', '').strip()
                lead_vals['expected_revenue'] = float(raw_price)
            except (ValueError, TypeError):
                pass
        if payload.get('travel_date_from') or payload.get('departure_date'):
            lead_vals['x_travel_date_from'] = payload.get('travel_date_from') or payload.get('departure_date')
        if payload.get('travel_date_to'):
            lead_vals['x_travel_date_to'] = payload.get('travel_date_to')

        lead_vals.update(loc_vals)

        lead = env['crm.lead'].create(lead_vals)
        return self._json_response({
            'success': True,
            'id': lead.id,
            'team_id': lead.team_id.id if lead.team_id else False,
            'team_name': lead.team_id.name if lead.team_id else False,
            'assigned_user_id': lead.user_id.id if lead.user_id else False,
            'assigned_user_name': lead.user_id.name if lead.user_id else False,
            'state_id': lead.state_id.id if lead.state_id else False,
            'state_name': lead.state_id.name if lead.state_id else False,
        })

    @http.route('/travel_crm/api/meta/leadgen', type='http', auth='none', csrf=False, methods=['GET', 'POST'])
    def meta_leadgen_webhook(self, **kwargs):
        """Meta (Facebook / Instagram Lead Ads) Graph API Real-Time Webhook."""
        request.update_env(user=SUPERUSER_ID, su=True)
        env = request.env

        # 1. Meta Webhook Verification Handshake (GET)
        if request.httprequest.method == 'GET':
            mode = kwargs.get('hub.mode')
            token = kwargs.get('hub.verify_token')
            challenge = kwargs.get('hub.challenge')
            expected_token = env['ir.config_parameter'].sudo().get_str('travel_crm.meta_verify_token', 'meta_verify_token_travel_crm')
            if mode == 'subscribe' and token == expected_token:
                return request.make_response(challenge or '', headers=[('Content-Type', 'text/plain')])
            return self._json_response({'error': 'Verification failed'}, status=403)

        # 2. Meta Lead Payload Ingestion (POST)
        payload = self._parse_payload()
        entry = payload.get('entry', [])
        created_leads = []

        source = env['utm.source'].search([('name', '=', 'Facebook Lead Ads')], limit=1) \
            or env['utm.source'].create({'name': 'Facebook Lead Ads'})

        for item in entry:
            changes = item.get('changes', [])
            for change in changes:
                field = change.get('field')
                value = change.get('value', {})
                if field == 'leadgen':
                    field_data = value.get('field_data', [])
                    form_data = {}
                    for f in field_data:
                        fname = f.get('name')
                        fval = f.get('values', [''])[0]
                        form_data[fname] = fval

                    name = form_data.get('full_name') or form_data.get('first_name') or 'Meta Lead ' + str(value.get('leadgen_id', ''))
                    phone = form_data.get('phone_number') or form_data.get('phone')
                    email = form_data.get('email')
                    city = form_data.get('city')
                    state = form_data.get('state')

                    loc_vals = env['crm.lead']._detect_location_from_payload({'city': city, 'state': state})
                    lead_vals = {
                        'name': name,
                        'contact_name': name,
                        'phone': phone,
                        'email_from': email,
                        'type': 'opportunity',
                        'source_id': source.id,
                        'description': "Meta Lead Ads (Form ID: %s, Leadgen ID: %s)" % (value.get('form_id'), value.get('leadgen_id')),
                    }
                    lead_vals.update(loc_vals)
                    lead = env['crm.lead'].create(lead_vals)
                    created_leads.append(lead.id)

        return self._json_response({'success': True, 'created_lead_ids': created_leads})

    @http.route('/travel_crm/api/indiamart', type='http', auth='none', csrf=False, methods=['POST'])
    def indiamart_webhook(self, **kwargs):
        """IndiaMART Push API & JSON Payload Webhook Endpoint."""
        payload = self._parse_payload()
        if not payload and request.httprequest.data:
            body_text = request.httprequest.data.decode('utf-8', errors='ignore')
            payload = request.env['crm.lead']._parse_email_lead_body(body_text, default_source="IndiaMART")

        request.update_env(user=SUPERUSER_ID, su=True)
        env = request.env

        source = env['utm.source'].search([('name', '=', 'IndiaMART')], limit=1) \
            or env['utm.source'].create({'name': 'IndiaMART'})

        contact_name = payload.get('SENDER_NAME') or payload.get('contact_name') or 'IndiaMART Lead'
        phone = payload.get('SENDER_MOBILE') or payload.get('phone') or payload.get('mobile')
        email = payload.get('SENDER_EMAIL') or payload.get('email_from') or payload.get('email')
        city = payload.get('QUERY_CITY') or payload.get('city')
        state = payload.get('QUERY_STATE') or payload.get('state')
        query = payload.get('QUERY_MESSAGE') or payload.get('description') or payload.get('QUERY_PRODUCT_NAME')

        loc_vals = env['crm.lead']._detect_location_from_payload({'city': city, 'state': state})
        lead_vals = {
            'name': 'IndiaMART: ' + (payload.get('QUERY_PRODUCT_NAME') or contact_name),
            'contact_name': contact_name,
            'phone': phone,
            'email_from': email,
            'description': query,
            'type': 'opportunity',
            'source_id': source.id,
        }
        lead_vals.update(loc_vals)

        lead = env['crm.lead'].create(lead_vals)
        return self._json_response({'success': True, 'id': lead.id, 'source': 'IndiaMART', 'assigned_to': lead.user_id.name if lead.user_id else False})

    @http.route('/travel_crm/api/justdial', type='http', auth='none', csrf=False, methods=['POST'])
    def justdial_webhook(self, **kwargs):
        """JustDial Push API & Webhook Endpoint."""
        payload = self._parse_payload()
        if not payload and request.httprequest.data:
            body_text = request.httprequest.data.decode('utf-8', errors='ignore')
            payload = request.env['crm.lead']._parse_email_lead_body(body_text, default_source="JustDial")

        request.update_env(user=SUPERUSER_ID, su=True)
        env = request.env

        source = env['utm.source'].search([('name', '=', 'JustDial')], limit=1) \
            or env['utm.source'].create({'name': 'JustDial'})

        contact_name = payload.get('name') or payload.get('contact_name') or 'JustDial Lead'
        phone = payload.get('mobile') or payload.get('phone')
        email = payload.get('email') or payload.get('email_from')
        city = payload.get('city')
        state = payload.get('state')
        category = payload.get('category') or payload.get('description') or 'Travel Inquiry'

        loc_vals = env['crm.lead']._detect_location_from_payload({'city': city, 'state': state})
        lead_vals = {
            'name': 'JustDial: ' + category,
            'contact_name': contact_name,
            'phone': phone,
            'email_from': email,
            'description': payload.get('description') or category,
            'type': 'opportunity',
            'source_id': source.id,
        }
        lead_vals.update(loc_vals)

        lead = env['crm.lead'].create(lead_vals)
        return self._json_response({'success': True, 'id': lead.id, 'source': 'JustDial', 'assigned_to': lead.user_id.name if lead.user_id else False})
