<h1 align="center">
  <br>
  Egypt EconLens
  <br>
</h1>

<h4 align="center">A Comprehensive Economic Intelligence & Supply Chain Analytics Platform.</h4>

<p align="center">
  <a href="#key-features">Key Features</a> •
  <a href="#how-it-works">How It Works</a> •
  <a href="#installation--local-setup">Installation</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#credits">Credits</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/Flask-Web%20Framework-lightgrey.svg" alt="Flask">
  <img src="https://img.shields.io/badge/Database-SQL%20Server-red.svg" alt="SQL Server">
  <img src="https://img.shields.io/badge/Analytics-Power%20BI-yellow.svg" alt="Power BI">
  <img src="https://img.shields.io/badge/Cloud-Azure-blue.svg" alt="Azure">
</p>

---

## 🌟 Overview

**Egypt EconLens** is an end-to-end Business Intelligence platform hosted on Microsoft Azure. It bridges the gap between raw economic data and decision-ready intelligence. By deeply integrating trade flows, macroeconomic indicators, and supply-chain risk analytics, it provides an all-in-one unified analytical environment for executives and data analysts.

The platform is designed to look and feel like a modern, premium application, featuring smooth view transitions, dynamic AI capabilities, and embedded analytics.

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

- **📊 Embedded Power BI Reports**: Seamless integration of interactive PBIX dashboards and paginated RDL reports directly into a beautiful custom UI.
- **🤖 AI Analytics Copilot**: A natural-language AI assistant powered by advanced Prompt Engineering. It converts user questions into validated SQL queries, generating business insights, dynamic data tables, and `QuickChart` visualizations on the fly.
- **📄 Executive Chat Summarizer**: Instantly export your AI conversations as professional, Q&A formatted PDF executive briefs, securely delivered via email using Power Automate.
- **⚡ Power Automate Integration**: Automated workflows for exporting dashboards, delivering paginated PDF reports, and sending daily alerts to subscribers when data is modified.
- **🌐 Smooth Page Transitions**: Utilizing the modern View Transitions API to create a fluid, app-like navigation experience without the overhead of an SPA framework.
- **🔒 SharePoint State Management**: A lightweight persistence layer for tracking report versions and managing user subscriber preferences.

---

## 💡 How We Bypassed the Power BI Embedded License Barrier

A major technical highlight of this project is our workaround for the expensive Power BI Embedded capacity node, allowing public viewers to see reports without purchasing a dedicated node:
1. Created a shared **Demo Microsoft Account**.
2. Added the account as a **Guest user** to our university tenant via Azure Active Directory.
3. Granted the demo account Viewer access on the Fabric workspace.
4. Activated the **Microsoft Fabric Trial** (60 days free) and assigned it to the workspace—enabling paginated RDL reports to render correctly without Premium capacity.
5. Integrated the demo account into our Azure-hosted web app with a custom UI "Demo Account" modal to give visitors seamless access.

---

## 🏗️ Architecture & Tech Stack

- **Frontend:** HTML5, Custom CSS3 (with View Transitions API), Vanilla JavaScript
- **Backend Framework:** Python 3.11, Flask
- **Data Engineering:** SQL Server Data Warehouse, SSIS ETL Pipelines
- **Reporting:** Microsoft Fabric, Power BI Service (PBIX & Paginated RDL)
- **Automation:** Power Automate, SharePoint Lists
- **AI & LLM:** OpenRouter API (GPT-4 class models via API)
- **Cloud Hosting:** Azure App Service (Linux)

---

## 💻 Installation & Local Setup

To run Egypt EconLens on your local machine, follow these steps:

### 1. Prerequisites
- **Python 3.10+** installed on your system.
- **SQL Server & ODBC Driver 17** installed.
- An **OpenRouter API Key** for the AI Copilot.
- Your **Power Automate HTTP trigger URLs** (if testing email automation).

### 2. Clone and Setup Environment

Clone the repository and navigate to the project root, then create a virtual environment:

```powershell
# Create a virtual environment
python -m venv .venv

# Enable script execution (Windows only)
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# Activate the virtual environment
.\.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies

Install the required Python packages:

```powershell
python -m pip install --upgrade pip
python -m pip install flask flask-cors python-dotenv openai flask-mail reportlab pyodbc pandas requests numpy sqlalchemy cachetools
```

### 4. Environment Variables

Create a `.env` file in the root directory. You can use `.env.example` as a template (if available) or copy the variables below:

```env
# AI API
OPENROUTER_API_KEY=your_openrouter_api_key

# App Settings
HTTP_REFERER=http://localhost:5000
X_TITLE=EgyptTradeAI

# Database
SQL_SERVER=YOUR_SERVER_NAME
SQL_DATABASE=EgyptBI_DWH1
# Note: For local Windows Auth, SQL_USERNAME/PASSWORD can be omitted.

# Email Automation (Flask-Mail)
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_app_password

# Power Automate
POWER_AUTOMATE_URL=your_power_automate_pdf_flow_url
SUBSCRIBE_FLOW_URL=your_subscribe_flow_url
UPDATE_SUBSCRIBERS_FILE=data/update_subscribers.json
SUBSCRIBERS_API_KEY=your_secret_key_for_subscribers_endpoint
```

*(⚠️ **CRITICAL:** Do NOT upload your `.env` file to GitHub! Ensure it is in your `.gitignore`)*

### 5. Running the Application

Start the Flask development server:

```powershell
python app2.py
```

Open `http://127.0.0.1:5000` in your web browser. You will be greeted by the premium EconLens UI.

---

## 🔒 Security & Deployment Notes

- **Managed Identity:** The application uses Managed Identity when deployed to Azure App Service to access resources securely without hardcoded passwords.
- **Environment Variables:** Never commit `.env` or hardcode API keys in the source code.

---

## 🎓 Credits & License

This project was developed as an academic graduation project and portfolio piece for the **ITI Business Intelligence Track 2026**.

**Developed By:**
- Ayman Abd Elsalam
- Shaimaa Hesham
- Mahmoud Reda
- Eman Salah
- Moaaz Ashraf

*"Turning Data into Decisions"*
