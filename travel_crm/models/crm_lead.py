from odoo import api, fields, models


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    # -- Vertical scoping --------------------------------------------
    x_is_travel_lead = fields.Boolean(
        compute='_compute_is_travel_lead', store=True, string='Is Travel Lead',
        help="True when this lead belongs to the Travel Desk team. Used to keep "
             "travel-specific fields/tabs from showing up on non-travel leads "
             "(e.g. a furniture or generic sales opportunity) elsewhere in CRM.")

    # -- Travel details -----------------------------------------------
    x_destination_id = fields.Many2one('travel.destination', string='Destination')
    x_package_id = fields.Many2one('travel.package', string='Travel Package', tracking=True)
    x_travel_date_from = fields.Date(string='Travel Start Date')
    x_travel_date_to = fields.Date(string='Travel End Date')

    @api.onchange('x_package_id')
    def _onchange_x_package_id(self):
        if self.x_package_id:
            self.expected_revenue = self.x_package_id.price
            if self.x_package_id.destination_id:
                self.x_destination_id = self.x_package_id.destination_id
            if self.x_package_id.package_type:
                self.x_package_type = self.x_package_id.package_type


    x_package_type = fields.Selection([
        ('fit', 'FIT (Individual / Family)'),
        ('group', 'Group Tour'),
        ('customized', 'Customized / Bespoke'),
        ('corporate', 'Corporate / MICE'),
        ('honeymoon', 'Honeymoon'),
        ('pilgrimage', 'Pilgrimage'),
        ('budget', 'Budget / Economy'),
        ('standard', 'Standard 3-Star'),
        ('deluxe', 'Deluxe 4-Star'),
        ('luxury', 'Luxury 5-Star / Resort'),
        ('custom', 'Custom Tailor-Made'),
    ], string='Package Type', tracking=True)

    x_pax_adults = fields.Integer('Adults', default=1)
    x_pax_children = fields.Integer('Children', default=0)
    x_pax_infants = fields.Integer('Infants', default=0)
    x_total_pax = fields.Integer(compute='_compute_total_pax', store=True, string='Total Pax')

    # -- Documentation --------------------------------------------------
    x_visa_required = fields.Boolean('Visa Required')
    x_visa_status = fields.Selection([
        ('na', 'Not Required'),
        ('pending', 'Pending Submission'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='na', string='Visa Status', tracking=True)
    x_kyc_status = fields.Selection([
        ('pending', 'Pending'),
        ('submitted', 'Submitted'),
        ('verified', 'Verified'),
    ], default='pending', string='KYC / Travel Docs Status', tracking=True)
    x_travel_insurance = fields.Boolean('Travel Insurance Opted')
    x_flight_included = fields.Boolean('Flight Included', default=True)

    # -- Sales process tracking -----------------------------------------
    x_itinerary_sent = fields.Boolean('Itinerary Shared', tracking=True)
    x_itinerary_sent_date = fields.Datetime('Itinerary Shared On')
    x_booking_reference = fields.Char('Booking Reference')
    x_call_disposition = fields.Selection([
        ('fresh', 'Fresh Lead'),
        ('rnr', 'Ring No Response'),
        ('interested', 'Interested / Relevant'),
        ('call_back', 'Call Back Later'),
        ('not_interested', 'Not Interested'),
        ('converted', 'Converted'),
    ], default='fresh', string='Call Disposition', tracking=True)

    x_is_qualified = fields.Boolean(compute='_compute_x_is_qualified', string='Is Qualified')

    @api.depends('stage_id', 'stage_id.name', 'stage_id.sequence', 'x_call_disposition')
    def _compute_x_is_qualified(self):
        for lead in self:
            stage_name = (lead.stage_id.name or '').lower()
            lead.x_is_qualified = bool(
                'qualified' in stage_name or
                'itinerary' in stage_name or
                'negotiation' in stage_name or
                'booking' in stage_name or
                'documentation' in stage_name or
                'trip' in stage_name or
                (lead.stage_id and lead.stage_id.is_won) or
                (lead.stage_id and lead.stage_id.sequence > 1)
            )



    # -- Payments & Invoicing ---------------------------------------------
    x_installment_ids = fields.One2many(
        'travel.payment.installment', 'lead_id', string='Payment Installments')
    x_invoice_ids = fields.One2many(
        'account.move', 'x_lead_id', string='Invoices')
    x_invoice_count = fields.Integer(
        compute='_compute_invoice_count', string='Invoice Count')
    x_amount_received = fields.Monetary(
        compute='_compute_payment_amounts', store=True,
        string='Amount Received', currency_field='company_currency')
    x_amount_pending = fields.Monetary(
        compute='_compute_payment_amounts', store=True,
        string='Amount Pending', currency_field='company_currency')

    @api.depends('x_invoice_ids')
    def _compute_invoice_count(self):
        for lead in self:
            lead.x_invoice_count = len(lead.x_invoice_ids)


    # -- AI lead summary (stub, mirrors TeleCRM's "Lead-IQ") -------------
    x_ai_lead_summary = fields.Text('AI Lead Summary')
    x_ai_next_step = fields.Text('AI Suggested Next Step')
    x_ai_generated_on = fields.Datetime('Summary Generated On', readonly=True)

    # -- Calls & AI coaching ----------------------------------------------
    x_call_log_ids = fields.One2many('travel.call.log', 'lead_id', string='Call Logs')
    x_call_count = fields.Integer(compute='_compute_call_count', string='Call Count')
    x_last_call_ai_score = fields.Integer(
        compute='_compute_call_count', string='Last Call AI Score')

    # -- Security & Phone Masking for Non-Admin / Sales Users -----------
    mobile = fields.Char(string='Mobile')
    x_phone_masked = fields.Char(compute='_compute_masked_phone_fields', string='Phone (Display)')
    x_mobile_masked = fields.Char(compute='_compute_masked_phone_fields', string='Mobile (Display)')

    @api.depends('phone', 'mobile')
    def _compute_masked_phone_fields(self):
        is_manager = (
            self.env.user.has_group('sales_team.group_sale_manager') or
            self.env.user.has_group('base.group_erp_manager') or
            self.env.user.has_group('base.group_system') or
            self.env.is_superuser()
        )
        for lead in self:
            if is_manager:
                lead.x_phone_masked = lead.phone or ''
                lead.x_mobile_masked = lead.mobile or ''
            else:
                lead.x_phone_masked = self._mask_number(lead.phone)
                lead.x_mobile_masked = self._mask_number(lead.mobile)

    @api.model
    def _mask_number(self, num_str):
        if not num_str:
            return ''
        clean = str(num_str).strip()
        if len(clean) <= 6:
            return clean
        prefix = clean[:5]
        suffix = clean[-2:]
        masked_len = max(len(clean) - 7, 4)
        return f"{prefix}{'X' * masked_len}{suffix}"

    # -- WhatsApp quick-chat (lightweight fallback; see AI Lead Summary tab
    #    for the note on Odoo Enterprise's native WhatsApp app) ------------
    x_whatsapp_link = fields.Char(compute='_compute_whatsapp_link', string='WhatsApp Link')

    @api.depends('x_call_log_ids', 'x_call_log_ids.ai_overall_score', 'phone', 'mobile')
    def _compute_call_count(self):
        for lead in self:
            lead._sync_voip_calls_for_lead()
            lead.x_call_count = len(lead.x_call_log_ids)
            last = lead.x_call_log_ids.sorted('call_datetime', reverse=True)[:1]
            lead.x_last_call_ai_score = last.ai_overall_score if last else 0

    def _sync_voip_calls_for_lead(self):
        self.ensure_one()
        phone_raw = self.phone or self.mobile or ''
        phone_digits = ''.join(c for c in phone_raw if c.isdigit())
        domain = []
        if phone_digits and len(phone_digits) >= 7:
            domain = [('phone_number', 'like', phone_digits[-10:])]
        if self.partner_id:
            domain = ['|', ('partner_id', '=', self.partner_id.id)] + domain if domain else [('partner_id', '=', self.partner_id.id)]
        if not domain:
            domain = [('activity_res_model', '=', 'crm.lead'), ('activity_res_id', '=', self.id)]
        else:
            domain = ['|', '&', ('activity_res_model', '=', 'crm.lead'), ('activity_res_id', '=', self.id)] + domain

        voip_calls = self.env['voip.call'].sudo().search(domain)
        if voip_calls:
            voip_calls._sync_to_travel_call_logs()

    @api.depends('phone', 'mobile')
    def _compute_whatsapp_link(self):
        for lead in self:
            raw = lead.mobile or lead.phone or ''
            digits = ''.join(ch for ch in raw if ch.isdigit())
            lead.x_whatsapp_link = 'https://web.whatsapp.com/send?phone=%s' % digits if digits else False

    def action_view_call_logs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Call Logs',
            'res_model': 'travel.call.log',
            'view_mode': 'list,form',
            'domain': [('lead_id', '=', self.id)],
            'context': {'default_lead_id': self.id},
        }

    def action_open_whatsapp(self):
        self.ensure_one()
        if not self.x_whatsapp_link:
            return
        phone_num = self.mobile or self.phone or 'Unknown'
        self.message_post(
            body=f"<p style='color: #25d366; font-weight: bold;'>💬 WhatsApp Chat Opened</p><p>Initiated conversation with <b>{phone_num}</b> via WhatsApp Web.</p>",
            message_type='comment',
            subtype_xmlid='mail.mt_note'
        )
        return {
            'type': 'ir.actions.act_url',
            'url': self.x_whatsapp_link,
            'target': 'new',
        }

    @api.depends('team_id')
    def _compute_is_travel_lead(self):
        travel_team = self.env.ref('travel_crm.crm_team_travel_desk', raise_if_not_found=False)
        for lead in self:
            lead.x_is_travel_lead = bool(travel_team) and lead.team_id.id == travel_team.id

    @api.depends('x_pax_adults', 'x_pax_children', 'x_pax_infants')
    def _compute_total_pax(self):
        for lead in self:
            lead.x_total_pax = (lead.x_pax_adults or 0) + (lead.x_pax_children or 0) + (lead.x_pax_infants or 0)

    @api.depends('x_installment_ids.amount', 'x_installment_ids.state', 'expected_revenue',
                 'x_invoice_ids', 'x_invoice_ids.payment_state', 'x_invoice_ids.amount_total', 'x_invoice_ids.amount_residual')
    def _compute_payment_amounts(self):
        for lead in self:
            if lead.x_invoice_ids:
                total_inv = sum(lead.x_invoice_ids.mapped('amount_total'))
                residual_inv = sum(lead.x_invoice_ids.mapped('amount_residual'))
                received = total_inv - residual_inv
                lead.x_amount_received = received
                lead.x_amount_pending = max(residual_inv, 0)
            else:
                received = sum(lead.x_installment_ids.filtered(lambda i: i.state == 'paid').mapped('amount'))
                lead.x_amount_received = received
                lead.x_amount_pending = max((lead.expected_revenue or 0) - received, 0)

    def action_create_invoice(self):
        self.ensure_one()
        return {
            'name': 'Create invoice(s)',
            'type': 'ir.actions.act_window',
            'res_model': 'travel.lead.invoice.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_lead_id': self.id,
                'default_amount': self.expected_revenue or (self.x_package_id.price if self.x_package_id else 0.0),
            }
        }


    def action_view_invoices(self):
        self.ensure_one()
        invoices = self.x_invoice_ids
        if len(invoices) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Customer Invoice',
                'res_model': 'account.move',
                'res_id': invoices.id,
                'view_mode': 'form',
            }
        return {
            'type': 'ir.actions.act_window',
            'name': 'Invoices',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', invoices.ids)],
        }

    def action_mark_itinerary_sent(self):
        itinerary_stage = self.env['crm.stage'].search([
            '|', ('name', '=ilike', '%itinerary%'), ('name', '=ilike', '%shared%')
        ], limit=1)
        vals = {
            'x_itinerary_sent': True,
            'x_itinerary_sent_date': fields.Datetime.now()
        }
        if itinerary_stage:
            vals['stage_id'] = itinerary_stage.id
        self.write(vals)

    def action_generate_ai_summary(self):
        """Generates real AI Lead Summary & Suggested Next Step using Google Gemini / NVIDIA AI API."""
        import json
        import logging
        import requests
        from odoo.exceptions import UserError

        _logger = logging.getLogger(__name__)

        gemini_key = (self.env['ir.config_parameter'].sudo().get_str('travel_crm.gemini_api_key') or '').strip()
        nvidia_key = (self.env['ir.config_parameter'].sudo().get_str('travel_crm.nvidia_api_key') or '').strip()

        if not gemini_key and not nvidia_key:
            raise UserError(
                "No AI API key found in System Parameters!\n\n"
                "Please configure 'travel_crm.gemini_api_key' or 'travel_crm.nvidia_api_key' "
                "under Configuration -> Settings or System Parameters to enable real AI generation."
            )


        for lead in self:
            cust_name = False
            if lead.partner_id and lead.partner_id.name:
                cust_name = lead.partner_id.name
            elif lead.contact_name and '@' not in lead.contact_name:
                cust_name = lead.contact_name
            elif lead.partner_name and '@' not in lead.partner_name:
                cust_name = lead.partner_name

            display_cust_name = cust_name if cust_name else "Not provided"

            destination = lead.x_destination_id.name if lead.x_destination_id else 'Not specified'
            pkg_type = dict(lead._fields['x_package_type'].selection).get(lead.x_package_type, 'General Tour') if lead.x_package_type else 'General Tour'
            pax = "%d Adults, %d Children, %d Infants (Total: %d)" % (lead.x_pax_adults or 0, lead.x_pax_children or 0, lead.x_pax_infants or 0, lead.x_total_pax or 0)
            dates = "%s to %s" % (lead.x_travel_date_from or 'TBD', lead.x_travel_date_to or 'TBD')
            disposition = dict(lead._fields['x_call_disposition'].selection).get(lead.x_call_disposition, 'Fresh') if lead.x_call_disposition else 'Fresh'
            budget = "₹%s" % (lead.expected_revenue) if lead.expected_revenue else 'Not specified'

            call_notes = []
            for call in lead.x_call_log_ids.sorted('call_datetime', reverse=True)[:5]:
                call_notes.append("Call (%s, %ds, %s): %s" % (
                    call.call_type, call.duration_seconds or 0, call.call_disposition or 'Fresh', call.note or 'No notes'
                ))
            call_history_str = "\n".join(call_notes) if call_notes else "No calls logged yet."

            chatter_notes = []
            for msg in lead.message_ids.filtered(lambda m: m.message_type in ('comment', 'email', 'sms'))[:5]:
                if msg.body:
                    clean_body = msg.body.replace('<p>', '').replace('</p>', '').replace('<br/>', '\n').strip()
                    if clean_body:
                        chatter_notes.append("- %s: %s" % (msg.author_id.name if msg.author_id else 'System', clean_body))
            chatter_str = "\n".join(chatter_notes) if chatter_notes else "No chatter notes logged."

            prompt = f"""You are an expert AI CRM Sales Analyst for a Travel Agency.
Analyze the following travel lead details, call logs, and client communications:

Customer Name: {display_cust_name}
Phone: {lead.phone or lead.mobile or 'N/A'}
Email: {lead.email_from or 'N/A'}
Destination: {destination}
Package Type: {pkg_type}
Pax Details: {pax}
Travel Dates: {dates}
Expected Revenue / Budget: {budget}
Call Disposition Status: {disposition}
Lead Description / Inquiry Notes: {lead.description or 'No initial description provided.'}

Call Log History:
{call_history_str}

Chatter & Communication Notes:
{chatter_str}

CRITICAL INSTRUCTION: If Customer Name is 'Not provided' or N/A, DO NOT attempt to guess, extract, or infer a person's name from their email address or lead title. Simply refer to them as 'the client' or 'the customer'.

Respond STRICTLY in valid JSON format with two keys:
1. "summary": A fluent, well-crafted single continuous paragraph (3-4 smooth sentences) summarizing the client's travel request, trip scope, budget, pax count, call disposition status, and interaction history into a cohesive executive narrative. Do NOT use bullet points, line breaks, or robotic key-value fragments.
2. "next_step": A single, clear, actionable next step sentence recommendation for the travel consultant.
"""

            success = False
            if gemini_key:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={gemini_key.strip()}"
                    payload = {
                        'contents': [{'parts': [{'text': prompt}]}],
                        'generationConfig': {'response_mime_type': 'application/json'}
                    }
                    resp = requests.post(url, json=payload, timeout=12)
                    if resp.status_code == 200:
                        res_json = resp.json()
                        text_resp = res_json['candidates'][0]['content']['parts'][0]['text']
                        ai_data = json.loads(text_resp)
                        lead.x_ai_lead_summary = ai_data.get('summary', '')
                        lead.x_ai_next_step = ai_data.get('next_step', '')
                        lead.x_ai_generated_on = fields.Datetime.now()
                        success = True
                except Exception as e:
                    _logger.warning("Gemini AI API call failed: %s", str(e))

            if not success and nvidia_key:
                try:
                    url = "https://integrate.api.nvidia.com/v1/chat/completions"
                    headers = {
                        "Authorization": f"Bearer {nvidia_key.strip()}",
                        "Content-Type": "application/json"
                    }
                    payload = {
                        "model": "nvidia/llama-3.1-nemotron-70b-instruct",
                        "messages": [
                            {"role": "system", "content": "You are a travel CRM assistant. Output strictly valid JSON with keys 'summary' and 'next_step'."},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.2
                    }
                    resp = requests.post(url, headers=headers, json=payload, timeout=15)
                    if resp.status_code == 200:
                        text_resp = resp.json()['choices'][0]['message']['content']
                        ai_data = json.loads(text_resp)
                        lead.x_ai_lead_summary = ai_data.get('summary', '')
                        lead.x_ai_next_step = ai_data.get('next_step', '')
                        lead.x_ai_generated_on = fields.Datetime.now()
                        success = True
                except Exception as e:
                    _logger.warning("NVIDIA AI API call failed: %s", str(e))

            if not success:
                note_count = len(lead.message_ids)
                lead_name_str = cust_name if cust_name else "The client"
                dates_info = f" scheduled between {lead.x_travel_date_from} and {lead.x_travel_date_to}" if lead.x_travel_date_from and lead.x_travel_date_to else ""
                revenue_info = f" with an expected revenue budget of ${lead.expected_revenue:,.2f}" if lead.expected_revenue else ""

                lead.x_ai_lead_summary = (
                    f"{lead_name_str} has submitted an inquiry for a {pkg_type.lower()} package to {destination} for {lead.x_total_pax or 1} traveller(s){dates_info}{revenue_info}. "
                    f"The lead currently carries a call disposition status of '{disposition}', with a total of {note_count} communication interaction(s) logged across phone calls and chatter history. "
                    f"All primary travel preferences and contact details are registered, requiring proactive follow-up to finalize itinerary details and booking quotes."
                )
                lead.x_ai_next_step = (
                    f"Initiate a direct follow-up with {cust_name if cust_name else 'the client'} via WhatsApp or Phone to review the {destination} itinerary options and confirm booking details."
                )
                lead.x_ai_generated_on = fields.Datetime.now()

    def action_start_voip_call(self):
        self.ensure_one()
        phone_num = self.phone or self.mobile or ''
        contact = (
            self.partner_id.name if self.partner_id else
            (self.contact_name if self.contact_name and '@' not in self.contact_name else
             (self.partner_name if self.partner_name and '@' not in self.partner_name else 'Customer'))
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'travel_crm_open_voip',
            'params': {
                'lead_id': self.id,
                'name': contact,
                'phone': phone_num,
            }
        }

    def action_open_qualification_wizard(self):
        self.ensure_one()
        return {
            'name': 'Qualify Travel Lead',
            'type': 'ir.actions.act_window',
            'res_model': 'travel.lead.qualification.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_lead_id': self.id,
            }
        }

    @api.model
    def _detect_location_from_payload(self, payload):
        """Auto-detect City, State, and Country from incoming JSON payload dict."""
        vals = {}
        city = payload.get('city') or payload.get('QUERY_CITY') or payload.get('city_name')
        state_input = (payload.get('state') or payload.get('state_name') or payload.get('state_code')
                       or payload.get('QUERY_STATE'))
        country_input = payload.get('country') or payload.get('country_name') or payload.get('country_code')

        if city:
            vals['city'] = str(city).strip()

        state_rec = False
        if state_input:
            state_str = str(state_input).strip()
            state_rec = self.env['res.country.state'].search([
                '|', '|', ('name', '=ilike', state_str), ('code', '=ilike', state_str), ('name', 'ilike', state_str)
            ], limit=1)

        country_rec = False
        if country_input:
            country_str = str(country_input).strip()
            country_rec = self.env['res.country'].search([
                '|', ('name', '=ilike', country_str), ('code', '=ilike', country_str)
            ], limit=1)

        if not country_rec and state_rec and state_rec.country_id:
            country_rec = state_rec.country_id

        if state_rec:
            vals['state_id'] = state_rec.id
        if country_rec:
            vals['country_id'] = country_rec.id

        return vals

    @api.model
    def _parse_email_lead_body(self, body_text, default_source="Email Inquiry"):
        """Extract Name, Phone, Email, City, State, and Query from raw email text (JustDial/IndiaMART)."""
        import re
        data = {}
        if not body_text:
            return data

        lines = body_text.splitlines()
        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
            
            # Name extraction
            m_name = re.search(r'(?:Name|Buyer Name|Sender Name|Contact Name)\s*[:=-]\s*(.+)', line_str, re.I)
            if m_name and 'contact_name' not in data:
                data['contact_name'] = m_name.group(1).strip()
            
            # Phone extraction
            m_phone = re.search(r'(?:Mobile|Phone|Contact|Mobile No|Sender Mobile)\s*[:=-]\s*([+\d\s-]+)', line_str, re.I)
            if m_phone and 'phone' not in data:
                data['phone'] = m_phone.group(1).strip()
                
            # Email extraction
            m_email = re.search(r'(?:Email|Sender Email|Email ID)\s*[:=-]\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', line_str, re.I)
            if m_email and 'email_from' not in data:
                data['email_from'] = m_email.group(1).strip()

            # City extraction
            m_city = re.search(r'(?:City|Buyer City|Location)\s*[:=-]\s*(.+)', line_str, re.I)
            if m_city and 'city' not in data:
                data['city'] = m_city.group(1).strip()

            # State extraction
            m_state = re.search(r'(?:State|Buyer State|Region)\s*[:=-]\s*(.+)', line_str, re.I)
            if m_state and 'state' not in data:
                data['state'] = m_state.group(1).strip()

        data['description'] = body_text
        return data

    def _auto_distribute_lead(self):
        """Intelligent Regional Routing & Workload-Capacity Balanced Round-Robin Assignment."""
        for lead in self:
            state_name = lead.state_id.name if lead.state_id else ''
            city_name = lead.city or ''
            
            target_team = False
            search_terms = [t for t in [state_name, city_name] if t]
            for term in search_terms:
                team = self.env['crm.team'].search([('name', 'ilike', term)], limit=1)
                if team:
                    target_team = team
                    break

            if not target_team:
                target_team = self.env.ref('travel_crm.crm_team_travel_desk', raise_if_not_found=False)

            if target_team and lead.team_id != target_team:
                lead.team_id = target_team

            # If user_id is missing or defaulted to system bot/root, reassign to real human sales agent
            if (not lead.user_id or lead.user_id.id in (1, self.env.ref('base.user_root').id)) and target_team:
                eligible_users = target_team.member_ids.filtered(
                    lambda u: not u.share and u.id != 1 and u.id != self.env.ref('base.user_root').id
                )
                if not eligible_users:
                    eligible_users = self.env['res.users'].search([
                        ('share', '=', False),
                        ('active', '=', True),
                        ('id', '!=', 1),
                        ('id', '!=', self.env.ref('base.user_root').id),
                    ])

                if eligible_users:
                    user_workloads = []
                    for user in eligible_users:
                        open_count = self.search_count([
                            ('user_id', '=', user.id),
                            ('probability', '<', 100),
                            ('active', '=', True)
                        ])
                        user_workloads.append((open_count, user.id))
                    
                    user_workloads.sort(key=lambda x: x[0])
                    best_user_id = user_workloads[0][1]
                    lead.user_id = best_user_id

    def _check_auto_booking_reference(self):
        """Auto-generates a unique Booking Reference (e.g. BK-2026-0060)
        when a lead reaches 'Booking Confirmed', 'Trip Confirmed (Won)', or any confirmed/won stage."""
        import random
        from datetime import date
        year = date.today().year

        for lead in self:
            if not lead.x_booking_reference:
                stage_name = (lead.stage_id.name or '').lower() if lead.stage_id else ''
                is_confirmed_stage = bool(
                    'booking' in stage_name or
                    'confirmed' in stage_name or
                    'won' in stage_name or
                    'trip' in stage_name or
                    'documentation' in stage_name or
                    (lead.stage_id and lead.stage_id.is_won)
                )
                if is_confirmed_stage:
                    ref_code = f"BK-{year}-{lead.id:04d}" if lead.id else f"YTT-{random.randint(100000, 999999)}"
                    lead.write({'x_booking_reference': ref_code})
                    lead.message_post(
                        body=f"<p style='color: #7141C8; font-weight: bold;'>🎫 Automatic Booking Reference Generated</p>"
                             f"<p>Booking Reference <b>{ref_code}</b> automatically generated upon moving to stage <i>{lead.stage_id.name}</i>.</p>",
                        message_type='comment',
                        subtype_xmlid='mail.mt_note'
                    )

    @api.model_create_multi
    def create(self, vals_list):
        leads = super().create(vals_list)
        for lead in leads:
            if not lead.user_id or lead.user_id.id in (1, self.env.ref('base.user_root').id):
                lead._auto_distribute_lead()
        leads._check_auto_booking_reference()
        return leads

    def write(self, vals):
        if 'x_package_id' in vals and vals['x_package_id'] and 'expected_revenue' not in vals:
            pkg = self.env['travel.package'].browse(vals['x_package_id'])
            if pkg:
                vals['expected_revenue'] = pkg.price
        res = super().write(vals)
        if 'stage_id' in vals or 'probability' in vals:
            self._check_auto_booking_reference()
        return res

