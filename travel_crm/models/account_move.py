from odoo import fields, models

class AccountMove(models.Model):
    _inherit = 'account.move'

    x_lead_id = fields.Many2one('crm.lead', string='Travel Lead')
