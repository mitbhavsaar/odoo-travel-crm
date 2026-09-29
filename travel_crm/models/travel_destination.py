from odoo import api, fields, models


class TravelDestination(models.Model):
    _name = 'travel.destination'
    _description = 'Travel Destination'
    _order = 'name'

    name = fields.Char(required=True)
    country_id = fields.Many2one('res.country', string='Country')
    state_id = fields.Many2one(
        'res.country.state',
        string='State / Province',
        domain="[('country_id', '=', country_id)]"
    )
    is_domestic = fields.Boolean(string='Domestic')
    active = fields.Boolean(default=True)

    @api.onchange('country_id')
    def _onchange_country_id(self):
        if self.country_id and self.state_id and self.state_id.country_id != self.country_id:
            self.state_id = False

