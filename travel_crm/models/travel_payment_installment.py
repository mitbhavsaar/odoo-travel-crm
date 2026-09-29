from odoo import api, fields, models


class TravelPaymentInstallment(models.Model):
    _name = 'travel.payment.installment'
    _description = 'Travel Payment Installment'
    _order = 'due_date asc, id asc'

    lead_id = fields.Many2one('crm.lead', string='Lead / Opportunity', required=True, ondelete='cascade')
    name = fields.Char(required=True, default='Installment')
    amount = fields.Monetary(required=True, currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', related='lead_id.company_currency', store=True, readonly=True)
    due_date = fields.Date(required=True)
    state = fields.Selection([
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
    ], default='pending', required=True)
    payment_date = fields.Date()
    payment_reference = fields.Char()

    def action_mark_paid(self):
        self.write({'state': 'paid', 'payment_date': fields.Date.context_today(self)})

    @api.model
    def _cron_flag_overdue(self):
        today = fields.Date.context_today(self)
        overdue = self.search([('state', '=', 'pending'), ('due_date', '<', today)])
        overdue.write({'state': 'overdue'})
