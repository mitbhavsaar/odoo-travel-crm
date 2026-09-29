import logging
from odoo import api, fields, models
from odoo.tools.image import image_data_uri

_logger = logging.getLogger(__name__)
PROVISIONING_URI_SCHEME = "linphone-config://"


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    @api.model
    def barcode(self, barcode_type, value, **kwargs):
        """Override barcode to catch ReportLab RuntimeError / RenderPMError safely
        when pycairo or renderPM is missing, preventing server crashes."""
        try:
            return super().barcode(barcode_type, value, **kwargs)
        except Exception as e:
            _logger.warning("Barcode generation safely caught error: %s", e)
            return b''


class VoipProvider(models.Model):
    _inherit = 'voip.provider'

    def _cloud_storage_provider(self):
        """Return 'local' if no external cloud storage provider is configured so that
        Odoo's VoIP engine uses the local filestore cleanly without raising cloud storage warnings."""
        res = super()._cloud_storage_provider()
        return res or 'local'

    @api.constrains("recording_enabled", "mode")
    def _check_recording_enabled(self):
        """Bypass the RedirectWarning check when enabling call recording."""
        pass


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    cloud_storage_provider = fields.Selection(
        selection_add=[
            ('local', 'Local Database Filestore'),
        ],
        ondelete={'local': 'set null'},
    )


class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.depends_context("uid")
    @api.depends(
        "uses_odoo_provider",
        "voip_username",
        "res_users_settings_id.voip_linphone_provisioning_serial",
    )
    def _compute_linphone_provisioning(self):
        """Safely compute Linphone QR barcode without crashing if ReportLab renderPM package is missing."""
        for user in self:
            if user == self.env.user and user.uses_odoo_provider and user.voip_username:
                try:
                    url = user._get_linphone_provisioning_url()
                    qr_code = self.env["ir.actions.report"].barcode(
                        "QR",
                        f"{PROVISIONING_URI_SCHEME}{url}",
                        width=512,
                        height=512,
                        barLevel="M",
                    )
                    user.linphone_provisioning_qr_code = image_data_uri(qr_code) if qr_code else False
                    user.linphone_provisioning_url = url
                except Exception:
                    user.linphone_provisioning_qr_code = False
                    try:
                        user.linphone_provisioning_url = user._get_linphone_provisioning_url()
                    except Exception:
                        user.linphone_provisioning_url = False
            else:
                user.linphone_provisioning_qr_code = False
                user.linphone_provisioning_url = False


class VoipCall(models.Model):
    _inherit = 'voip.call'

    @api.model_create_multi
    def create(self, vals_list):
        calls = super().create(vals_list)
        calls._sync_to_travel_call_logs()
        return calls

    def write(self, vals):
        res = super().write(vals)
        self._sync_to_travel_call_logs()
        return res

    def _sync_to_travel_call_logs(self):
        for call in self:
            phone_raw = call.phone_number or ''
            phone_digits = ''.join(c for c in phone_raw if c.isdigit())
            if not phone_digits and not call.partner_id and not (getattr(call, 'activity_res_model', False) == 'crm.lead' and getattr(call, 'activity_res_id', False)):
                continue

            lead = False
            act_model = getattr(call, 'activity_res_model', False)
            act_id = getattr(call, 'activity_res_id', False)

            if act_model == 'crm.lead' and act_id:
                lead = self.env['crm.lead'].sudo().browse(act_id).exists()

            if not lead and phone_digits and len(phone_digits) >= 7:
                search_suffix = phone_digits[-10:]
                lead = self.env['crm.lead'].sudo().search([
                    '|', ('phone', 'like', search_suffix), ('mobile', 'like', search_suffix)
                ], limit=1)

            if not lead and call.partner_id:
                lead = self.env['crm.lead'].sudo().search([('partner_id', '=', call.partner_id.id)], limit=1)

            if lead:
                existing = self.env['travel.call.log'].sudo().search([
                    '|',
                    ('x_voip_call_id', '=', call.id),
                    '&', ('lead_id', '=', lead.id), ('call_datetime', '=', call.start_date or call.create_date)
                ], limit=1)

                if lead and lead.x_call_disposition and lead.x_call_disposition != 'fresh':
                    disposition = lead.x_call_disposition
                elif call.state in ('aborted', 'missed') or (call.duration or 0) == 0:
                    disposition = 'rnr'
                else:
                    disposition = 'interested'

                call_type = 'outgoing' if call.direction == 'outgoing' else ('incoming' if call.direction == 'incoming' else 'missed')
                if call.state == 'aborted' or call.state == 'missed':
                    call_type = 'missed'

                vals = {
                    'lead_id': lead.id,
                    'agent_id': call.user_id.id if call.user_id else self.env.uid,
                    'caller_number': call.phone_number or lead.phone or lead.mobile or 'Unknown',
                    'call_type': call_type,
                    'call_datetime': call.start_date or call.create_date,
                    'duration_seconds': call.duration or 0,
                    'sim_line': 'app',
                    'call_disposition': disposition,
                    'note': f"Odoo Enterprise VoIP Call ({call.state or 'Completed'})",
                    'x_voip_call_id': call.id,
                }

                if existing:
                    existing.sudo().write(vals)
                else:
                    self.env['travel.call.log'].sudo().create(vals)
