from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    travel_gemini_api_key = fields.Char(
        string='Gemini AI API Key',
        config_parameter='travel_crm.gemini_api_key',
        help="Google Gemini API Key used for generating AI Lead Summaries."
    )
    travel_nvidia_api_key = fields.Char(
        string='NVIDIA AI API Key',
        config_parameter='travel_crm.nvidia_api_key',
        help="NVIDIA Llama API Key used as secondary fallback for AI Lead Summaries."
    )
    travel_sla_timeout_minutes = fields.Integer(
        string='SLA Response Timeout (Minutes)',
        config_parameter='travel_crm.sla_timeout_minutes',
        default=15,
        help="Timeout in minutes after which un-contacted leads are auto-reassigned to the next available sales rep."
    )

    def set_values(self):
        # Prevent Odoo 20 cloud_storage module from throwing "Please configure the Cloud Storage before enabling it"
        # when cloud_storage_provider parameter is set to 'local' without an external cloud provider
        ICP = self.env['ir.config_parameter'].sudo()
        if ICP.get_str('cloud_storage_provider') in ('local', 'bare_file_system'):
            ICP.set_str('cloud_storage_provider', False)
        if hasattr(self, 'cloud_storage_provider') and getattr(self, 'cloud_storage_provider', False) in ('local', 'bare_file_system'):
            self.cloud_storage_provider = False
        super().set_values()
