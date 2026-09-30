import random

from odoo import api, fields, models


class TravelCallLog(models.Model):
    _name = 'travel.call.log'
    _description = 'Travel Call Log & AI Coaching'
    _order = 'call_datetime desc, id desc'
    _rec_name = 'caller_number'

    # -- Linkage --------------------------------------------------------
    lead_id = fields.Many2one('crm.lead', string='Lead / Opportunity', ondelete='cascade', index=True)
    agent_id = fields.Many2one('res.users', string='Agent', default=lambda self: self.env.user)
    team_id = fields.Many2one(related='lead_id.team_id', store=True, string='Sales Team')
    voip_call_id = fields.Many2one('voip.call', string='VoIP Call Log', ondelete='set null', index=True)

    # -- Call metadata (mirrors the fields on TeleCRM's Export Activity
    #    Report: Called On, Call Start Time, Call Type, Duration, Feedback,
    #    Note, Caller, First Attempted/Successful Contact, Campaign Name) --
    caller_number = fields.Char(string='Caller / Number', required=True)
    call_type = fields.Selection([
        ('outgoing', 'Outgoing'),
        ('incoming', 'Incoming'),
        ('missed', 'Missed'),
    ], string='Call Type', default='outgoing', required=True)
    call_datetime = fields.Datetime(string='Call Start Time', default=fields.Datetime.now, required=True)
    duration_seconds = fields.Integer(string='Duration (sec)')
    duration_display = fields.Char(compute='_compute_duration_display', string='Duration')
    sim_line = fields.Selection([
        ('sim1', 'SIM 1'),
        ('sim2', 'SIM 2'),
        ('app', 'In-App / VoIP'),
    ], string='SIM / Line', default='sim1',
        help="Which device line the call was placed/received on. Populated by the mobile "
             "call-sync app (see the /travel_crm/api/call_log endpoint) when call-log sync "
             "is wired up, or set manually.")
    campaign_name = fields.Char(string='Campaign Name')
    is_first_attempt = fields.Boolean(string='First Attempted Contact')
    is_first_success = fields.Boolean(string='First Successful Contact')
    note = fields.Text(string='Call Note')
    recording_url = fields.Char(
        string='Recording Link',
        help="Link to the call recording, if the telephony/call-sync provider stores one.")
    recording_file = fields.Binary(string='Audio Recording (MP3)', attachment=True)
    recording_filename = fields.Char(string='Audio Filename', default='call_recording.mp3')
    recording_player_html = fields.Html(compute='_compute_recording_player_html', string='Audio Player')

    call_disposition = fields.Selection(
        selection=lambda self: self.env['crm.lead']._fields['call_disposition'].selection,
        string='Disposition')

    @api.depends('recording_file', 'recording_filename', 'recording_url')
    def _compute_recording_player_html(self):
        for rec in self:
            if rec.recording_file:
                src = f"/web/content/travel.call.log/{rec.id}/recording_file/{rec.recording_filename or 'call_recording.mp3'}"
                rec.recording_player_html = f'''
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <audio controls style="height: 32px; max-width: 220px;">
                            <source src="{src}" type="audio/mpeg"/>
                            Your browser does not support audio element.
                        </audio>
                        <a href="{src}?download=true" class="btn btn-sm btn-outline-secondary" title="Download MP3">
                            <i class="oi" data-icon="download"></i> Download
                        </a>
                    </div>
                '''
            elif rec.recording_url:
                rec.recording_player_html = f'''
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <audio controls style="height: 32px; max-width: 220px;">
                            <source src="{rec.recording_url}" type="audio/mpeg"/>
                            Your browser does not support audio element.
                        </audio>
                        <a href="{rec.recording_url}" target="_blank" download="call_recording.mp3" class="btn btn-sm btn-outline-secondary" title="Download MP3">
                            <i class="oi" data-icon="download"></i> Download
                        </a>
                    </div>
                '''
            else:
                rec.recording_player_html = '<span class="text-muted" style="font-size: 12px; font-style: italic;">No Recording</span>'

    # -- AI post-call coaching / scoring (mirrors TeleCRM's Lead-IQ panel:
    #    per-skill ratings, objection-handling / conversion percentages,
    #    decision-maker flag, and qualitative agent coaching notes) -------
    ai_generated = fields.Boolean(string='AI Score Generated', readonly=True)
    ai_generated_on = fields.Datetime(string='AI Score Generated On', readonly=True)
    ai_rapport_score = fields.Integer(string='Rapport Building', readonly=True)
    ai_needs_discovery_score = fields.Integer(string='Needs Discovery', readonly=True)
    ai_objection_handling_score = fields.Integer(string='Objection Handling', readonly=True)
    ai_closing_score = fields.Integer(string='Closing Technique', readonly=True)
    ai_overall_score = fields.Integer(
        compute='_compute_ai_overall_score', store=True, string='Overall Call Score')
    ai_conversion_probability = fields.Float(string='Conversion Probability (%)', readonly=True)
    ai_is_decision_maker = fields.Boolean(string='Speaking to Decision Maker', readonly=True)
    ai_sentiment = fields.Selection([
        ('positive', 'Positive'),
        ('neutral', 'Neutral'),
        ('negative', 'Negative'),
    ], string='Caller Sentiment', readonly=True)
    ai_feedback_good = fields.Text(string='What Went Well', readonly=True)
    ai_feedback_improve = fields.Text(string='Could Improve', readonly=True)

    @api.depends('duration_seconds')
    def _compute_duration_display(self):
        for rec in self:
            secs = rec.duration_seconds or 0
            rec.duration_display = '%d:%02d' % (secs // 60, secs % 60)

    @api.depends('ai_rapport_score', 'ai_needs_discovery_score',
                 'ai_objection_handling_score', 'ai_closing_score')
    def _compute_ai_overall_score(self):
        for rec in self:
            scores = [s for s in (
                rec.ai_rapport_score, rec.ai_needs_discovery_score,
                rec.ai_objection_handling_score, rec.ai_closing_score) if s]
            rec.ai_overall_score = round(sum(scores) / len(scores)) if scores else 0

    def action_generate_ai_score(self):
        """Stub for an LLM-backed post-call scoring pass (TeleCRM's 'Lead-IQ'-style
        panel: per-skill ratings, objection-handling/conversion %, decision-maker
        detection, and qualitative coaching feedback, all derived from the call
        recording/transcript).

        This produces a *structurally complete* score using simple heuristics
        (call duration + disposition) so the panel is fully usable end-to-end
        today. To make the numbers real: send `recording_url` (or a transcript)
        to a speech-to-text + LLM pipeline (Anthropic/OpenAI, or Odoo's IAP LLM
        connector once available for CRM), parse a structured response, and
        write it into these same fields instead of the heuristic below.
        """
        for rec in self:
            duration = rec.duration_seconds or 0
            base = 40 if duration < 30 else 60 if duration < 120 else 80
            jitter = lambda: max(0, min(100, base + random.randint(-15, 15)))
            rec.ai_rapport_score = jitter()
            rec.ai_needs_discovery_score = jitter()
            rec.ai_objection_handling_score = jitter()
            rec.ai_closing_score = jitter()
            rec.ai_conversion_probability = round(
                (rec.ai_rapport_score + rec.ai_closing_score) / 2 * 0.8, 1)
            rec.ai_is_decision_maker = rec.call_disposition in ('interested', 'converted')
            rec.ai_sentiment = (
                'positive' if rec.call_disposition in ('interested', 'converted')
                else 'negative' if rec.call_disposition == 'not_interested'
                else 'neutral')
            disp_label = dict(self._fields['call_disposition']._description_selection(self.env)).get(rec.call_disposition, rec.call_disposition or 'n/a') if rec.call_disposition else 'n/a'
            rec.ai_feedback_good = (
                "[Stub] Call lasted %s; agent reached disposition '%s'. Connect an LLM "
                "API key to generate real coaching feedback from the recording/transcript."
                % (rec.duration_display, disp_label))
            rec.ai_feedback_improve = (
                "[Stub] Suggested improvement areas will appear here once AI scoring "
                "is connected to a real transcript source."
            )
            rec.ai_generated = True
            rec.ai_generated_on = fields.Datetime.now()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'lead_id' in vals and vals['lead_id'] and not vals.get('call_disposition'):
                lead = self.env['crm.lead'].browse(vals['lead_id'])
                if lead and lead.call_disposition and lead.call_disposition != 'fresh':
                    vals['call_disposition'] = lead.call_disposition
        recs = super().create(vals_list)
        for rec in recs:
            if rec.lead_id and rec.call_disposition and rec.call_disposition != rec.lead_id.call_disposition:
                rec.lead_id.call_disposition = rec.call_disposition
        return recs

    def write(self, vals):
        res = super().write(vals)
        if 'call_disposition' in vals:
            for rec in self:
                if rec.lead_id and rec.call_disposition and rec.call_disposition != rec.lead_id.call_disposition:
                    rec.lead_id.call_disposition = rec.call_disposition
        return res

