import logging
from datetime import datetime, timedelta
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class CrmLeadSLAReassignment(models.Model):
    _inherit = 'crm.lead'

    sla_deadline = fields.Datetime('SLA Response Deadline', tracking=True)
    sla_status = fields.Selection([
        ('on_track', '⏱️ SLA On Track'),
        ('breached', '⚠️ SLA Breached (Auto-Reassigned)'),
        ('resolved', '✅ SLA Met / Contacted'),
    ], default='on_track', string='SLA Status', compute='_compute_sla_status', store=True, tracking=True)
    sla_breach_count = fields.Integer('SLA Reassignment Count', default=0)
    last_assigned_date = fields.Datetime('Last Assigned Date', default=fields.Datetime.now)

    @api.model_create_multi
    def create(self, vals_list):
        leads = super().create(vals_list)
        get_param = self.env['ir.config_parameter'].sudo().get_str
        sla_mins = int(get_param('travel_crm.sla_timeout_minutes', default=15) or 15)
        now = fields.Datetime.now()
        for lead in leads:
            if lead.is_travel_lead and not lead.sla_deadline:
                lead.sla_deadline = now + timedelta(minutes=sla_mins)
                lead.last_assigned_date = now
        return leads

    def write(self, vals):
        # If user_id changes, reset SLA timer
        if 'user_id' in vals:
            vals['last_assigned_date'] = fields.Datetime.now()
            get_param = self.env['ir.config_parameter'].sudo().get_str
            sla_mins = int(get_param('travel_crm.sla_timeout_minutes', default=15) or 15)
            vals['sla_deadline'] = fields.Datetime.now() + timedelta(minutes=sla_mins)

        res = super().write(vals)

        # If call disposition or stage changes away from fresh, mark SLA as resolved
        if any(f in vals for f in ['call_disposition', 'stage_id', 'itinerary_sent']):
            for lead in self:
                if lead.call_disposition != 'fresh' or lead.itinerary_sent:
                    if lead.sla_status != 'resolved':
                        lead.write({'sla_status': 'resolved'})

        return res

    @api.depends('sla_deadline', 'call_disposition', 'itinerary_sent')
    def _compute_sla_status(self):
        now = fields.Datetime.now()
        for lead in self:
            if lead.call_disposition != 'fresh' or lead.itinerary_sent:
                lead.sla_status = 'resolved'
            elif lead.sla_deadline and lead.sla_deadline < now and lead.sla_status != 'breached':
                lead.sla_status = 'breached'
            elif not lead.sla_status:
                lead.sla_status = 'on_track'

    def action_trigger_sla_reassign_now(self):
        """Manually trigger SLA Reassignment for testing or manager override."""
        self.ensure_one()
        prev_user = self.user_id
        next_user = self._reassign_lead_due_to_sla_breach()
        
        msg = _("⚡ Lead SLA Reassigned! Reassigned from %s to %s.") % (
            prev_user.name if prev_user else 'Unassigned',
            next_user.name if next_user else 'Unassigned'
        )
        if prev_user != next_user:
            msg += _("\n\n💡 NOTE: If you are filtering by 'My Opportunities', remove the filter in the top search bar to see leads assigned to other team members.")

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("SLA Lead Auto-Reassigned"),
                'message': msg,
                'type': 'warning' if prev_user != next_user else 'info',
                'sticky': True,
            }
        }

    def _reassign_lead_due_to_sla_breach(self):
        self.ensure_one()
        travel_team = self.env.ref('travel_crm.crm_team_travel_desk', raise_if_not_found=False) or self.team_id
        members = travel_team.member_ids if travel_team else self.env['res.users'].search([('share', '=', False)])

        # Pick next available member excluding current user
        candidate_members = members.filtered(lambda u: u.id != self.user_id.id and u.active and not u.share)
        if candidate_members:
            # Pick user with lowest open lead count
            next_user = sorted(candidate_members, key=lambda u: len(u.opportunity_ids.filtered(lambda l: l.stage_id and not l.stage_id.is_won)))[0]
        else:
            next_user = self.user_id or self.env.user

        prev_user_name = self.user_id.name if self.user_id else 'Unassigned'
        now = fields.Datetime.now()
        get_param = self.env['ir.config_parameter'].sudo().get_str
        sla_mins = int(get_param('travel_crm.sla_timeout_minutes', default=15) or 15)

        vals = {
            'user_id': next_user.id,
            'sla_status': 'breached',
            'sla_breach_count': self.sla_breach_count + 1,
            'sla_deadline': now + timedelta(minutes=sla_mins),
            'last_assigned_date': now,
            'type': 'opportunity',
        }
        if travel_team:
            vals['team_id'] = travel_team.id

        self.write(vals)

        # Post chatter escalation note
        self.message_post(
            body=f"<p>⚠️ <b>SLA BREACH DETECTED &amp; AUTO-REASSIGNED!</b><br/>"
                 f"No call or response was logged within {sla_mins} minutes.<br/>"
                 f"Reassigned from <b>{prev_user_name}</b> to <b>{next_user.name}</b>.<br/>"
                 f"SLA Reassignment Count: <b>{self.sla_breach_count}</b></p>",
            message_type='comment',
            subtype_xmlid='mail.mt_note'
        )

        # Schedule urgent activity for new rep
        if next_user.id != self.env.uid:
            self.activity_schedule(
                'mail.mail_activity_data_call',
                summary=_("⚠️ URGENT SLA Breach: Immediate Call Required!"),
                note=_("This lead was auto-reassigned to you due to an SLA breach from %s. Please call immediately!") % prev_user_name,
                user_id=next_user.id
            )

        return next_user

    @api.model
    def _cron_check_sla_breaches(self):
        """Cron job executing every 5 minutes to check for un-contacted SLA breached leads."""
        now = fields.Datetime.now()
        breached_leads = self.search([
            ('is_travel_lead', '=', True),
            ('call_disposition', '=', 'fresh'),
            ('itinerary_sent', '=', False),
            ('sla_deadline', '<=', now),
        ])
        _logger.info("Cron SLA Check: Found %s breached travel leads for auto-reassignment.", len(breached_leads))
        for lead in breached_leads:
            try:
                lead._reassign_lead_due_to_sla_breach()
            except Exception as e:
                _logger.error("Failed to reassign lead %s on SLA breach: %s", lead.id, str(e))
