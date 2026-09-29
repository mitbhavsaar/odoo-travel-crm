from odoo import api, fields, models

class TravelPackage(models.Model):
    _name = 'travel.package'
    _description = 'Travel Package'
    _order = 'name'

    name = fields.Char(string='Package Name', required=True)
    price = fields.Monetary(string='Price', required=True, currency_field='currency_id')
    destination_id = fields.Many2one('travel.destination', string='Destination')
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
    ], string='Package Type')
    description = fields.Text(string='Description')
    active = fields.Boolean(string='Active', default=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Currency', related='company_id.currency_id', readonly=True)

