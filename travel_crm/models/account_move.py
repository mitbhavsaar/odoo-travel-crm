from odoo import fields, models

class AccountMove(models.Model):
    _inherit = 'account.move'

    lead_id = fields.Many2one('crm.lead', string='Travel Lead')
