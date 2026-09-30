from odoo import api, fields, models, _

class TravelLeadInvoiceWizard(models.TransientModel):
    _name = 'travel.lead.invoice.wizard'
    _description = 'Travel Lead Invoice Wizard'

    lead_id = fields.Many2one('crm.lead', string='Lead', required=True)
    advance_payment_method = fields.Selection([
        ('delivered', 'Regular Invoice'),
        ('percentage', 'Down payment (percentage)'),
        ('fixed', 'Down payment (fixed amount)'),
    ], string='Create Invoice', default='delivered', required=True)

    amount = fields.Monetary(string='Down Payment Amount', currency_field='currency_id')
    amount_percentage = fields.Float(string='Down Payment Percentage', default=10.0)
    currency_id = fields.Many2one('res.currency', related='lead_id.company_currency', readonly=True)

    def action_create_invoices(self):
        self.ensure_one()
        lead = self.lead_id
        partner = lead.partner_id
        if not partner:
            partner_name = (
                (lead.contact_name if lead.contact_name and '@' not in lead.contact_name else False) or
                (lead.partner_name if lead.partner_name and '@' not in lead.partner_name else False) or
                lead.name or
                'Customer'
            )
            partner = self.env['res.partner'].create({
                'name': partner_name,
                'phone': lead.phone or lead.mobile,
                'email': lead.email_from if lead.email_from and '@' in lead.email_from else False,
                'street': lead.street,
                'city': lead.city,
                'state_id': lead.state_id.id if lead.state_id else False,
                'country_id': lead.country_id.id if lead.country_id else False,
            })
            lead.partner_id = partner.id

        total_amount = lead.expected_revenue or (lead.package_id.price if lead.package_id else 0.0)
        if self.advance_payment_method == 'percentage':
            inv_amount = total_amount * (self.amount_percentage / 100.0)
            line_name = f"Down Payment ({self.amount_percentage}%) for {lead.package_id.name if lead.package_id else lead.name}"
        elif self.advance_payment_method == 'fixed':
            inv_amount = self.amount
            line_name = f"Down Payment for {lead.package_id.name if lead.package_id else lead.name}"
        else:
            inv_amount = total_amount
            line_name = f"{lead.package_id.name if lead.package_id else 'Travel Booking - ' + lead.name}{' (' + lead.destination_id.name + ')' if lead.destination_id else ''}"

        income_account = self.env['account.account'].search([
            ('account_type', '=', 'income')
        ], limit=1)

        move_vals = {
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'lead_id': lead.id,
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': [(0, 0, {
                'name': line_name,
                'quantity': 1.0,
                'price_unit': inv_amount,
                'account_id': income_account.id if income_account else False,
            })],
        }
        invoice = self.env['account.move'].create(move_vals)

        lead.message_post(
            body=f"<p style='color: #28a745; font-weight: bold;'>🧾 Customer Invoice Created ({dict(self._fields['advance_payment_method'].selection).get(self.advance_payment_method)})</p>"
                 f"<p>Invoice <b>{invoice.name or 'Draft'}</b> created for customer <b>{partner.name}</b> with total <b>₹{inv_amount:,.2f}</b>.</p>",
            message_type='comment',
            subtype_xmlid='mail.mt_note'
        )

        return {
            'type': 'ir.actions.act_window',
            'name': 'Customer Invoice',
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }
