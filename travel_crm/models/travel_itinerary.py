import json
import logging
import uuid
import urllib.request
import urllib.parse
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class TravelItineraryLine(models.Model):
    _name = 'travel.itinerary.line'
    _description = 'Travel Day-wise Itinerary Line'
    _order = 'sequence, day_number, id'

    lead_id = fields.Many2one('crm.lead', string='Lead Opportunity', ondelete='cascade', index=True)
    sequence = fields.Integer('Sequence', default=10)
    day_number = fields.Integer('Day Number', required=True, default=1)
    title = fields.Char('Day Title', required=True)
    description = fields.Text('Activities & Details')
    meals_included = fields.Char('Meals Included', help="e.g. Breakfast, Lunch, Dinner")
    activity_type = fields.Selection([
        ('arrival', '✈️ Arrival & Check-in'),
        ('sightseeing', '🏛️ Sightseeing & City Tour'),
        ('adventure', '🏔️ Adventure & Activity'),
        ('leisure', '🏖️ Leisure & Relax'),
        ('shopping', '🛍️ Local Market & Shopping'),
        ('departure', '🛫 Departure & Transfer'),
    ], default='sightseeing', string='Activity Type')
    image_url = fields.Char('Image URL')


class CrmLeadItineraryExtension(models.Model):
    _inherit = 'crm.lead'

    itinerary_line_ids = fields.One2many(
        'travel.itinerary.line', 'lead_id', string='Day-Wise Itinerary', copy=True)
    portal_access_token = fields.Char(
        'Portal Access Token', copy=False, readonly=True, index=True)
    portal_url = fields.Char(
        compute='_compute_portal_url', string='Portal Web Link')
    itinerary_status = fields.Selection([
        ('draft', 'Draft Itinerary'),
        ('shared', 'Shared with Client'),
        ('accepted', 'Approved / Accepted by Client'),
        ('change_requested', 'Change Requested'),
    ], default='draft', string='Itinerary Status', tracking=True)
    itinerary_inclusions = fields.Text(
        'Inclusions', default="• Accommodation in 4-Star / Deluxe Hotels\n• Daily Breakfast & Welcome Dinner\n• Airport Transfers in Private AC Vehicle\n• Sightseeing & Entry Tickets as per itinerary\n• English Speaking Tour Guide")
    itinerary_exclusions = fields.Text(
        'Exclusions', default="• International / Domestic Airfare (unless specified)\n• Visa Processing Fees & Travel Insurance\n• Personal Expenses, Tips & Porterage\n• Any items not explicitly listed in inclusions")
    customer_feedback_notes = fields.Text('Customer Change Request Notes', readonly=True)

    @api.depends('portal_access_token')
    def _compute_portal_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_str('web.base.url', default='http://localhost:2000')
        for lead in self:
            if lead.portal_access_token:
                lead.portal_url = f"{base_url}/travel/itinerary/{lead.portal_access_token}"
            else:
                lead.portal_url = False

    def _ensure_portal_access_token(self):
        for lead in self:
            if not lead.portal_access_token:
                lead.portal_access_token = uuid.uuid4().hex

    def get_portal_itinerary_url(self):
        self.ensure_one()
        self._ensure_portal_access_token()
        base_url = self.env['ir.config_parameter'].sudo().get_str('web.base.url', default='http://localhost:8069')
        return f"{base_url}/travel/itinerary/{self.portal_access_token}"

    def action_generate_ai_itinerary(self):
        """Generate day-by-day travel itinerary using Gemini / NVIDIA LLM or smart template engine."""
        self.ensure_one()
        destination_name = self.destination_id.name if self.destination_id else (self.name or "Tropical Destination")
        duration = 5
        if self.travel_date_from and self.travel_date_to:
            delta = (self.travel_date_to - self.travel_date_from).days + 1
            if delta > 0:
                duration = delta
        
        pax_info = f"{self.total_pax or 2} Persons ({self.pax_adults or 2} Adults)"
        package_type = dict(self._fields['package_type'].selection).get(self.package_type, 'Standard Tour') if self.package_type else 'Custom Tour'
        budget_str = f"{self.company_currency.symbol or '$'}{self.expected_revenue:,.2f}" if self.expected_revenue else "Standard Budget"

        # Check configured LLM provider and API key
        get_str = self.env['ir.config_parameter'].sudo().get_str
        provider = get_str('travel_crm.ai_provider', default='gemini')
        api_key = get_str('travel_crm.gemini_api_key', default='') if provider == 'gemini' else get_str('travel_crm.nvidia_api_key', default='')

        generated_lines = []
        if api_key:
            try:
                prompt = (
                    f"Create a day-by-day travel itinerary for a {duration}-day trip to {destination_name}.\n"
                    f"Travel Type: {package_type}, Pax: {pax_info}, Budget: {budget_str}.\n"
                    f"Return ONLY a valid JSON array of objects with keys:\n"
                    f'["day_number", "title", "description", "meals_included", "activity_type"]\n'
                    f'activity_type MUST be one of: "arrival", "sightseeing", "adventure", "leisure", "shopping", "departure".\n'
                    f"Make the descriptions vivid, exciting, and professional."
                )
                
                if provider == 'gemini':
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
                    payload = {"contents": [{"parts": [{"text": prompt}]}]}
                    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
                    with urllib.request.urlopen(req, timeout=12) as response:
                        res_data = json.loads(response.read().decode('utf-8'))
                        text_resp = res_data['candidates'][0]['content']['parts'][0]['text']
                        # Strip markdown backticks if any
                        clean_json = text_resp.replace('```json', '').replace('```', '').strip()
                        raw_lines = json.loads(clean_json)
                        for item in raw_lines:
                            generated_lines.append((0, 0, {
                                'day_number': item.get('day_number', 1),
                                'title': item.get('title', 'Day Activities'),
                                'description': item.get('description', ''),
                                'meals_included': item.get('meals_included', 'Breakfast'),
                                'activity_type': item.get('activity_type', 'sightseeing'),
                                'sequence': item.get('day_number', 1) * 10,
                            }))
            except Exception as e:
                _logger.warning("AI LLM Itinerary Generation fallback triggered: %s", str(e))

        # Fallback if API key missing or LLM call failed/unavailable
        if not generated_lines:
            generated_lines = self._generate_fallback_itinerary(destination_name, duration)

        # Clear existing lines and set new AI generated lines
        self.itinerary_line_ids.unlink()
        self.itinerary_line_ids = generated_lines
        self.itinerary_status = 'draft'

        self.message_post(
            body=f"<p style='color: #0080ff; font-weight: bold;'>🤖 AI Day-Wise Itinerary Generated</p>"
                 f"<p>Created <b>{len(generated_lines)} Days</b> of personalized travel itinerary for <b>{destination_name}</b> ({duration} Days).</p>",
            message_type='comment',
            subtype_xmlid='mail.mt_note'
        )
        return True

    def _generate_fallback_itinerary(self, destination, duration):
        lines = []
        # Day 1: Arrival
        lines.append((0, 0, {
            'day_number': 1,
            'title': f'Arrival in {destination} & Hotel Check-in',
            'description': f'Arrive at {destination} airport. Traditional welcome by tour manager, private transfer to hotel. Evening free at leisure to explore local night market.',
            'meals_included': 'Welcome Dinner',
            'activity_type': 'arrival',
            'sequence': 10,
        }))

        # Middle Days: Sightseeing / Adventure / Leisure
        mid_activities = [
            ('Full-Day Iconic City Highlights & Cultural Tour', 'Guided tour of historical monuments, UNESCO sites, and scenic viewpoints with photo stops.', 'Breakfast & Lunch', 'sightseeing'),
            ('Adventure & Nature Excursion', 'Full day excursion to waterfalls, scenic landscape trails, and local artisan village tour.', 'Breakfast & Dinner', 'adventure'),
            ('Beach & Resort Relaxation', 'Free day to enjoy resort amenities, beach activities, water sports, and sunset cruise.', 'Breakfast', 'leisure'),
            ('Shopping & Local Heritage Walk', 'Explore famous local bazaars, handicrafts, authentic local cuisine tasting, and cultural show.', 'Breakfast & Dinner', 'shopping'),
        ]

        for d in range(2, duration):
            act_idx = (d - 2) % len(mid_activities)
            title, desc, meals, act_type = mid_activities[act_idx]
            lines.append((0, 0, {
                'day_number': d,
                'title': f'Day {d}: {title}',
                'description': desc,
                'meals_included': meals,
                'activity_type': act_type,
                'sequence': d * 10,
            }))

        # Final Day: Departure
        lines.append((0, 0, {
            'day_number': duration,
            'title': f'Day {duration}: Farewell {destination} & Airport Transfer',
            'description': f'Enjoy a leisurely breakfast at the hotel. Check-out and private transfer to airport for your onward flight with wonderful memories of {destination}!',
            'meals_included': 'Breakfast',
            'activity_type': 'departure',
            'sequence': duration * 10,
        }))
        return lines

    def action_share_itinerary_portal(self):
        self.ensure_one()
        if not self.itinerary_line_ids:
            raise UserError(_("Please generate or add day-wise itinerary lines before sharing with client."))
        
        self._ensure_portal_access_token()
        self.itinerary_sent = True
        self.itinerary_sent_date = fields.Datetime.now()
        self.itinerary_status = 'shared'

        # Move to 'Itinerary Shared' stage if present
        shared_stage = self.env.ref('travel_crm.stage_travel_itinerary_shared', raise_if_not_found=False)
        if not shared_stage:
            domain = [('name', 'ilike', 'itinerary')]
            if self.team_id:
                domain = ['&'] + domain + ['|', ('team_ids', '=', False), ('team_ids', 'in', [self.team_id.id])]
            shared_stage = self.env['crm.stage'].search(domain, limit=1)
        if shared_stage:
            self.stage_id = shared_stage.id

        portal_url = self.get_portal_itinerary_url()
        self.message_post(
            body=f"<p>🌐 <b>Day-Wise Itinerary Shared via Customer Web Portal</b><br/>"
                 f"Public Customer Portal Link: <a href='{portal_url}' target='_blank'>{portal_url}</a></p>",
            message_type='comment',
            subtype_xmlid='mail.mt_note'
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Itinerary Shared Successfully!"),
                'message': _("Customer portal link has been generated and logged in chatter."),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_preview_itinerary_portal(self):
        self.ensure_one()
        portal_url = self.get_portal_itinerary_url()
        return {
            'type': 'ir.actions.act_url',
            'url': portal_url,
            'target': 'new',
        }
