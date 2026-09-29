from odoo import api, fields, models


class TravelLeadQualificationWizard(models.TransientModel):
    _name = 'travel.lead.qualification.wizard'
    _description = 'Call Lead Qualification Pop-up Wizard'

    lead_id = fields.Many2one('crm.lead', string='Lead / Opportunity', required=True, ondelete='cascade')
    destination_id = fields.Many2one('travel.destination', string='Destination')
    travel_date_from = fields.Date(string='Travel Start Date')
    travel_date_to = fields.Date(string='Travel End Date')
    pax_adults = fields.Integer(string='Adults (12+ yrs)', default=1)
    pax_children = fields.Integer(string='Children (2-11 yrs)', default=0)
    pax_infants = fields.Integer(string='Infants (0-2 yrs)', default=0)
    package_type = fields.Selection([
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
    ], string='Package Type', default='fit')
    flight_included = fields.Boolean(string='Flight Included', default=True)
    total_budget = fields.Float(string='Estimated Total Budget (₹)')
    call_disposition = fields.Selection([
        ('fresh', 'Fresh Lead'),
        ('interested', 'Interested'),
        ('call_back', 'Call Back Scheduled'),
        ('rnr', 'RNR (Ring No Response)'),
        ('not_interested', 'Not Interested'),
        ('converted', 'Converted'),
    ], string='Call Disposition', default='interested', required=True)
    qualification_notes = fields.Text(string='Qualification Notes / Client Requirements')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        lead_id = self.env.context.get('default_lead_id') or (
            self.env.context.get('active_id') if self.env.context.get('active_model') == 'crm.lead' else False
        )
        if lead_id:
            lead = self.env['crm.lead'].browse(lead_id)
            if lead.exists():
                valid_pkg = [k for k, _ in self._fields['package_type'].selection]
                valid_disp = [k for k, _ in self._fields['call_disposition'].selection]
                res.update({
                    'lead_id': lead.id,
                    'destination_id': lead.x_destination_id.id if lead.x_destination_id else False,
                    'travel_date_from': lead.x_travel_date_from,
                    'travel_date_to': lead.x_travel_date_to,
                    'pax_adults': lead.x_pax_adults or 1,
                    'pax_children': lead.x_pax_children or 0,
                    'pax_infants': lead.x_pax_infants or 0,
                    'package_type': lead.x_package_type if lead.x_package_type in valid_pkg else 'fit',
                    'flight_included': lead.x_flight_included if hasattr(lead, 'x_flight_included') else True,
                    'total_budget': lead.expected_revenue or 0.0,
                    'call_disposition': lead.x_call_disposition if lead.x_call_disposition in valid_disp else 'interested',
                })
        return res

    def action_apply_qualification(self):
        self.ensure_one()
        lead = self.lead_id

        # 1. Update lead values
        lead_vals = {
            'x_destination_id': self.destination_id.id if self.destination_id else False,
            'x_travel_date_from': self.travel_date_from,
            'x_travel_date_to': self.travel_date_to,
            'x_pax_adults': self.pax_adults,
            'x_pax_children': self.pax_children,
            'x_pax_infants': self.pax_infants,
            'x_package_type': self.package_type,
            'x_call_disposition': self.call_disposition,
        }
        if self.total_budget:
            lead_vals['expected_revenue'] = self.total_budget
        if hasattr(lead, 'x_flight_included'):
            lead_vals['x_flight_included'] = self.flight_included

        # 2. Find and update stage to Qualified
        qualified_stage = self.env.ref('travel_crm.stage_travel_qualified', raise_if_not_found=False)
        if not qualified_stage:
            qualified_stage = self.env['crm.stage'].search([
                ('name', 'ilike', 'Qualified'),
                ('|'), ('team_id', '=', lead.team_id.id), ('team_id', '=', False)
            ], limit=1)
        if qualified_stage:
            lead_vals['stage_id'] = qualified_stage.id

        lead.write(lead_vals)

        # 3. Post summary in Chatter
        dest_name = self.destination_id.name if self.destination_id else 'Not Specified'
        dates_str = f"{self.travel_date_from or 'TBD'} to {self.travel_date_to or 'TBD'}"
        notes_str = self.qualification_notes or 'None'
        pax_str = f"{self.pax_adults} Adults, {self.pax_children} Children, {self.pax_infants} Infants"
        flight_str = "Yes" if self.flight_included else "No"
        disp_dict = dict(self._fields['call_disposition'].selection)
        disp_label = disp_dict.get(self.call_disposition, self.call_disposition)

        chatter_msg = f"""
        <div style="font-family: sans-serif; font-size: 13px;">
            <p style="color: #28a745; font-weight: bold; font-size: 14px; margin-bottom: 6px;">
                ✅ Lead Qualified via Call Qualification Wizard
            </p>
            <table style="width: 100%; max-width: 500px; border-collapse: collapse; border: 1px solid #dee2e6;">
                <tr style="background-color: #f8f9fa;">
                    <td style="padding: 6px 10px; font-weight: bold; width: 40%;">Destination:</td>
                    <td style="padding: 6px 10px;">{dest_name}</td>
                </tr>
                <tr>
                    <td style="padding: 6px 10px; font-weight: bold;">Travel Dates:</td>
                    <td style="padding: 6px 10px;">{dates_str}</td>
                </tr>
                <tr style="background-color: #f8f9fa;">
                    <td style="padding: 6px 10px; font-weight: bold;">Passengers (Pax):</td>
                    <td style="padding: 6px 10px;">{pax_str}</td>
                </tr>
                <tr>
                    <td style="padding: 6px 10px; font-weight: bold;">Package &amp; Budget:</td>
                    <td style="padding: 6px 10px;">{self.package_type.capitalize() if self.package_type else ''} | ₹{self.total_budget:,.2f}</td>
                </tr>
                <tr style="background-color: #f8f9fa;">
                    <td style="padding: 6px 10px; font-weight: bold;">Flight Included:</td>
                    <td style="padding: 6px 10px;">{flight_str}</td>
                </tr>
                <tr>
                    <td style="padding: 6px 10px; font-weight: bold;">Call Disposition:</td>
                    <td style="padding: 6px 10px;"><span class="badge bg-success">{disp_label}</span></td>
                </tr>
            </table>
            <p style="margin-top: 8px;"><b>Notes:</b> {notes_str}</p>
        </div>
        """
        lead.message_post(body=chatter_msg, message_type='comment', subtype_xmlid='mail.mt_note')

        return {'type': 'ir.actions.act_window_close'}
