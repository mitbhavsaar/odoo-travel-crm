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
