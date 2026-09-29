{
    'name': 'Travel Agency CRM',
    'version': '20.0.1.0.0',
    'category': 'Sales/CRM',
    'summary': 'Lead-to-booking CRM for travel agencies, built on Odoo CRM',
    'description': """
Travel Agency CRM
==================
Extends Odoo's CRM app with a travel-agency pipeline and lead-management
capabilities, designed to replicate the workflow of vertical CRM tools
(lead capture, call/WhatsApp logging, automation rules, AI lead summaries,
follow-up dashboards, and a rep leaderboard) for a travel-agency vertical:

* Travel-specific lead fields: destination, travel dates, pax breakdown,
  package type, visa/KYC status, itinerary tracking, booking reference.
* A dedicated "Travel Desk" sales team and pipeline stages (Inquiry ->
  Itinerary Shared -> Negotiation -> Booking Confirmed -> Documentation &
  Payment -> Trip Confirmed).
* A call-disposition field for granular funnel tracking (Fresh Lead, RNR,
  Interested, Call Back Later, Not Interested, Converted).
* A payment installment tracker per lead (for group/package bookings paid
  in parts).
* Automation rules that fire on stage change / call disposition to
  schedule follow-ups and send templated messages automatically.
* A dashboard (pivot/graph) approximating a follow-ups board, funnel
  breakdown, and team leaderboard.
* A stub AI "Lead Summary" action, ready to be wired to an LLM API.
* A per-call log (travel.call.log) with structured, LLM-ready post-call
  AI coaching fields (skill scores, decision-maker flag, sentiment,
  conversion probability, qualitative feedback) - mirrors TeleCRM's
  "Lead-IQ" panel.
* Two inbound webhook endpoints (API-key secured) so a mobile call-sync
  app can push SIM call logs, and travel portals / ad platforms can push
  leads directly into the pipeline, without a bespoke connector per source.
* A multi-step "Export Activity Report" wizard (select fields -> customize
  columns -> download XLSX), matching TeleCRM's export builder.
* A WhatsApp quick-chat button (wa.me) on the lead form as a lightweight
  fallback; Odoo Enterprise's native WhatsApp app is the config path to
  full two-way synced messaging.
""",
    'author': '361 Techno Consulting',
    'depends': ['crm', 'account', 'sale_crm', 'mail', 'sms', 'calendar', 'base_automation', 'voip'],
    'data': [
        'security/ir.access.csv',
        'data/crm_team_data.xml',
        'data/crm_stage_data.xml',
        'data/mail_template_data.xml',
        'data/automation_data.xml',
        'data/travel_export_field_data.xml',
        'views/crm_lead_views.xml',
        'views/travel_destination_views.xml',
        'views/travel_package_views.xml',
        'views/travel_payment_views.xml',

        'views/travel_call_log_views.xml',
        'views/travel_export_wizard_views.xml',
        'views/travel_lead_qualification_wizard_views.xml',
        'views/travel_lead_invoice_wizard_views.xml',
        'views/res_config_settings_views.xml',
        'views/crm_dashboard_views.xml',
        'views/crm_menu_views.xml',
    ],


    'demo': [
        'data/demo_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'travel_crm/static/src/scss/crm_dashboard.scss',
            'travel_crm/static/src/js/crm_dashboard.js',
            'travel_crm/static/src/xml/crm_dashboard.xml',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,

    'application': True,
    'license': 'LGPL-3',
}

