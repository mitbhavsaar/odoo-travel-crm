# Travel Agency CRM (`travel_crm`) - Odoo 20.0

A comprehensive Lead-to-Booking CRM module for Travel Agencies built on top of Odoo 20 CRM. Inspired by TeleCRM & vertical travel tools, it adds destination management, call/SIM logging, automated follow-ups, payment installment tracking, AI coaching summaries, custom dashboards, system configuration settings, and inbound webhooks.

---

## 📋 Table of Contents
1. [Overview & Key Features](#-overview--key-features)
2. [Module Architecture](#-module-architecture)
3. [Configuration & Settings](#-configuration--settings)
4. [Step-by-Step Lead Lifecycle & Workflow](#-step-by-step-lead-lifecycle--workflow)
5. [Models & Data Fields](#-models--data-fields)
6. [Automated Actions & Triggers](#-automated-actions--triggers)
7. [Call Logging & AI Coaching ("Lead-IQ")](#-call-logging--ai-coaching-lead-iq)
8. [API & Inbound Webhooks](#-api--inbound-webhooks)
9. [Export Activity Report Wizard](#-export-activity-report-wizard)
10. [Payment Installment Tracking](#-payment-installment-tracking)
11. [Dashboards & Analytics](#-dashboards--analytics)
12. [Installation & Setup](#-installation--setup)

---

## 🌟 Overview & Key Features

* **Dedicated Sales Team ("Travel Desk")**: Scopes travel-specific fields so generic sales opportunities remain unaffected.
* **Travel Pipeline Stages**: Structured from `New Inquiry` to `Trip Confirmed (Won)`.
* **Automatic Stage Updates**: Clicking **Mark Itinerary as Shared** automatically transitions the lead stage to **Itinerary Shared**.
* **AI API Key Management & Lead Summary**: Configure Google Gemini or NVIDIA API keys via System Settings (**Travel Desk -> Configuration -> Settings**). Generates rich AI executive narratives and actionable next-step recommendations without hardcoded default fallback keys.
* **Travel Lead Details**: Destination, Travel Dates, Pax breakdown (Adults, Children, Infants), Package Type.
* **Documentation & Visas**: Visa Status, KYC Document Verification, Travel Insurance.
* **Call Disposition**: Fresh Lead, RNR, Interested, Call Back Later, Not Interested, Converted.
* **Payment Installment Tracker**: Manage deposit & partial payments for group or customized travel packages.
* **Automated Email & Activity Scheduling**: Automatic acknowledgement emails, follow-up calls, and KYC document collection tasks.
* **Call Logs & AI Coaching**: Track caller number, SIM line (SIM 1 / SIM 2 / App), call duration, recording link, and AI skill scores (Rapport, Needs Discovery, Closing, Objection Handling, Sentiment Analysis).
* **API Webhooks**: Secure endpoints (`/travel_crm/api/lead`, `/travel_crm/api/call_log`, Meta Leadgen, IndiaMART, JustDial) for mobile call sync apps, website forms, or ad platforms.
* **Multi-Step Export Wizard**: 3-step export wizard (Select Fields -> Customize Columns -> Download XLSX).
* **WhatsApp Integration**: Quick `wa.me` chat button on lead forms.
* **Clean Code Structure**: Includes standard `.gitignore` for Python, Odoo, and IDE bytecode exclusion.

---

## 🏗️ Module Architecture

```
travel_crm/
├── .gitignore                    # Git ignore file for bytecode & IDE configs
├── __init__.py
├── __manifest__.py
├── controllers/
│   ├── __init__.py
│   └── main.py                   # Inbound Webhook API Endpoints
├── data/
│   ├── crm_team_data.xml         # Travel Desk Sales Team
│   ├── crm_stage_data.xml        # Custom Pipeline Stages
│   ├── mail_template_data.xml    # Email Templates (Acknowledgement, Booking Confirmed)
│   ├── automation_data.xml       # Automated Actions (Base Automation)
│   ├── travel_export_field_data.xml # Field Catalog for Export Wizard
│   └── demo_data.xml             # Sample Leads & Call Logs
├── models/
│   ├── __init__.py
│   ├── crm_lead.py               # Travel Lead Extension & AI Lead Summary
│   ├── res_config_settings.py    # Settings panel for Gemini & NVIDIA API Keys
│   ├── travel_call_log.py        # Call Logging & AI Coaching
│   ├── travel_destination.py     # Destination Master
│   ├── travel_export_wizard.py   # Multi-step XLSX Export Builder
│   └── travel_payment_installment.py # Payment Installment Tracking
├── security/
│   └── ir.model.access.csv       # Access Rights
└── views/
    ├── crm_dashboard_views.xml   # Funnel, Leaderboard, Follow-ups
    ├── crm_lead_views.xml        # Inherited Lead Form/Kanban/List Views
    ├── crm_menu_views.xml        # Travel Desk Navigation Menus
    ├── res_config_settings_views.xml # AI API Key Settings UI
    ├── travel_call_log_views.xml # Call Log Form/List/Pivot Views
    ├── travel_destination_views.xml # Destination Views
    ├── travel_export_wizard_views.xml # Export Wizard Modal
    └── travel_payment_views.xml  # Payment Installment Views
```

---

## ⚙️ Configuration & Settings

Navigate to **Travel Desk -> Configuration -> Settings**:
* **Gemini AI API Key** (`travel_crm.gemini_api_key`): Set your Google Gemini API Key for AI Lead Summaries.
* **NVIDIA AI API Key** (`travel_crm.nvidia_api_key`): Set your NVIDIA Llama API Key as secondary fallback.
* *Note*: If no API key is configured, clicking **Generate AI Summary** raises a friendly prompt instructing the user to configure keys in Settings.

---

## 🔄 Step-by-Step Lead Lifecycle & Workflow

### **Step 1: Lead Capture / Entry**
Leads enter the system through three main methods:
1. **Manual Entry**: Sales reps create an opportunity in the **Travel Desk** pipeline.
2. **Webhooks (`/travel_crm/api/lead`)**: Portal inquiries, Meta Lead Ads, or website contact forms push lead details via JSON payload.
3. **Inbound Call Sync (`/travel_crm/api/call_log`)**: Pushed by a mobile call-sync app; if the caller phone number is unknown, a new lead is automatically generated.

### **Step 2: Automated Initial Response**
* As soon as a lead is created with an email address assigned to the **Travel Desk**, an automated action triggers an **Acknowledgement Email** to the customer.
* Initial Call Disposition defaults to **Fresh Lead**.

### **Step 3: Qualification & Call Logging**
* The sales agent calls the customer and logs call details in **Calls & AI Coaching**.
* The call log records duration, SIM line used, call type (Incoming/Outgoing/Missed), call notes, and recording URLs.
* Disposition update:
  * **Call Back Later**: Automatically schedules a call activity for the next day.
  * **Interested**: Rep collects trip requirements (Destination, Package Type, Travel Dates, Adults/Children count).

### **Step 4: Itinerary Sharing & Automatic Stage Transition**
* Rep prepares the itinerary and clicks **Mark Itinerary as Shared**.
* The system automatically moves the opportunity stage to **Itinerary Shared** and schedules a **Follow-up Call Activity** for 2 days later.

### **Step 5: Negotiation & Booking Confirmation**
* Upon reaching an agreement, the rep updates the stage to **Booking Confirmed**.
* The system automatically:
  1. Sends a **Booking Confirmation Email** with trip details to the customer.
  2. Schedules a **Collect KYC / Travel Documents** activity due in 1 day.

### **Step 6: Documentation & Payments**
* Rep inputs Visa Status (`Pending`, `Submitted`, `Approved`, `Rejected`), KYC Status, and Insurance details.
* Package amount and payment installments are created under **Payment Summary**:
  * Down payments and installments are logged with due dates.
  * As payments are received, rep clicks **Mark Paid**.
  * A daily cron job (`_cron_flag_overdue`) automatically flags pending installments past their due date as **Overdue**.

### **Step 7: Trip Confirmed (Won)**
* Once documentation is complete and full payment is received, the lead is moved to **Trip Confirmed (Won)**.

---

## 📊 Models & Data Fields

### 1. `crm.lead` (Extended)
* `x_is_travel_lead` *(Boolean)*: Identifies if lead belongs to the Travel Desk team.
* `x_destination_id` *(Many2one)*: Link to `travel.destination`.
* `x_travel_date_from` / `x_travel_date_to` *(Date)*: Trip dates.
* `x_package_type` *(Selection)*: FIT, Group, Customized, Corporate, Honeymoon, Pilgrimage.
* `x_pax_adults`, `x_pax_children`, `x_pax_infants`, `x_total_pax` *(Computed)*.
* `x_visa_required`, `x_visa_status`, `x_kyc_status`, `x_travel_insurance`.
* `x_call_disposition` *(Selection)*: Fresh, RNR, Interested, Call Back Later, Not Interested, Converted.
* `x_booking_reference`, `x_itinerary_sent`, `x_itinerary_sent_date`.
* `x_amount_received`, `x_amount_pending` *(Monetary Computed)*.
* `x_call_log_ids` *(One2many `travel.call.log`)*.
* `x_installment_ids` *(One2many `travel.payment.installment`)*.
* `x_ai_lead_summary`, `x_ai_next_step`, `x_ai_generated_on`.

### 2. `res.config.settings` (Extended)
* `travel_gemini_api_key` *(Char)*: `travel_crm.gemini_api_key` parameter.
* `travel_nvidia_api_key` *(Char)*: `travel_crm.nvidia_api_key` parameter.

### 3. `travel.call.log`
* `caller_number`, `call_type` (`outgoing`, `incoming`, `missed`), `call_datetime`, `duration_seconds`.
* `sim_line` (`sim1`, `sim2`, `app`), `campaign_name`, `recording_url`, `note`.
* **AI Coaching Ratings**: `ai_rapport_score`, `ai_needs_discovery_score`, `ai_objection_handling_score`, `ai_closing_score`, `ai_overall_score` (Computed average).
* **AI Signals**: `ai_conversion_probability`, `ai_is_decision_maker`, `ai_sentiment`, `ai_feedback_good`, `ai_feedback_improve`.

### 4. `travel.payment.installment`
* `lead_id`, `name`, `amount`, `due_date`, `state` (`pending`, `paid`, `overdue`), `payment_date`, `payment_reference`.

### 5. `travel.destination`
* `name`, `country_id`, `state_id` (Many2one to `res.country.state` filtered by `country_id`), `is_domestic`, `active`.

---

## 🤖 Call Logging & AI Coaching ("Lead-IQ")

Each call record includes an **AI Coaching** panel inspired by TeleCRM's Lead-IQ feature:
* **Generate AI Score Button**: Executes heuristic/LLM analysis on call duration, disposition, and notes.
* **Metrics Tracked**:
  * Skill ratings (0-100) for Rapport, Needs Discovery, Objection Handling, and Closing.
  * Sentiment detection (Positive, Neutral, Negative).
  * Decision Maker identification.
  * Qualitative coaching points (*What Went Well*, *Could Improve*).

---

## ⚡ API & Inbound Webhooks

Configured with shared secret authentication via `X-Api-Key` header or `api_key` payload parameter (configured in System Parameters `travel_crm.api_key`).

### 1. Inbound Call Log (`POST /travel_crm/api/call_log`)
**Payload Example:**
```json
{
  "api_key": "YOUR_SECRET_KEY",
  "lead_phone": "+919876543210",
  "lead_name": "Rahul Sharma",
  "agent_email": "agent@example.com",
  "caller_number": "+919876543210",
  "call_type": "outgoing",
  "duration_seconds": 145,
  "sim_line": "sim1",
  "note": "Interested in Bali 5D4N package"
}
```

### 2. Generic Lead Capture (`POST /travel_crm/api/lead`)
**Payload Example:**
```json
{
  "api_key": "YOUR_SECRET_KEY",
  "name": "Europe Honeymoon Trip",
  "contact_name": "Priya Patel",
  "phone": "+919812345678",
  "email": "priya@example.com",
  "state": "Rajasthan",
  "city": "Jaipur",
  "source": "Google Ads",
  "description": "Looking for Switzerland & Paris package"
}
```

### 3. Meta (FB/Insta) Graph API Webhook (`GET` & `POST /travel_crm/api/meta/leadgen`)
- **GET (Verification Handshake)**: Handshakes with Meta app using `hub.mode`, `hub.verify_token`, `hub.challenge`.
- **POST (Lead Ingestion)**: Ingests `leadgen` real-time change notifications directly into `crm.lead`.

### 4. IndiaMART Lead Ingestion (`POST /travel_crm/api/indiamart`)
- **JSON Payload Example:**
```json
{
  "SENDER_NAME": "Pankaj Agarwal",
  "SENDER_MOBILE": "+919822334455",
  "SENDER_EMAIL": "pankaj@example.com",
  "QUERY_CITY": "Jaipur",
  "QUERY_STATE": "Rajasthan",
  "QUERY_PRODUCT_NAME": "Kerala Honeymoon Package",
  "QUERY_MESSAGE": "Looking for 6 Nights Kerala Tour"
}
```

### 5. JustDial Lead Ingestion (`POST /travel_crm/api/justdial`)
- **JSON Payload Example:**
```json
{
  "name": "Rohan Sharma",
  "mobile": "+919765432109",
  "email": "rohan@example.com",
  "city": "Mumbai",
  "state": "Maharashtra",
  "category": "Himachal Family Package",
  "description": "Need Manali & Shimla Tour"
}
```

---

## 📤 Export Activity Report Wizard

Accessible under **Travel Desk > Export Activity Report**:
1. **Step 1 (Select Fields)**: Filter by Date range, Team, Agent, and choose fields (Caller, Call Start, Duration, Disposition, Destination, Package Amount, etc.).
2. **Step 2 (Customize Columns)**: Drag & drop to reorder column sequence or rename header labels.
3. **Step 3 (Download)**: Generates and downloads a custom formatted `.xlsx` spreadsheet.

---

## ⚙️ Installation & Setup

1. Place `travel_crm` directory into your custom addons path.
2. Update App List in Odoo (`Settings > Activate Developer Mode > Apps > Update Apps List`).
3. Search for **Travel Agency CRM** and click **Install**.
4. Configure AI API Keys: Go to **Travel Desk -> Configuration -> Settings** and set **Gemini AI API Key** or **NVIDIA AI API Key**.
5. Configure Webhook Secret (Optional): Add `travel_crm.api_key` under `Settings > Technical > System Parameters`.

---
*Developed for Odoo 20.0*
