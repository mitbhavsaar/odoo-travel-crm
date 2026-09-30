import logging
from odoo import http, _
from odoo.http import request

_logger = logging.getLogger(__name__)


class TravelItineraryPortalController(http.Controller):

    @http.route('/travel/itinerary/<string:token>', type='http', auth='public', website=True, sitemap=False)
    def view_itinerary_portal(self, token, **kw):
        lead = request.env['crm.lead'].sudo().search([('portal_access_token', '=', token)], limit=1)
        if not lead:
            return request.not_found()

        status_msg = kw.get('status')
        values = {
            'lead': lead,
            'status_msg': status_msg,
            'page_name': 'travel_itinerary_portal',
        }
        return request.render('travel_crm.portal_itinerary_template', values)

    @http.route('/travel/itinerary/<string:token>/accept', type='http', auth='public', methods=['POST'], website=True, csrf=True)
    def accept_itinerary_portal(self, token, **kw):
        lead = request.env['crm.lead'].sudo().search([('portal_access_token', '=', token)], limit=1)
        if not lead:
            return request.not_found()

        lead.write({
            'itinerary_status': 'accepted',
        })

        # Move to Negotiation or Booking Confirmed stage if present
        next_stage = request.env.ref('travel_crm.stage_travel_booking_confirmed', raise_if_not_found=False) \
            or request.env.ref('travel_crm.stage_travel_negotiation', raise_if_not_found=False)
        if not next_stage:
            domain = ['|', ('name', 'ilike', 'booking'), ('name', 'ilike', 'negotiation')]
            if lead.team_id:
                domain = ['&'] + domain + ['|', ('team_ids', '=', False), ('team_ids', 'in', [lead.team_id.id])]
            next_stage = request.env['crm.stage'].sudo().search(domain, limit=1)

        if next_stage:
            lead.stage_id = next_stage.id

        lead.message_post(
            body=f"<p>🎉 <b>Customer Approved &amp; Confirmed Itinerary!</b><br/>"
                 f"The customer approved their day-wise travel itinerary via the Web Portal link.</p>",
            message_type='comment',
            subtype_xmlid='mail.mt_note'
        )

        return request.redirect(f'/travel/itinerary/{token}?status=accepted')

    @http.route('/travel/itinerary/<string:token>/request_change', type='http', auth='public', methods=['POST'], website=True, csrf=True)
    def request_change_itinerary_portal(self, token, **kw):
        lead = request.env['crm.lead'].sudo().search([('portal_access_token', '=', token)], limit=1)
        if not lead:
            return request.not_found()

        feedback = kw.get('customer_feedback', '').strip()
        lead.write({
            'itinerary_status': 'change_requested',
            'customer_feedback_notes': feedback,
        })

        lead.message_post(
            body=f"<p>⚠️ <b>Customer Requested Itinerary Changes</b><br/>"
                 f"<b>Customer Notes:</b> {feedback or 'No notes provided'}</p>",
            message_type='comment',
            subtype_xmlid='mail.mt_note'
        )

        return request.redirect(f'/travel/itinerary/{token}?status=change_requested')
