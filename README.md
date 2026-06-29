<h1 align="center">
  <br>
  🇪🇬 Egypt EconLens
  <br>
</h1>

<h4 align="center">A Comprehensive Economic Intelligence & Supply Chain Analytics Platform</h4>

<p align="center">
  <a href="#key-features">Key Features</a> •
  <a href="#how-it-works">How It Works</a> •
  <a href="#installation--local-setup">Installation</a> •
  <a href="#architecture--tech-stack">Architecture</a> •
  <a href="#team">Team</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white" alt="Flask">
  <img src="https://img.shields.io/badge/SQL%20Server-CC2927?style=for-the-badge&logo=microsoftsqlserver&logoColor=white" alt="SQL Server">
  <img src="https://img.shields.io/badge/Power%20BI-F2C811?style=for-the-badge&logo=powerbi&logoColor=black" alt="Power BI">
  <img src="https://img.shields.io/badge/Azure-0078D4?style=for-the-badge&logo=microsoftazure&logoColor=white" alt="Azure">
  <img src="https://img.shields.io/badge/Microsoft%20Fabric-742774?style=for-the-badge" alt="Fabric">
</p>

---

## 🌟 Overview

**Egypt EconLens** is an end-to-end Business Intelligence platform hosted on Microsoft Azure. It bridges the gap between raw economic data and decision-ready intelligence by deeply integrating trade flows, macroeconomic indicators, and supply-chain risk analytics into one unified analytical environment.

The platform features smooth view transitions, a natural-language AI Copilot, embedded Power BI dashboards, automated PDF report delivery via Power Automate, and a premium dark-mode UI — all built without any frontend frameworks.

---

## 🚀 Visual Showcase

<p align="center">
  <img src="test/Screenshot%202026-06-20%20233750.png" width="48%" alt="Web App Interface">
  <img src="test/reporttest1.png" width="48%" alt="Embedded Power BI Dashboard">
</p>
<p align="center">
  <img src="test/aitest1.png" width="48%" alt="AI Copilot Interface">
  <img src="test/aitest2.png" width="48%" alt="AI Insight and Charts">
</p>
<p align="center">
  <img src="test/pbixsend.png" width="48%" alt="Export and Share Modal">
  <img src="test/testemail1.png" width="48%" alt="Automated PDF Report via Email">
</p>

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 📊 **Embedded Power BI Reports** | Seamless integration of interactive PBIX dashboards and paginated RDL reports into a custom UI |
| 🤖 **AI Analytics Copilot** | Natural-language assistant that converts questions into validated SQL, generating insights, tables, and dynamic charts (Bar, Line, Area, Donut) |
| 📄 **Executive Chat Summarizer** | Export AI conversations as professional Q&A PDF briefs, delivered via email using Power Automate |
| ⚡ **Power Automate Integration** | Automated workflows for dashboard export, paginated PDF delivery, and daily subscriber alerts |
| 🌐 **View Transitions API** | Fluid, app-like page navigation without SPA framework overhead |
| 📱 **Mobile-First Responsive** | WhatsApp-style AI chat, swipeable bottom dock, and keyboard-aware inputs for a native mobile feel |
| 🔒 **SharePoint State Management** | Lightweight persistence for report versions and subscriber preferences |

---

## 💡 How We Bypassed the Power BI Embedded License Barrier

A major technical highlight — we enabled public report viewing without purchasing a dedicated Power BI Embedded capacity node:

1. Created a shared **Demo Microsoft Account**
2. Added the account as a **Guest user** to our university tenant via Azure AD
3. Granted the demo account **Viewer access** on the Fabric workspace
4. Activated the **Microsoft Fabric Trial** (60 days free) — enabling paginated RDL reports without Premium capacity
5. Integrated the demo account into our web app with a custom "Demo Account" modal for seamless visitor access

---

## 🏗️ Architecture & Tech Stack

```
┌─────────────────────────────────────────────────────────┐
│                     Azure App Service                    │
│  ┌───────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  Flask     │  │  Middleware   │  │  Templates       │  │
│  │  (app2.py) │  │  • prompt_   │  │  • index.html    │  │
│  │           │  │    builder   │  │  • about.html    │  │
│  │           │  │  • sql_      │  │  • guide.html    │  │
│  │           │  │    validator │  │                  │  │
│  │           │  │  • schema_   │  │  Static Assets   │  │
│  │           │  │    retriever │  │  • style.css     │  │
│  └─────┬─────┘  └──────┬───────┘  │  • mobile.css    │  │
│        │               │          └──────────────────┘  │
└────────┼───────────────┼────────────────────────────────┘
         │               │
    ┌────▼────┐   ┌──────▼──────┐   ┌──────────────┐
    │ SQL     │   │ OpenRouter  │   │ Power BI     │
    │ Server  │   │ (GPT-4     │   │ Service      │
    │ DWH     │   │  class)    │   │ (Fabric)     │
    └─────────┘   └─────────────┘   └──────────────┘
                                    ┌──────────────┐
                                    │ Power        │
                                    │ Automate     │
                                    │ + SharePoint │
                                    └──────────────┘
```

| Layer | Technologies |
|---|---|
| **Frontend** | HTML5, Custom CSS3 (View Transitions API), Vanilla JavaScript |
| **Backend** | Python 3.11, Flask |
| **Data Engineering** | SQL Server Data Warehouse, SSIS ETL Pipelines |
| **Reporting** | Microsoft Fabric, Power BI Service (PBIX & Paginated RDL) |
| **Automation** | Power Automate, SharePoint Lists |
| **AI & LLM** | OpenRouter API (GPT-4 class models) |
| **Cloud** | Azure App Service (Linux) |

---

## 💻 Installation & Local Setup

### 1. Prerequisites

- **Python 3.10+**
- **SQL Server & ODBC Driver 17**
- An **OpenRouter API Key** for the AI Copilot
- **Power Automate HTTP trigger URLs** (optional — for email automation)

### 2. Clone & Setup

```powershell
git clone https://github.com/moaaz311/FinalProjectAPP.git
cd FinalProjectAPP

# Create virtual environment
python -m venv .venv

# Activate (Windows)
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Environment Variables

Create a `.env` file in the root directory:

```env
# AI API
OPENROUTER_API_KEY=your_openrouter_api_key

# App Settings
HTTP_REFERER=http://localhost:5000
X_TITLE=EgyptTradeAI

# Database
SQL_SERVER=YOUR_SERVER_NAME
SQL_DATABASE=EgyptBI_DWH1

# Email (Flask-Mail)
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_app_password

# Power Automate
POWER_AUTOMATE_URL=your_power_automate_pdf_flow_url
SUBSCRIBE_FLOW_URL=your_subscribe_flow_url
UPDATE_SUBSCRIBERS_FILE=data/update_subscribers.json
SUBSCRIBERS_API_KEY=your_secret_key
```

> ⚠️ **CRITICAL:** Never commit your `.env` file! It is already in `.gitignore`.

### 5. Run

```powershell
python app2.py
```

Open **http://127.0.0.1:5000** — you'll be greeted by the premium EconLens UI.

---

## 📁 Project Structure

```
├── app2.py                  # Main Flask application
├── middleware/
│   ├── prompt_builder.py    # AI prompt engineering
│   ├── sql_validator.py     # SQL query validation & safety
│   └── schema_retriever.py  # Database schema context
├── knowledge/
│   ├── schema.json          # DWH schema definition
│   └── schema.txt           # Schema summary
├── templates/
│   ├── index.html           # Main dashboard (Power BI + AI Chat)
│   ├── about.html           # Team page
│   └── guide.html           # User guide
├── static/
│   ├── css/
│   │   ├── style.css        # Main styles
│   │   ├── mobile.css       # Mobile-responsive overrides
│   │   ├── about.css        # About page styles
│   │   └── guide.css        # Guide page styles
│   ├── img/                 # Assets (hero bg, icons, guide images)
│   └── profile/             # Team member profile photos
├── .github/workflows/       # Azure deployment CI/CD
├── requirements.txt
├── .env                     # Environment variables (gitignored)
└── .gitignore
```

---

## 🔒 Security & Deployment

- **Managed Identity** is used on Azure App Service — no hardcoded passwords in production
- **Environment Variables** for all secrets — never committed to source control
- **CI/CD** via GitHub Actions → Azure App Service (Linux)

---

## 👥 Team

This project was developed as a graduation project for the **ITI Business Intelligence Track 2026**.

<table>
  <tr>
    <td align="center">
      <a href="https://github.com/3bslam">
        <img src="static/profile/ayman.png" width="100px;" alt="Ayman"/><br />
        <sub><b>Ayman Abd Elsalam</b></sub>
      </a><br />
      <sub>Data Engineer & DWH Specialist</sub><br />
      <a href="https://www.linkedin.com/in/ayman-abd-elsalam-5b2131381/">
        <img src="https://img.shields.io/badge/-LinkedIn-0A66C2?style=flat&logo=linkedin&logoColor=white" alt="LinkedIn">
      </a>
    </td>
    <td align="center">
      <a href="https://github.com/shaimaahesham">
        <img src="static/profile/shaimaa.png" width="100px;" alt="Shaimaa"/><br />
        <sub><b>Shaimaa Hesham</b></sub>
      </a><br />
      <sub>BI & AI Solutions Developer</sub><br />
      <a href="https://www.linkedin.com/in/shaimaa-hesham/">
        <img src="https://img.shields.io/badge/-LinkedIn-0A66C2?style=flat&logo=linkedin&logoColor=white" alt="LinkedIn">
      </a>
    </td>
    <td align="center">
      <a href="https://github.com/mahmoud113647">
        <img src="static/profile/mahmoud.png" width="100px;" alt="Mahmoud"/><br />
        <sub><b>Mahmoud Reda</b></sub>
      </a><br />
      <sub>Power BI Developer</sub><br />
      <a href="https://www.linkedin.com/in/mahmoud-aboali-539130389/">
        <img src="https://img.shields.io/badge/-LinkedIn-0A66C2?style=flat&logo=linkedin&logoColor=white" alt="LinkedIn">
      </a>
    </td>
    <td align="center">
      <a href="https://github.com/emanemysalah3-ai">
        <img src="static/profile/eman.png" width="100px;" alt="Eman"/><br />
        <sub><b>Eman Salah</b></sub>
      </a><br />
      <sub>Power BI Developer</sub><br />
      <a href="https://www.linkedin.com/in/emansalahahmed/">
        <img src="https://img.shields.io/badge/-LinkedIn-0A66C2?style=flat&logo=linkedin&logoColor=white" alt="LinkedIn">
      </a>
    </td>
    <td align="center">
      <a href="https://www.linkedin.com/in/moaaz-achraf/">
        <img src="static/profile/moaz.png" width="100px;" alt="Moaaz"/><br />
        <sub><b>Moaaz Ashraf</b></sub>
      </a><br />
      <sub>Cloud, Automation & Platform Engineer</sub><br />
      <a href="https://www.linkedin.com/in/moaaz-achraf/">
        <img src="https://img.shields.io/badge/-LinkedIn-0A66C2?style=flat&logo=linkedin&logoColor=white" alt="LinkedIn">
      </a>
    </td>
  </tr>
</table>

<p align="center"><i>"Turning Data into Decisions"</i></p>

---

<p align="center">
  Made with ❤️ by the ITI BI 2026 Team
</p>
