from odoo import api, SUPERUSER_ID

def post_init_hook(env):
    travel_team = env.ref('travel_crm.crm_team_travel_desk', raise_if_not_found=False)
    if travel_team:
        all_users = env['res.users'].search([('share', '=', False)])
        travel_team.write({'member_ids': [(6, 0, all_users.ids)]})

        keywords = ['tour', 'trip', 'honeymoon', 'package', 'inquiry', 'enquiry', 'travel', 'dubai', 'goa', 'kerala', 'bali', 'switzerland', 'paris']
        all_leads = env['crm.lead'].search([])
        travel_leads = all_leads.filtered(lambda l: l.is_travel_lead or l.team_id == travel_team or l.destination_id or l.package_id or any(k in (l.name or '').lower() for k in keywords))
        travel_leads.write({
            'team_id': travel_team.id,
            'type': 'opportunity',
            'is_travel_lead': True,
        })

    confirmed_leads = env['crm.lead'].search([
        ('booking_reference', '=', False)
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
