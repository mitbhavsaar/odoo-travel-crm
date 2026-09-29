import base64
import io

from odoo import api, fields, models
from odoo.exceptions import UserError


class TravelExportField(models.Model):
    """Seeded catalogue of exportable fields, so the wizard's 'Select Action
    Fields' step (step 1 of TeleCRM's Export Activity Report builder) has a
    friendly, curated pick-list instead of raw technical field names."""
    _name = 'travel.export.field'
    _description = 'Travel Export Field'
    _order = 'sequence, id'
    _rec_name = 'label'

    name = fields.Char(string='Technical Name', required=True)
    label = fields.Char(string='Column Label', required=True)
    source = fields.Selection([
        ('call_log', 'Call Log'),
        ('lead', 'Lead / Opportunity'),
    ], required=True, default='call_log')
    field_type = fields.Selection([
        ('char', 'Text'), ('selection', 'Selection'), ('many2one', 'Many2one'),
        ('datetime', 'Datetime'), ('date', 'Date'), ('integer', 'Number'),
        ('float', 'Decimal'), ('boolean', 'Yes/No'),
    ], default='char')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)


class TravelExportWizardLine(models.TransientModel):
    _name = 'travel.export.wizard.line'
    _description = 'Travel Export Wizard Column'
    _order = 'sequence, id'

    wizard_id = fields.Many2one('travel.export.wizard', ondelete='cascade')
    export_field_id = fields.Many2one('travel.export.field', required=True)
    custom_label = fields.Char(string='Column Header')
    sequence = fields.Integer(default=10)


class TravelExportWizard(models.TransientModel):
    """Multi-step 'Export Activity Report' builder, mirroring TeleCRM's flow:
    (1) Select Action Fields -> (2) Customize Column (reorder + rename) ->
    (3) generate & download an XLSX."""
    _name = 'travel.export.wizard'
    _description = 'Export Activity Report'

    state = fields.Selection([
        ('select', 'Select Fields'),
        ('customize', 'Customize Columns'),
        ('done', 'Download'),
    ], default='select')

    team_id = fields.Many2one('crm.team', string='Sales Team')
    date_from = fields.Date(string='From')
    date_to = fields.Date(string='To')
    agent_id = fields.Many2one('res.users', string='Agent')

    field_ids = fields.Many2many('travel.export.field', string='Fields to Export')
    line_ids = fields.One2many('travel.export.wizard.line', 'wizard_id', string='Columns')

    file_data = fields.Binary(string='Export File', readonly=True)
    file_name = fields.Char(string='File Name', readonly=True)
    record_count = fields.Integer(readonly=True)

    def action_next_to_customize(self):
        self.ensure_one()
        if not self.field_ids:
            raise UserError("Select at least one field to export.")
        self.line_ids.unlink()
        lines = [(0, 0, {
            'export_field_id': f.id,
            'custom_label': f.label,
            'sequence': index * 10,
        }) for index, f in enumerate(self.field_ids.sorted('sequence'))]
        self.write({'line_ids': lines, 'state': 'customize'})
        return self._reopen()

    def action_back_to_select(self):
        self.state = 'select'
        return self._reopen()

    def action_back_to_customize(self):
        self.state = 'customize'
        return self._reopen()

    def _get_call_log_domain(self):
        domain = []
        if self.team_id:
            domain.append(('team_id', '=', self.team_id.id))
        if self.agent_id:
            domain.append(('agent_id', '=', self.agent_id.id))
        if self.date_from:
            domain.append(('call_datetime', '>=', self.date_from))
        if self.date_to:
            domain.append(('call_datetime', '<=', self.date_to))
        return domain

    def _format_value(self, record, export_field):
        source_rec = record if export_field.source == 'call_log' else record.lead_id
        if not source_rec:
            return ''
        value = getattr(source_rec, export_field.name, '')
        field_def = source_rec._fields.get(export_field.name)
        if field_def is None:
            return value or ''
        if field_def.type == 'many2one':
            return value.display_name if value else ''
        if field_def.type == 'selection':
            selection = field_def.selection
            if callable(selection):
                selection = field_def._description_selection(source_rec.env)
            return dict(selection or []).get(value, value or '')
        if field_def.type == 'boolean':
            return 'Yes' if value else 'No'
        if field_def.type in ('datetime', 'date') and value:
            return str(value)
        return value if value is not False else ''

    def action_generate_export(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError("No columns configured - go back and select fields first.")
        logs = self.env['travel.call.log'].search(self._get_call_log_domain())

        output = io.BytesIO()
        workbook = __import__('xlsxwriter').Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Activity Report')
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#F0F0F0', 'border': 1})

        lines = self.line_ids.sorted('sequence')
        for col, line in enumerate(lines):
            sheet.write(0, col, line.custom_label or line.export_field_id.label, header_fmt)
            sheet.set_column(col, col, 22)
        for row, log in enumerate(logs, start=1):
            for col, line in enumerate(lines):
                sheet.write(row, col, self._format_value(log, line.export_field_id))
        workbook.close()
        output.seek(0)

        self.write({
            'file_data': base64.b64encode(output.read()),
            'file_name': 'travel_activity_report.xlsx',
            'record_count': len(logs),
            'state': 'done',
        })
        return self._reopen()

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'travel.export.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_download(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/travel.export.wizard/%s/file_data/%s?download=true' % (
                self.id, self.file_name),
            'target': 'self',
        }
