from odoo import api, SUPERUSER_ID

def post_init_hook(env):
    confirmed_leads = env['crm.lead'].search([
        ('x_booking_reference', '=', False)
    ]).filtered(lambda l: l.stage_id and (
        'booking' in (l.stage_id.name or '').lower() or
        'confirmed' in (l.stage_id.name or '').lower() or
        'won' in (l.stage_id.name or '').lower() or
        'trip' in (l.stage_id.name or '').lower() or
        'documentation' in (l.stage_id.name or '').lower() or
        l.stage_id.is_won
    ))
    for lead in confirmed_leads:
        lead._check_auto_booking_reference()
