from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from openai import OpenAI
from flask_mail import Mail

import hashlib
import html
import logging
import os
import re
import time
from urllib.parse import quote_plus

import numpy as np
import pandas as pd
import requests
from cachetools import TTLCache
from sqlalchemy import create_engine, text

# ── Middleware imports ───────────────────────────────────────────────────────
from middleware.sql_validator import validate_sql
from middleware.prompt_builder import (
    INTENT_SYSTEM,
    SQL_SYSTEM,
    SQL_REPAIR_SYSTEM,
    SUMMARY_SYSTEM,
    build_intent_prompt,
    build_sql_prompt,
    build_repair_prompt,
    build_summary_prompt,
)

# ======================
# LOAD ENV
# ======================

load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("egypt_trade_ai")

# ======================
# APP
# ======================

app = Flask(__name__)
CORS(app)

# ======================
# ENV
# ======================

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

HTTP_REFERER = os.getenv("HTTP_REFERER", "http://localhost:5000")
X_TITLE = os.getenv("X_TITLE", "EgyptTradeAI")

SQL_SERVER = os.getenv("SQL_SERVER")
SQL_DATABASE = os.getenv("SQL_DATABASE")

MAIL_USERNAME = os.getenv("MAIL_USERNAME")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")

POWER_AUTOMATE_URL = os.getenv("POWER_AUTOMATE_URL")

# Power Automate HTTP trigger that receives update-alert preferences
# and creates/updates rows in SharePoint List: ReportSubscribers.
SUBSCRIBE_FLOW_URL = os.getenv("SUBSCRIBE_FLOW_URL")

# ======================
# OPENROUTER
# ======================

client = None

try:
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY is missing in .env file")

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY
    )

except Exception as e:
    logger.warning("OpenRouter client initialization failed: %s", e)
    client = None

# ======================
# MAIL
# ======================

app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = MAIL_USERNAME
app.config["MAIL_PASSWORD"] = MAIL_PASSWORD

mail = Mail(app)

# ======================
# DATABASE
# ======================

try:
    if not SQL_SERVER or not SQL_DATABASE:
        raise ValueError("SQL_SERVER or SQL_DATABASE is missing in .env file")
        
    SQL_USERNAME = os.getenv("SQL_USERNAME")
    SQL_PASSWORD = os.getenv("SQL_PASSWORD")

    if SQL_USERNAME:
        # Remote connection (Microsoft Fabric / Azure SQL) using Managed Identity
        
        # Format server for Linux ODBC driver to prevent timeouts
        formatted_server = SQL_SERVER
        if not formatted_server.startswith("tcp:"):
            formatted_server = f"tcp:{formatted_server}"
        if "," not in formatted_server:
            formatted_server = f"{formatted_server},1433"
            
        connection_string = (
            "DRIVER={ODBC Driver 17 for SQL Server};"
            f"SERVER={formatted_server};"
            f"DATABASE={SQL_DATABASE};"
            "Authentication=ActiveDirectoryMsi;"
            "Encrypt=yes;"
            "TrustServerCertificate=no;"
        )
        engine = create_engine(
            f"mssql+pyodbc:///?odbc_connect={quote_plus(connection_string)}",
            pool_pre_ping=True,
            pool_recycle=3600
        )
    else:
        # Fallback to local Windows Authentication
        connection_string = (
            "DRIVER={ODBC Driver 17 for SQL Server};"
            f"SERVER={SQL_SERVER};"
            f"DATABASE={SQL_DATABASE};"
            "Trusted_Connection=yes;"
            "TrustServerCertificate=yes;"
        )
        engine = create_engine(
            f"mssql+pyodbc:///?odbc_connect={quote_plus(connection_string)}",
            pool_pre_ping=True,
            pool_recycle=3600
        )

    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

    logger.info("Database connected")
    db_error_msg = None

except Exception as e:
    logger.error("Database connection failed: %s", e)
    db_error_msg = f"Server: '{SQL_SERVER}' | DB: '{SQL_DATABASE}' | User: '{SQL_USERNAME}' | Exception: {str(e)}"
    engine = None

# ======================
# HOME
# ======================

@app.route("/")
def home():
    return render_template("index.html")

# ======================
# REPORTS
# ======================

REPORTS = [
    {
        "name": "Full_Light_Mode_PowerBI",
        "title": "Full Light Mode PowerBI Dashboard",
        "type": "PBIX",
        "format": "PBIR",
        "id": "fd74639c-26b8-4245-927c-f5e5f7bfa1e4",
        "url": "https://app.powerbi.com/reportEmbed?reportId=fd74639c-26b8-4245-927c-f5e5f7bfa1e4&autoAuth=true&ctid=ff4a48d6-4b5e-4fd3-8266-7eafc3e6e23e"
    },
    {
        # IMPORTANT: Power BI API returns this name with a trailing space.
        # Keep it exactly as-is so the existing Flow can match item()?['name'].
        "name": "Procurement Risk &Fraud Monitoring Report ",
        "title": "Procurement Risk &Fraud Monitoring Report",
        "type": "RDL",
        "format": "RDL",
        "id": "470349ed-7f49-494f-b62e-4c5325073e8e",
        "url": "https://app.powerbi.com/rdlEmbed?reportId=470349ed-7f49-494f-b62e-4c5325073e8e&groupId=9e1acf4e-e428-48a5-9f49-ca6c3bff92c3&autoAuth=true&ctid=ff4a48d6-4b5e-4fd3-8266-7eafc3e6e23e&experience=power-bi&rdl:parameterPanel=collapsed"
    },
    {
        "name": "Forecasting & Strategic Planning Report",
        "title": "Forecasting & Strategic Planning Report",
        "type": "RDL",
        "format": "RDL",
        "id": "f816875a-4fd8-44b9-a8f4-c22c536920d4",
        "url": "https://app.powerbi.com/rdlEmbed?reportId=f816875a-4fd8-44b9-a8f4-c22c536920d4&groupId=9e1acf4e-e428-48a5-9f49-ca6c3bff92c3&autoAuth=true&ctid=ff4a48d6-4b5e-4fd3-8266-7eafc3e6e23e&experience=power-bi&rdl:parameterPanel=collapsed"
    },
    {
        "name": "Executive Trade & Supply Chain Summary",
        "title": "Executive Trade & Supply Chain Summary",
        "type": "RDL",
        "format": "RDL",
        "id": "23b137ec-dc44-4de8-ba30-93eca6c0631e",
        "url": "https://app.powerbi.com/rdlEmbed?reportId=23b137ec-dc44-4de8-ba30-93eca6c0631e&groupId=9e1acf4e-e428-48a5-9f49-ca6c3bff92c3&autoAuth=true&ctid=ff4a48d6-4b5e-4fd3-8266-7eafc3e6e23e&experience=power-bi&rdl:parameterPanel=collapsed"
    },
    {
        "name": "Supply Chain Operations Performance",
        "title": "Supply Chain Operations Performance",
        "type": "RDL",
        "format": "RDL",
        "id": "f4757103-3ab4-44c7-af32-399a2e4129da",
        "url": "https://app.powerbi.com/rdlEmbed?reportId=f4757103-3ab4-44c7-af32-399a2e4129da&groupId=9e1acf4e-e428-48a5-9f49-ca6c3bff92c3&autoAuth=true&ctid=ff4a48d6-4b5e-4fd3-8266-7eafc3e6e23e&experience=power-bi&rdl:parameterPanel=collapsed"
    },
    {
        "name": "Macro Currency & Cost Exposure",
        "title": "Macro Currency & Cost Exposure",
        "type": "RDL",
        "format": "RDL",
        "id": "5e2f5bc7-5fc9-4119-8d58-04162bb2a3da",
        "url": "https://app.powerbi.com/rdlEmbed?reportId=5e2f5bc7-5fc9-4119-8d58-04162bb2a3da&groupId=9e1acf4e-e428-48a5-9f49-ca6c3bff92c3&autoAuth=true&ctid=ff4a48d6-4b5e-4fd3-8266-7eafc3e6e23e&experience=power-bi&rdl:parameterPanel=collapsed"
    },
    {
        "name": "Trade Partners",
        "title": "Trade Partners",
        "type": "RDL",
        "format": "RDL",
        "id": "c4753a9e-52ac-41e3-8b4b-fd72cdf79f50",
        "url": "https://app.powerbi.com/rdlEmbed?reportId=c4753a9e-52ac-41e3-8b4b-fd72cdf79f50&autoAuth=true&ctid=ff4a48d6-4b5e-4fd3-8266-7eafc3e6e23e&experience=power-bi&clientSideAuth=0"
    }
]

VALID_REPORTS = [report["name"] for report in REPORTS]
REPORT_BY_NAME = {report["name"]: report for report in REPORTS}
REPORT_BY_ID = {report["id"]: report for report in REPORTS}
REPORT_TITLES = {report["name"]: report.get("title", report["name"]) for report in REPORTS}

# Backward compatibility for cached/older front-end values.
# Values here map any old UI/report names to the exact names returned by the Power BI API.
REPORT_ALIASES = {
    "Reportv1": "Procurement Risk &Fraud Monitoring Report ",
    "report2": "Forecasting & Strategic Planning Report",
    "report1perfectwidth": "Executive Trade & Supply Chain Summary",
    "Executive_Trade_Supply_Chain_Summary_Report": "Executive Trade & Supply Chain Summary",
    "Executive Trade & Supply Chain Summary Report": "Executive Trade & Supply Chain Summary",
    "Executive Trade & Supply Chain Summary": "Executive Trade & Supply Chain Summary",
    "Procurement_Risk_Fraud_Monitoring_Report": "Procurement Risk &Fraud Monitoring Report ",
    "Procurement Risk &Fraud Monitoring Report": "Procurement Risk &Fraud Monitoring Report ",
    "Procurement Risk &Fraud Monitoring Report ": "Procurement Risk &Fraud Monitoring Report ",
    "Forecasting_Strategic_Planning_Report": "Forecasting & Strategic Planning Report",
    "Forecasting & Strategic Planning_Report": "Forecasting & Strategic Planning Report",
    "Forecasting & Strategic Planning Report": "Forecasting & Strategic Planning Report",
    "Full Light Mode PowerBI Dashboard": "Full_Light_Mode_PowerBI",
    "Full_Light_Mode_PowerBI": "Full_Light_Mode_PowerBI",
    "Supply Chain Operations": "Supply Chain Operations Performance",
    "Supply Chain Operations Performance": "Supply Chain Operations Performance",
    "Supply_Chain_Operations_Performance": "Supply Chain Operations Performance",
    "Macro Currency & Cost Exposure": "Macro Currency & Cost Exposure",
    "Macro Currency Cost Exposure": "Macro Currency & Cost Exposure",
    "Macro_Currency_Cost_Exposure": "Macro Currency & Cost Exposure",
    "Trade Partners": "Trade Partners",
    "Trade_Partners": "Trade Partners",
    "Trade Balance by Partner": "Trade Partners",
}

# Normalize/repair RDL parameter names and internal values.
# Power BI export expects internal parameter names/values, not UI labels.
FORECASTING_REPORT_ID = "f816875a-4fd8-44b9-a8f4-c22c536920d4"
FORECASTING_REPORT_NAME = "Forecasting & Strategic Planning Report"

PROCUREMENT_REPORT_ID = "470349ed-7f49-494f-b62e-4c5325073e8e"
PROCUREMENT_REPORT_NAME = "Procurement Risk &Fraud Monitoring Report "

EXECUTIVE_REPORT_ID = "23b137ec-dc44-4de8-ba30-93eca6c0631e"
EXECUTIVE_REPORT_NAME = "Executive Trade & Supply Chain Summary"

SUPPLY_OPS_REPORT_ID = "f4757103-3ab4-44c7-af32-399a2e4129da"
SUPPLY_OPS_REPORT_NAME = "Supply Chain Operations Performance"

MACRO_REPORT_ID = "5e2f5bc7-5fc9-4119-8d58-04162bb2a3da"
MACRO_REPORT_NAME = "Macro Currency & Cost Exposure"

TRADE_PARTNERS_REPORT_ID = "c4753a9e-52ac-41e3-8b4b-fd72cdf79f50"
TRADE_PARTNERS_REPORT_NAME = "Trade Partners"

FORECASTING_PARAMETER_ALIASES = {
    "ReportParameter1": "ForecastScenario",
    "ForecastScenario": "ForecastScenario",
    "ForecastBaseYear": "ForecastBaseYear",
    "ForecastHorizonYears": "ForecastHorizonYears",
}

FORECAST_SCENARIO_VALUE_MAP = {
    "Base Scenario": "Base",
    "Optimistic Scenario": "Optimistic",
    "Stress Scenario": "Stress",
    "Base": "Base",
    "Optimistic": "Optimistic",
    "Stress": "Stress",
}

FORECAST_HORIZON_VALUE_MAP = {
    "Next 1 Year": "1",
    "Next 2 Years": "2",
    "Next 3 Years": "3",
    "1": "1",
    "2": "2",
    "3": "3",
    1: "1",
    2: "2",
    3: "3",
}

PROCUREMENT_PARAMETER_ALIASES = {
    "Year": "Year",
    "Month": "Month",
    "ProcurementYear": "Year",
    "ProcurementMonth": "Month",
}

EXECUTIVE_PARAMETER_ALIASES = {
    "Year": "Year",
    "Country": "Country",
    "ExecutiveYear": "Year",
    "ExecutiveCountry": "Country",
}

SUPPLY_OPS_PARAMETER_ALIASES = {
    "Year": "Year",
    "Month": "Month",
    "SupplyYear": "Year",
    "SupplyMonth": "Month",
    "OperationsYear": "Year",
    "OperationsMonth": "Month",
}

MACRO_PARAMETER_ALIASES = {
    "MacroYear": "MacroYear",
    "Year": "MacroYear",
    "Macro_Year": "MacroYear",
}

TRADE_PARTNERS_PARAMETER_ALIASES = {
    "P_year": "P_year",
    "P_Country": "P_Country",
    "Year": "P_year",
    "Country": "P_Country",
    "TradePartnerYear": "P_year",
    "TradePartnerCountry": "P_Country",
}


SUPPLY_OPS_MONTH_VALUE_MAP = {
    "Jan": "1", "January": "1", "01 - January": "1", "1": "1", "01": "1", 1: "1",
    "Feb": "2", "February": "2", "02 - February": "2", "2": "2", "02": "2", 2: "2",
    "Mar": "3", "March": "3", "03 - March": "3", "3": "3", "03": "3", 3: "3",
    "Apr": "4", "April": "4", "04 - April": "4", "4": "4", "04": "4", 4: "4",
    "May": "5", "05 - May": "5", "5": "5", "05": "5", 5: "5",
    "Jun": "6", "June": "6", "06 - June": "6", "6": "6", "06": "6", 6: "6",
    "Jul": "7", "July": "7", "07 - July": "7", "7": "7", "07": "7", 7: "7",
    "Aug": "8", "August": "8", "08 - August": "8", "8": "8", "08": "8", 8: "8",
    "Sep": "9", "September": "9", "09 - September": "9", "9": "9", "09": "9", 9: "9",
    "Oct": "10", "October": "10", "10 - October": "10", "10": "10", 10: "10",
    "Nov": "11", "November": "11", "11 - November": "11", "11": "11", 11: "11",
    "Dec": "12", "December": "12", "12 - December": "12", "12": "12", 12: "12",
}


def _normalize_simple_parameters(parameter_values, aliases: dict[str, str]) -> list:
    """Normalize basic RDL parameters while preserving the selected order.

    Multi-value paginated report parameters are represented as repeated
    name/value entries. This function also accepts a list in the value field
    and expands it into repeated entries for safety.
    """
    if not isinstance(parameter_values, list):
        return []

    normalized = []
    for parameter in parameter_values:
        if not isinstance(parameter, dict):
            continue

        raw_name = str(parameter.get("name", "")).strip()
        name = aliases.get(raw_name, raw_name)
        raw_value = parameter.get("value", "")

        if not name:
            continue

        values = raw_value if isinstance(raw_value, list) else [raw_value]

        for value in values:
            value = str(value).strip()
            if value == "":
                continue

            normalized.append({
                "name": name,
                "value": value
            })

    return normalized


def _normalize_forecasting_parameters(parameter_values):
    """Return Power BI export-ready parameter values for the Forecasting RDL."""
    if not isinstance(parameter_values, list):
        return []

    normalized = []
    for parameter in parameter_values:
        if not isinstance(parameter, dict):
            continue

        raw_name = str(parameter.get("name", "")).strip()
        name = FORECASTING_PARAMETER_ALIASES.get(raw_name, raw_name)
        value = parameter.get("value", "")

        if name == "ForecastScenario":
            value = FORECAST_SCENARIO_VALUE_MAP.get(value, value)
        elif name == "ForecastHorizonYears":
            value = FORECAST_HORIZON_VALUE_MAP.get(value, value)
        elif name == "ForecastBaseYear":
            value = str(value).strip()

        value = str(value).strip()
        if not name or value == "":
            continue

        normalized.append({
            "name": name,
            "value": value
        })

    return normalized


def _normalize_procurement_parameters(parameter_values):
    """Return Power BI export-ready Year/Month values for the Procurement RDL."""
    return _normalize_simple_parameters(parameter_values, PROCUREMENT_PARAMETER_ALIASES)


def _normalize_executive_parameters(parameter_values):
    """Return Power BI export-ready Year/Country values for the Executive RDL."""
    return _normalize_simple_parameters(parameter_values, EXECUTIVE_PARAMETER_ALIASES)


def _normalize_supply_ops_parameters(parameter_values):
    """Return Power BI export-ready Year/Month values for Supply Chain Operations Performance.

    The RDL shows month labels such as Jan/Feb, but the export API expects
    the internal numeric Month values. This also repairs cached old front-end
    payloads that still send text month labels.
    """
    normalized = _normalize_simple_parameters(parameter_values, SUPPLY_OPS_PARAMETER_ALIASES)
    for parameter in normalized:
        if parameter.get("name") == "Month":
            raw_value = parameter.get("value", "")
            parameter["value"] = SUPPLY_OPS_MONTH_VALUE_MAP.get(raw_value, str(raw_value).strip())
    return normalized


def _normalize_macro_parameters(parameter_values):
    """Return Power BI export-ready MacroYear values for Macro Currency & Cost Exposure."""
    return _normalize_simple_parameters(parameter_values, MACRO_PARAMETER_ALIASES)


def _normalize_trade_partners_parameters(parameter_values):
    """Return Power BI export-ready P_year/P_Country values for Trade Partners."""
    return _normalize_simple_parameters(parameter_values, TRADE_PARTNERS_PARAMETER_ALIASES)


def _normalize_report_parameters(report_name: str, report_id: str, parameter_values: list) -> list:
    if report_name == FORECASTING_REPORT_NAME or report_id == FORECASTING_REPORT_ID:
        return _normalize_forecasting_parameters(parameter_values)
    if report_name == PROCUREMENT_REPORT_NAME or report_id == PROCUREMENT_REPORT_ID:
        return _normalize_procurement_parameters(parameter_values)
    if report_name == EXECUTIVE_REPORT_NAME or report_id == EXECUTIVE_REPORT_ID:
        return _normalize_executive_parameters(parameter_values)
    if report_name == SUPPLY_OPS_REPORT_NAME or report_id == SUPPLY_OPS_REPORT_ID:
        return _normalize_supply_ops_parameters(parameter_values)
    if report_name == MACRO_REPORT_NAME or report_id == MACRO_REPORT_ID:
        return _normalize_macro_parameters(parameter_values)
    if report_name == TRADE_PARTNERS_REPORT_NAME or report_id == TRADE_PARTNERS_REPORT_ID:
        return _normalize_trade_partners_parameters(parameter_values)
    return parameter_values if isinstance(parameter_values, list) else []

# ======================
# CHAT PIPELINE CONFIG
# ======================

_INTENT_MODEL = "openai/gpt-4.1-nano"
_SQL_MODEL = "openai/gpt-4.1-mini"
_REPAIR_MODEL = "openai/gpt-4.1-mini"
_SUMMARY_MODEL = "openai/gpt-4.1-nano"

_MAX_RETRIES = int(os.getenv("MAX_RETRIES", 1))
_CACHE_TTL = int(os.getenv("CACHE_TTL", 300))

_cache: TTLCache = TTLCache(maxsize=500, ttl=_CACHE_TTL)

_SESSION_TTL = int(os.getenv("SESSION_TTL", 1800))
_sessions: TTLCache = TTLCache(maxsize=1000, ttl=_SESSION_TTL)

_SMALL_TALK = {
    "hi": "👋 Hi! I'm your Egypt Trade AI Assistant.",
    "hello": "👋 Hello! I'm your Egypt Trade AI Assistant.",
    "hey": "👋 Hey! Ready to explore your BI data.",
    "how are you": "😊 I'm doing great and ready to analyze your BI data.",
    "who are you": "🤖 I'm your AI BI Assistant connected to EgyptBI_DWH1.",
    "what can you do": (
        "📊 I can:\n\n"
        "• Analyze trade data\n"
        "• Explore countries\n"
        "• Analyze commodities\n"
        "• Generate BI insights\n"
        "• Analyze supply chain KPIs"
    ),
    "thanks": "😊 You're welcome!",
    "thank you": "😊 Happy to help!"
}

# ======================
# HELPERS
# ======================

def _clean_sql(raw: str) -> str:
    """Strip markdown fences from model output."""
    return (
        raw.replace("```sql", "")
           .replace("```tsql", "")
           .replace("```", "")
           .strip()
    )
def _looks_like_sql_query(text_value: str) -> bool:
    q = (text_value or "").strip().lower()

    return (
        q.startswith("select ")
        or q.startswith("with ")
    )


def _hash_text(value: str) -> str:
    """Return a short hash for safe logs without exposing the raw value."""
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()[:12]


def _safe_log_sql(event: str, sql: str, **fields) -> None:
    """Log SQL metadata only; never print raw SQL, emails, or secrets."""
    safe_fields = {
        "sql_hash": _hash_text(sql),
        "sql_length": len(sql or ""),
        **fields,
    }
    logger.info("%s | %s", event, safe_fields)


def _get_session_id(data: dict) -> str:
    """Resolve a stable session key for follow-up question memory."""
    raw_session = (
        data.get("session_id")
        or data.get("conversation_id")
        or request.headers.get("X-Session-ID")
        or f"{request.remote_addr}:{request.headers.get('User-Agent', '')}"
    )
    return hashlib.sha256(str(raw_session).encode("utf-8")).hexdigest()[:24]


_FOLLOW_UP_RE = re.compile(
    r"\b(same|again|previous|last|that|it|those|them|what about|compare with|for\s+\d{4}|in\s+\d{4})\b",
    re.IGNORECASE,
)
_ARABIC_FOLLOW_UP_HINTS = (
    "نفس", "زي", "السابق", "اللي فات", "الماضي", "كمان", "برضو",
    "طب", "طيب", "ماذا عن", "قارن", "لسنة", "للسنة", "سنة", "في 20", "لـ20"
)


def _is_follow_up_question(question: str) -> bool:
    q = (question or "").strip().lower()
    if not q:
        return False

    if _FOLLOW_UP_RE.search(q):
        return True

    if _contains_arabic(question) and any(hint in q for hint in _ARABIC_FOLLOW_UP_HINTS):
        return True

    # Very short questions with a year are usually follow-ups, e.g. "2025?".
    if len(q.split()) <= 5 and re.search(r"\b20\d{2}\b", q):
        return True

    return False


def _hydrate_follow_up_question(session_id: str, original_question: str, question: str) -> str:
    """Turn follow-up wording into a context-aware standalone BI request."""
    memory = _sessions.get(session_id)

    if not memory or not _is_follow_up_question(original_question):
        return question

    return f"""
Current follow-up question: {question}

Previous user question: {memory.get('original_question', '')}
Previous resolved BI question: {memory.get('resolved_question', '')}
Previous intent: {memory.get('intent', '')}
Previous SQL: {memory.get('sql', '')}

Resolve the current follow-up as a standalone BI question. Preserve the previous domain, metric, grouping, and filters unless the current question explicitly changes them.
""".strip()


def _remember_conversation(
    session_id: str,
    original_question: str,
    resolved_question: str,
    intent: str,
    sql: str,
    records: list[dict] | None = None,
    chart: dict | None = None,
) -> None:
    """Store the last successful analytical turn for follow-up questions."""
    if not session_id or not sql:
        return

    _sessions[session_id] = {
        "original_question": original_question,
        "resolved_question": resolved_question,
        "intent": intent,
        "sql": sql,
        "records_sample": (records or [])[:5],
        "chart": chart or {},
        "saved_at": time.time(),
    }

# ======================
# ARABIC QUESTION NORMALIZATION
# ======================

def _contains_arabic(text: str) -> bool:
    """Return True when the user question contains Arabic characters."""
    return bool(re.search(r"[\u0600-\u06FF]", text or ""))


def _normalise_arabic_text(text: str) -> str:
    """
    Normalise Arabic text so common spellings map to the same keywords.
    This helps the English SQL-generation prompt understand Arabic user questions.
    """
    text = text or ""

    # Remove Arabic diacritics and tatweel
    text = re.sub(r"[\u064B-\u0652]", "", text)
    text = text.replace("ـ", "")

    replacements = {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ة": "ه",
        "ى": "ي",
        "ؤ": "و",
        "ئ": "ي",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return re.sub(r"\s+", " ", text).strip().lower()


def normalise_question_for_ai(question: str) -> str:
    """
    Convert common Arabic BI questions into canonical English questions.
    The database schema/prompt examples are English, so this prevents Arabic
    questions from being incorrectly classified as unavailable data.
    """
    if not _contains_arabic(question):
        return question

    q = _normalise_arabic_text(question)

    # Products with late shipping/delivery delay
    if (
        any(word in q for word in ["منتج", "المنتج", "المنتجات", "منتجات"])
        and any(word in q for word in ["تاخير", "متاخر", "متاخره", "متاخرين", "الاكبر تاخير", "اكبر تاخير"])
        and any(word in q for word in ["شحن", "الشحن", "تسليم", "التسليم", "توصيل", "التوصيل"])
    ):
        return "Which products have the highest late delivery rate?"

    # Shipping delays without explicitly saying products
    if (
        any(word in q for word in ["تاخير", "متاخر", "متاخره", "متاخرين"])
        and any(word in q for word in ["شحن", "الشحن", "تسليم", "التسليم", "توصيل", "التوصيل"])
    ):
        return "Which products have the highest late delivery rate?"

    # Top selling / highest sales products
    if (
        any(word in q for word in ["منتج", "المنتج", "المنتجات", "منتجات"])
        and any(word in q for word in ["مبيعات", "مبيعا", "مبيعاً", "الاكثر مبيعا", "اكثر مبيعا", "اعلي مبيعات", "اعلى مبيعات"])
    ):
        return "Which products have the highest sales?"

    # Top countries by trade value
    if (
        any(word in q for word in ["دول", "الدول", "بلدان", "البلدان", "دوله", "الدوله"])
        and any(word in q for word in ["تجاره", "التجاره", "تجارة", "قيمة", "قيمه", "صادرات", "واردات"])
    ):
        return "What are the top countries by trade value?"

    # Exports/imports comparison
    if (
        any(word in q for word in ["صادرات", "الصادرات", "واردات", "الواردات"])
        and any(word in q for word in ["قارن", "مقارنه", "مقارنة", "مقارنه بين", "مقارنة بين"])
    ):
        return "Compare exports and imports by year."

    # GDP growth questions
    if (
        any(word in q for word in ["نمو", "النمو"])
        and any(word in q for word in ["الناتج المحلي", "الناتج المحلى", "gdp"])
    ):
        return f"{question}\n\nTranslate this Arabic question to English first, then answer using the available schema."

    # Generic Arabic fallback
    return f"{question}\n\nTranslate this Arabic question to English first, then answer using the available schema."




# ======================
# UPDATE SUBSCRIPTION HELPERS
# ======================

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalise_email(email: str) -> str:
    return (email or "").strip().lower()


def _llm(system: str, user: str, model: str, max_tokens: int = 600) -> str:
    """Single wrapper for all LLM calls through OpenRouter."""
    if client is None:
        raise RuntimeError("OpenRouter client is not available. Check OPENROUTER_API_KEY in .env.")

    response = client.chat.completions.create(
        model=model,
        temperature=0.0,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        extra_headers={
            "HTTP-Referer": HTTP_REFERER,
            "X-Title": X_TITLE,
        },
    )

    return response.choices[0].message.content.strip()


_ARABIC_TRANSLATION_SYSTEM = """
You translate Arabic business-intelligence questions into one clear English BI question.
Return ONLY the translated English question.
Preserve numbers, years, countries, products, SQL/business terms, and metric intent.
Do not answer the question and do not generate SQL.
""".strip()


def translate_arabic_question_for_ai(original_question: str, fallback_question: str) -> str:
    """Dedicated Arabic → English step before intent detection."""
    if not _contains_arabic(original_question):
        return fallback_question

    prompt = f"""
Arabic user question:
{original_question}

Fallback canonical meaning if useful:
{fallback_question}
""".strip()

    try:
        translated = _llm(
            _ARABIC_TRANSLATION_SYSTEM,
            prompt,
            _INTENT_MODEL,
            max_tokens=120,
        ).strip()

        if translated:
            logger.info(
                "Arabic question translated | %s",
                {
                    "original_hash": _hash_text(original_question),
                    "translated_hash": _hash_text(translated),
                },
            )
            return translated

    except Exception as exc:
        logger.warning("Arabic translation step failed; using fallback normalization: %s", exc)

    return fallback_question


def clean_label(col_name: str) -> str:
    """Convert snake_case database columns into clean UI labels."""
    label = str(col_name).replace("_", " ").title()

    replacements = {
        "Usd": "USD",
        "Egp": "EGP",
        "Gdp": "GDP",
        "Kpi": "KPI",
        "Hs": "HS",
        "Id": "ID",
        "Pct": "%",
    }

    for old, new in replacements.items():
        label = label.replace(old, new)

    return label


def _is_year_col(col_name: str) -> bool:
    return col_name.lower() in {"year", "trade_year", "order_year", "date_year"}


def _is_time_col(col_name: str) -> bool:
    c = col_name.lower()
    return c in {"year", "trade_year", "month", "quarter", "date", "order_date"} or c.endswith("_year")


def _is_key_col(col_name: str) -> bool:
    c = col_name.lower()
    return c.endswith("_key") or c.endswith("_id") or c in {"key", "id"}


def _is_internal_display_col(col_name: str) -> bool:
    c = col_name.lower()

    return (
        c.endswith("_key")
        or c.endswith("_id")
        or c in {"key", "id", "is_strategic"}
    )


def _is_measure_col(col_name: str) -> bool:
    c = col_name.lower()

    not_metric_cols = {
        "commodity_key",
        "country_key",
        "date_key",
        "product_key",
        "trade_key",
        "order_key",
        "customer_key",
        "hs_code",
        "is_strategic",
        "year",
        "trade_year",
        "month",
        "quarter",
    }

    measure_hints = (
        "value", "usd", "egp", "sales", "profit", "gdp", "reserve",
        "pct", "percent", "rate", "days", "delay", "growth",
        "inflation", "avg", "average", "total", "cost", "volume",
        "amount", "quantity", "count", "revenue", "balance"
    )

    if c in not_metric_cols:
        return False

    if _is_key_col(c):
        return False

    return any(h in c for h in measure_hints)


def format_metric(value, col_name: str) -> str:
    c = col_name.lower()

    try:
        value = float(value)
    except Exception:
        return html.escape(str(value))

    # Never format years/codes/flags as money
    if c in {"year", "trade_year", "month", "quarter", "hs_code", "is_strategic"}:
        if value.is_integer():
            return str(int(value))
        return str(value)

    # Percent / rate
    if any(x in c for x in ["pct", "percent", "rate", "growth", "inflation"]):
        return f"{value:.2f}%"

    # Days / delays
    if "days" in c or "delay" in c:
        return f"{value:.1f} days"

    # EGP money
    if "egp" in c:
        sign = "-" if value < 0 else ""
        abs_value = abs(value)

        if abs_value >= 1_000_000_000:
            return f"{sign}EGP {abs_value / 1_000_000_000:.2f}B"
        elif abs_value >= 1_000_000:
            return f"{sign}EGP {abs_value / 1_000_000:.2f}M"
        elif abs_value >= 1_000:
            return f"{sign}EGP {abs_value / 1_000:.2f}K"
        return f"{sign}EGP {abs_value:,.2f}"

    # USD / trade money
    money_keywords = [
        "usd",
        "sales",
        "profit",
        "revenue",
        "trade_value",
        "cost",
        "value",
        "amount",
        "export",
        "exports",
        "import",
        "imports",
        "trade_balance",
        "balance",
        "total_trade",
        "total_exports",
        "total_imports"
    ]

    if any(x in c for x in money_keywords):
        sign = "-" if value < 0 else ""
        abs_value = abs(value)

        if abs_value >= 1_000_000_000:
            return f"{sign}${abs_value / 1_000_000_000:.2f}B"
        elif abs_value >= 1_000_000:
            return f"{sign}${abs_value / 1_000_000:.2f}M"
        elif abs_value >= 1_000:
            return f"{sign}${abs_value / 1_000:.2f}K"
        return f"{sign}${abs_value:,.2f}"

    # Generic number
    if value.is_integer():
        return f"{int(value):,}"

    return f"{value:,.2f}"
def build_formatted_table(source_df: pd.DataFrame, display_cols: list[str], add_rank: bool = False) -> str:
    table_df = source_df[display_cols].copy()

    rename_map = {
        col: clean_label(col)
        for col in display_cols
    }

    table_df = table_df.rename(columns=rename_map)

    if add_rank:
        table_df.insert(0, "Rank", range(1, len(table_df) + 1))

    formatters = {}

    for original_col in display_cols:
        display_col = rename_map[original_col]
        col_lower = original_col.lower()

        should_format = any(keyword in col_lower for keyword in [
            "usd", "egp", "value", "sales", "profit", "revenue",
            "cost", "amount", "total", "avg", "pct", "percent",
            "rate", "growth", "inflation", "days", "delay",
            "export", "exports", "import", "imports",
            "balance", "trade_balance"
        ])

        should_not_format = (
            col_lower in {"year", "trade_year", "hs_code", "is_strategic"}
            or col_lower.endswith("_key")
            or col_lower.endswith("_id")
        )

        if should_format and not should_not_format:
            formatters[display_col] = (
                lambda value, col=original_col: format_metric(value, col)
            )

    return table_df.to_html(
        classes="ai-result-table",
        index=False,
        border=0,
        escape=True,
        formatters=formatters
    )
def _detect_result_type(question: str, df: pd.DataFrame, metric_col: str | None) -> str:
    q = question.lower()
    columns = {c.lower() for c in df.columns}

    time_keywords = ("year", "yearly", "annual", "trend", "over time", "monthly", "quarterly")
    ranking_keywords = (
        "top", "highest", "largest", "most", "lowest", "smallest", "least",
        "best", "worst", "rank", "ranking"
    )

    has_time_col = any(_is_time_col(c) for c in columns)

    if has_time_col or any(k in q for k in time_keywords):
        return "trend"

    if metric_col is None:
        return "list"

    if len(df) > 1 and any(k in q for k in ranking_keywords):
        return "ranking"

    if len(df) > 1 and metric_col is not None:
        return "ranking"

    return "kpi"


def _table_title(question: str, metric_col: str | None, result_type: str, row_count: int) -> str:
    q = question.lower()
    metric_name = (metric_col or "").lower()

    if result_type == "trend":
        return "Trend Results"

    if result_type == "list":
        return "Result Details"

    if "delay" in metric_name or "days" in metric_name or "shipping" in q:
        return "Highest Delay Products"

    if "profit" in metric_name:
        return "Top Profit Results"

    if "sales" in metric_name or "revenue" in metric_name:
        return "Top Revenue Results"

    if "trade" in metric_name or "value" in metric_name or "usd" in metric_name:
        return f"Top {row_count} Results"

    return f"Top {row_count} Results"


def build_ai_answer(df: pd.DataFrame, summary: str, question: str = "") -> str:
    """
    Builds the final HTML answer shown inside the chatbot.

    Logic:
    - Trend results: show a trend table, not a misleading KPI.
    - Ranking results: show the top KPI + ranked table.
    - List/descriptive results: show a clean table.
    - Single KPI result: show KPI card only.
    - Never treat keys, IDs, HS codes, years, or flags as money.
    - Show a real text label for KPI/ranking results when available.
    """
    numeric_cols = df.select_dtypes(include=["number"]).columns

    metric_col = next(
        (c for c in numeric_cols if _is_measure_col(c)),
        None
    )

    non_numeric = [c for c in df.columns if c not in numeric_cols]
    label_col = non_numeric[0] if non_numeric else df.columns[0]

    display_cols = [
        c for c in df.columns
        if not _is_internal_display_col(c)
    ]

    if not display_cols:
        display_cols = list(df.columns)

    result_type = _detect_result_type(question, df, metric_col)
    table_title = _table_title(question, metric_col, result_type, len(df))

    # ======================
    # CASE 1: TIME SERIES / TREND
    # ======================
    if result_type == "trend":
        table_html = build_formatted_table(df, display_cols, add_rank=False)

        return f"""
<div style='line-height:1.8'>

<div style='font-size:20px;font-weight:bold'>
📈 Trend Insight
</div>

<div style='margin-top:10px;color:#94a3b8;font-size:14px'>
{html.escape(summary)}
</div>

<div style='margin-top:18px;color:#dbeafe;font-size:15px;font-weight:bold'>
{html.escape(table_title)}
</div>

<div style='margin-top:10px;overflow-x:auto'>
{table_html}
</div>

<div style='margin-top:10px;color:#94a3b8'>
Analysis based on {len(df)} records
</div>

</div>
"""

    # ======================
    # CASE 2: KPI OR RANKING
    # ======================
    if metric_col is not None:
        top = df.iloc[0]
        formatted_value = format_metric(top[metric_col], metric_col)
        metric_lower = metric_col.lower()

        ranking_table_html = ""

        has_real_label = (
            label_col != metric_col
            and label_col in df.columns
            and not pd.api.types.is_numeric_dtype(df[label_col])
        )

        top_tied_count = 1
        try:
            top_tied_count = int((df[metric_col] == top[metric_col]).sum())
        except Exception:
            top_tied_count = 1

        is_rate_ranking = (
            len(df) > 1
            and any(x in metric_lower for x in ["rate", "pct", "percent"])
        )

        if len(df) > 1:
            ranking_table_html = f"""
<div style='margin-top:18px;color:#dbeafe;font-size:15px;font-weight:bold'>
{html.escape(table_title)}
</div>

<div style='margin-top:10px;overflow-x:auto'>
{build_formatted_table(df, display_cols, add_rank=True)}
</div>
"""

        label_html = ""

        if is_rate_ranking and top_tied_count > 1:
            label_html = f"""
<div style='font-size:22px;font-weight:bold;color:#60a5fa;margin-top:15px'>
{top_tied_count} results tied at the highest rate
</div>
"""
        elif has_real_label:
            label_html = f"""
<div style='font-size:22px;font-weight:bold;color:#60a5fa;margin-top:15px'>
{html.escape(str(top[label_col]))}
</div>
"""

        return f"""
<div style='line-height:1.8'>

<div style='font-size:20px;font-weight:bold'>
📊 Business Insight
</div>

{label_html}

<div style='font-size:30px;font-weight:bold;color:#34d399;margin-top:15px'>
{formatted_value}
</div>

<div style='margin-top:6px;color:#94a3b8;font-size:13px'>
{html.escape(clean_label(metric_col))}
</div>

<div style='margin-top:10px;color:#94a3b8;font-size:14px'>
{html.escape(summary)}
</div>

{ranking_table_html}

<div style='margin-top:10px;color:#94a3b8'>
Analysis based on {len(df)} records
</div>

</div>
"""

    # ======================
    # CASE 3: DESCRIPTIVE / LIST RESULT
    # ======================
    table_html = build_formatted_table(df, display_cols, add_rank=False)

    return f"""
<div style='line-height:1.8'>

<div style='font-size:20px;font-weight:bold'>
📋 Result Summary
</div>

<div style='font-size:26px;font-weight:bold;color:#34d399;margin-top:12px'>
{len(df)} records found
</div>

<div style='margin-top:10px;color:#94a3b8;font-size:14px'>
{html.escape(summary)}
</div>

<div style='margin-top:18px;color:#dbeafe;font-size:15px;font-weight:bold'>
{html.escape(table_title)}
</div>

<div style='margin-top:10px;overflow-x:auto'>
{table_html}
</div>

</div>
"""


def build_sql_preview_answer(df: pd.DataFrame, sql: str) -> str:
    """
    Render direct SQL input as a table preview instead of forcing it into
    the Business Insight/KPI card renderer.
    """
    display_cols = [
        c for c in df.columns
        if not _is_internal_display_col(c)
    ]

    if not display_cols:
        display_cols = list(df.columns)

    preview_df = df[display_cols].head(20)
    table_html = build_formatted_table(
        preview_df,
        display_cols,
        add_rank=False
    )

    shown_rows = min(len(df), 20)

    return f"""
<div style='line-height:1.8'>

<div style='font-size:20px;font-weight:bold'>
📋 SQL Result Preview
</div>

<div style='margin-top:10px;color:#94a3b8;font-size:14px'>
The SQL query was executed successfully. Showing the first {shown_rows} rows.
</div>

<div style='margin-top:18px;color:#dbeafe;font-size:15px;font-weight:bold'>
Query Result
</div>

<div style='margin-top:10px;overflow-x:auto'>
{table_html}
</div>

<div style='margin-top:10px;color:#94a3b8;font-size:12px'>
Raw SQL input was handled as a table preview, not as a KPI insight.
</div>

</div>
"""


def _json_safe_value(value):
    """Convert pandas/numpy scalar values into JSON-safe Python values."""
    if pd.isna(value):
        return None
    if isinstance(value, np.generic):
        return value.item()
    return value


def _first_existing_column(columns: list[str], candidates: list[str]) -> str | None:
    lower_map = {str(col).lower(): col for col in columns}
    for candidate in candidates:
        if candidate.lower() in lower_map:
            return lower_map[candidate.lower()]
    return None


def _pick_metric_column_for_chart(df: pd.DataFrame) -> str | None:
    numeric_cols = [
        col for col in df.columns
        if pd.api.types.is_numeric_dtype(df[col]) and _is_measure_col(col)
    ]

    if numeric_cols:
        return numeric_cols[0]

    # Fallback for numeric-looking object columns after JSON/None conversion.
    for col in df.columns:
        if _is_measure_col(col):
            coerced = pd.to_numeric(df[col], errors="coerce")
            if coerced.notna().any():
                return col

    return None


def build_chart_metadata(df: pd.DataFrame, question: str = "") -> dict:
    """
    Return chart-ready JSON metadata for the front-end.

    The API still returns the full table in `data`; this object tells the UI
    how to visualize the same rows as a KPI, line chart, bar chart, or table.
    """
    if df is None or df.empty:
        return {
            "available": False,
            "type": "none",
            "title": "No chart available",
            "x": None,
            "y": None,
            "data": [],
        }

    columns = list(df.columns)
    metric_col = _pick_metric_column_for_chart(df)
    result_type = _detect_result_type(question, df, metric_col)

    time_col = _first_existing_column(
        columns,
        ["year", "trade_year", "order_year", "date_year", "month", "quarter", "month_name", "quarter_name"],
    )

    label_candidates = [
        col for col in columns
        if col != metric_col and not _is_internal_display_col(col)
    ]
    label_col = next(
        (col for col in label_candidates if not pd.api.types.is_numeric_dtype(df[col])),
        label_candidates[0] if label_candidates else None,
    )

    if metric_col is None:
        return {
            "available": False,
            "type": "table",
            "title": "Table Result",
            "x": None,
            "y": None,
            "data": [
                {col: _json_safe_value(row[col]) for col in columns}
                for _, row in df.head(20).iterrows()
            ],
        }

    if result_type == "trend" and time_col:
        x_col = time_col
        chart_type = "line"
        title = f"{clean_label(metric_col)} Trend"
    elif len(df) == 1:
        top = df.iloc[0]
        return {
            "available": True,
            "type": "kpi",
            "title": clean_label(metric_col),
            "metric": metric_col,
            "label": label_col,
            "value": _json_safe_value(top[metric_col]),
            "label_value": _json_safe_value(top[label_col]) if label_col else None,
            "data": [{
                "metric": metric_col,
                "value": _json_safe_value(top[metric_col]),
                "label": _json_safe_value(top[label_col]) if label_col else None,
            }],
        }
    elif label_col:
        x_col = label_col
        chart_type = "bar"
        title = f"{clean_label(metric_col)} by {clean_label(label_col)}"
    else:
        return {
            "available": False,
            "type": "table",
            "title": "Table Result",
            "x": None,
            "y": None,
            "data": [
                {col: _json_safe_value(row[col]) for col in columns}
                for _, row in df.head(20).iterrows()
            ],
        }

    chart_rows = []
    for _, row in df[[x_col, metric_col]].head(20).iterrows():
        chart_rows.append({
            x_col: _json_safe_value(row[x_col]),
            metric_col: _json_safe_value(row[metric_col]),
        })

    return {
        "available": True,
        "type": chart_type,
        "title": title,
        "x": x_col,
        "y": metric_col,
        "data": chart_rows,
    }

# ======================
# CHAT
# ======================

@app.route("/chat", methods=["POST"])
def chat():
    try:
        total_start = time.time()

        data = request.json or {}
        original_question = data.get("message", "").strip()
        question = normalise_question_for_ai(original_question)
        session_id = _get_session_id(data)

        if original_question and question != original_question:
            logger.info(
                "Question normalized | %s",
                {
                    "original_hash": _hash_text(original_question),
                    "normalized_hash": _hash_text(question),
                    "session_id": session_id,
                },
            )

        # Empty question check
        if not original_question:
            return jsonify({"error": "Question is empty"}), 400

        # Small-talk intercept — no LLM or DB call
        if original_question.lower() in _SMALL_TALK:
            return jsonify({
                "answer": _SMALL_TALK[original_question.lower()],
                "sql": "",
                "data": []
            })

        # Database availability check before spending AI tokens
        if engine is None:
            return jsonify({
                "answer": f"⚠️ Database connection is not available. Error: {db_error_msg}",
                "sql": "",
                "data": []
            }), 500

        # ======================
        # Direct SQL Preview Handler
        # ======================
        # If the user writes a SELECT/WITH query directly, execute it safely
        # and render a table preview instead of a misleading KPI card.
        if _looks_like_sql_query(original_question):
            validation = validate_sql(original_question)

            if not validation.is_valid:
                return jsonify({
                    "answer": "⚠️ This SQL query is not allowed or is unsafe.",
                    "sql": original_question,
                    "data": []
                }), 400

            try:
                df = pd.read_sql(original_question, engine)
                df = df.drop_duplicates()
                df = df.head(20)
                df = df.replace([np.nan, np.inf, -np.inf], None)
                records = df.to_dict(orient="records")

                chart = build_chart_metadata(df, original_question)

                return jsonify({
                    "answer": build_sql_preview_answer(df, original_question),
                    "sql": original_question,
                    "data": records,
                    "chart": chart
                })

            except Exception as exc:
                return jsonify({
                    "answer": f"⚠️ SQL execution failed: {str(exc)}",
                    "sql": original_question,
                    "data": []
                }), 500

        # OpenRouter availability check before spending DB work
        if client is None:
            return jsonify({
                "answer": "⚠️ AI client is not available. Please check OPENROUTER_API_KEY in your .env file.",
                "sql": "",
                "data": []
            }), 500

        # Dedicated Arabic translation step before intent detection
        if _contains_arabic(original_question):
            question = translate_arabic_question_for_ai(original_question, question)

        # Resolve follow-up questions using the previous successful turn
        question = _hydrate_follow_up_question(session_id, original_question, question)

        # Cache check
        cache_key = hashlib.md5(question.lower().strip().encode()).hexdigest()

        if cache_key in _cache:
            cached = dict(_cache[cache_key])
            cached["cached"] = True
            _remember_conversation(
                session_id,
                original_question,
                question,
                cached.get("intent", "UNKNOWN"),
                cached.get("sql", ""),
                cached.get("data", []),
                cached.get("chart", {}),
            )
            return jsonify(cached)

        # ======================
        # Stage 1: Intent Detection
        # ======================

        intent = _llm(
            INTENT_SYSTEM,
            build_intent_prompt(question),
            _INTENT_MODEL,
            max_tokens=20
        ).upper()

        if intent not in {"TRADE", "MACRO", "SUPPLY_CHAIN", "GENERAL", "UNANSWERABLE"}:
            intent = "TRADE"

        if intent == "GENERAL":
            return jsonify({
                "answer": "😊 I can help with trade, macro-economic, and supply-chain questions. What would you like to know?",
                "sql": "",
                "data": []
            })

        if intent == "UNANSWERABLE":
            return jsonify({
                "answer": "⚠️ I don't have data to answer that question. Try asking about trade flows, economic indicators, or supply chain performance.",
                "sql": "",
                "data": []
            })

        # ======================
        # Stage 2: SQL Generation
        # ======================

        sql_start = time.time()

        generated_sql = _clean_sql(
            _llm(
                SQL_SYSTEM,
                build_sql_prompt(question, intent),
                _SQL_MODEL,
                max_tokens=800
            )
        )

        _safe_log_sql(
            "SQL generated",
            generated_sql,
            intent=intent,
            duration_sec=round(time.time() - sql_start, 2),
            session_id=session_id,
        )

        if generated_sql.upper().startswith("CANNOT_ANSWER"):
            fallback_message = (
                "⚠️ I could not map this question to the available schema. "
                "Try asking about trade values, countries, commodities, GDP, supply-chain KPIs, or late delivery rate."
            )

            if _contains_arabic(original_question):
                fallback_message = (
                    "⚠️ لم أستطع ربط السؤال بالأعمدة المتاحة في قاعدة البيانات. "
                    "جرّب السؤال عن قيمة التجارة، الدول، المنتجات، GDP، مؤشرات سلسلة الإمداد، أو معدل تأخير التسليم."
                )

            return jsonify({
                "answer": fallback_message,
                "sql": "",
                "data": []
            })

        # ======================
        # Stage 3: SQL Validation
        # ======================

        validation = validate_sql(generated_sql)

        if not validation.is_valid:
            logger.warning("SQL validation failed | %s", {"errors": validation.errors, "session_id": session_id})

            repaired = _clean_sql(
                _llm(
                    SQL_REPAIR_SYSTEM,
                    build_repair_prompt(
                        generated_sql,
                        "; ".join(validation.errors),
                        question
                    ),
                    _REPAIR_MODEL,
                    max_tokens=800
                )
            )

            if repaired and not repaired.upper().startswith("CANNOT_REPAIR"):
                re_val = validate_sql(repaired)

                if re_val.is_valid:
                    generated_sql = repaired
                    logger.info("SQL repaired after validation failure | %s", {"session_id": session_id})
                else:
                    return jsonify({
                        "answer": "⚠️ Unable to generate a safe query for this question.",
                        "sql": "",
                        "data": []
                    })
            else:
                return jsonify({
                    "answer": "⚠️ Unable to generate a safe query for this question.",
                    "sql": "",
                    "data": []
                })

        if validation.warnings:
            logger.info("SQL validation warnings | %s", {"warnings": validation.warnings, "session_id": session_id})

        # ======================
        # Stage 4: SQL Execution
        # ======================

        df = None
        exec_error = None

        for attempt in range(_MAX_RETRIES + 1):
            try:
                query_start = time.time()

                df = pd.read_sql(generated_sql, engine)

                logger.info("SQL executed | %s", {"duration_sec": round(time.time() - query_start, 2), "session_id": session_id})
                break

            except Exception as exc:
                exec_error = str(exc)
                logger.warning("SQL execution failed | %s", {"attempt": attempt + 1, "error": exec_error, "session_id": session_id})

                if attempt < _MAX_RETRIES:
                    repaired = _clean_sql(
                        _llm(
                            SQL_REPAIR_SYSTEM,
                            build_repair_prompt(
                                generated_sql,
                                exec_error,
                                question
                            ),
                            _REPAIR_MODEL,
                            max_tokens=800
                        )
                    )

                    if repaired and not repaired.upper().startswith("CANNOT_REPAIR"):
                        if validate_sql(repaired).is_valid:
                            generated_sql = repaired
                            logger.info("SQL repaired, retrying execution | %s", {"session_id": session_id})
                        else:
                            break
                    else:
                        break

        if df is None:
            return jsonify({
                "answer": f"⚠️ Query execution failed: {exec_error}",
                "sql": generated_sql,
                "data": []
            }), 500

        # Empty result
        if df.empty:
            return jsonify({
                "answer": "No data found",
                "sql": generated_sql,
                "data": [],
                "chart": build_chart_metadata(pd.DataFrame(), question)
            })

        # ======================
        # Stage 5: Clean Result
        # ======================

# Remove exact duplicate rows caused by joins or repeated calendar grain
        df = df.drop_duplicates()

        df = df.head(20)
        df = df.replace([np.nan, np.inf, -np.inf], None)
        records = df.to_dict(orient="records")
        chart = build_chart_metadata(df, question)

        # ======================
        # Stage 6: Summarization
        # ======================

        summary = _llm(
            SUMMARY_SYSTEM,
            build_summary_prompt(question, generated_sql, records),
            _SUMMARY_MODEL,
            max_tokens=200
        )

        # ======================
        # Stage 7: Render Smart Answer
        # ======================

        answer = build_ai_answer(df, summary, question)

        logger.info("Chat request completed | %s", {"duration_sec": round(time.time() - total_start, 2), "session_id": session_id})

        response_payload = {
            "answer": answer,
            "sql": generated_sql,
            "data": records,
            "chart": chart,
            "intent": intent
        }

        _remember_conversation(
            session_id,
            original_question,
            question,
            intent,
            generated_sql,
            records,
            chart,
        )

        _cache[cache_key] = response_payload

        return jsonify(response_payload)

    except Exception as e:
        logger.exception("Chat request failed")

        return jsonify({
            "error": str(e)
        }), 500



# ======================
# UPDATE SUBSCRIPTIONS - SHAREPOINT VIA POWER AUTOMATE
# ======================

def _post_subscriber_preference(email: str, is_active: bool, reports: list[str]) -> dict:
    """
    Sends the user's update-alert preference to a Power Automate HTTP trigger.
    The flow should create/update the SharePoint list: ReportSubscribers.
    """
    if not SUBSCRIBE_FLOW_URL:
        return {
            "ok": False,
            "status_code": 500,
            "data": {
                "error": "SUBSCRIBE_FLOW_URL is missing in .env file"
            }
        }

    email = _normalise_email(email)

    payload = {
        "email": email,
        "isActive": is_active,
        "reports": reports if reports else ["ALL"],
        "source": "local-flask-web-app"
    }

    response = requests.post(
        SUBSCRIBE_FLOW_URL,
        json=payload,
        headers={
            "Content-Type": "application/json"
        },
        timeout=20
    )

    try:
        response_data = response.json()
    except Exception:
        response_data = {
            "raw": response.text
        }

    return {
        "ok": response.status_code in [200, 201, 202],
        "status_code": response.status_code,
        "data": response_data
    }


def _extract_subscription_payload() -> tuple[str, list[str]]:
    data = request.json or {}

    email = _normalise_email(data.get("email", ""))
    reports = data.get("reports") or ["ALL"]

    if isinstance(reports, str):
        reports = [reports]

    reports = [
        str(report).strip()
        for report in reports
        if str(report).strip()
    ] or ["ALL"]

    return email, reports


@app.route("/subscribe-updates", methods=["POST"])
def subscribe_updates():
    """Enable update alerts for an email via the SharePoint-backed Power Automate flow."""
    try:
        email, reports = _extract_subscription_payload()

        if not email:
            return jsonify({"error": "Email required"}), 400

        if not _EMAIL_RE.match(email):
            return jsonify({"error": "Invalid email format"}), 400

        result = _post_subscriber_preference(
            email=email,
            is_active=True,
            reports=reports
        )

        if not result["ok"]:
            return jsonify({
                "error": "Subscriber flow failed",
                "details": result["data"]
            }), result["status_code"]

        return jsonify({
            "message": "You are subscribed to report update alerts.",
            "email": email,
            "isActive": True
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/unsubscribe-updates", methods=["POST"])
def unsubscribe_updates():
    """Disable update alerts for an email via the SharePoint-backed Power Automate flow."""
    try:
        email, reports = _extract_subscription_payload()

        if not email:
            return jsonify({"error": "Email required"}), 400

        if not _EMAIL_RE.match(email):
            return jsonify({"error": "Invalid email format"}), 400

        result = _post_subscriber_preference(
            email=email,
            is_active=False,
            reports=reports
        )

        if not result["ok"]:
            return jsonify({
                "error": "Subscriber flow failed",
                "details": result["data"]
            }), result["status_code"]

        return jsonify({
            "message": "You are unsubscribed from report update alerts.",
            "email": email,
            "isActive": False
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ======================
# SEND PDF
# ======================

@app.route("/send-dashboard-pdf", methods=["POST"])
def send_dashboard_pdf():
    try:
        data = request.json or {}

        email = data.get("email")
        reports = data.get("reports", [])
        title = data.get("title", "Dashboard Export")
        raw_parameters = data.get("parameters") or {}
        raw_parameters_by_id = data.get("parametersById") or {}

        if not email:
            return jsonify({
                "error": "Email required"
            }), 400

        if len(reports) == 0:
            return jsonify({
                "error": "Select at least one report"
            }), 400

        canonical_reports = []
        for raw_report in reports:
            raw_report = str(raw_report)
            raw_report_trimmed = raw_report.strip()

            canonical_report = (
                REPORT_ALIASES.get(raw_report)
                or REPORT_ALIASES.get(raw_report_trimmed)
                or raw_report
                or raw_report_trimmed
            )

            if canonical_report in VALID_REPORTS:
                canonical_reports.append(canonical_report)

        reports = canonical_reports

        # Remove duplicates while preserving the user's selected order.
        reports = list(dict.fromkeys(reports))

        if len(reports) == 0:
            return jsonify({
                "error": "No valid reports selected"
            }), 400

        if not POWER_AUTOMATE_URL:
            return jsonify({
                "error": "POWER_AUTOMATE_URL is missing in .env file"
            }), 500

        selected_report_objects = [REPORT_BY_NAME[report_name] for report_name in reports]

        # Keep report parameters aligned with the canonical Power BI API names and IDs.
        # The iframe parameter selections are not readable by Flask, so the front-end
        # sends parameter values explicitly from the Share Reports modal.
        canonical_parameters_by_name = {}
        canonical_parameters_by_id = {}

        if isinstance(raw_parameters, dict):
            for raw_report_name, parameter_values in raw_parameters.items():
                canonical_name = (
                    REPORT_ALIASES.get(str(raw_report_name))
                    or REPORT_ALIASES.get(str(raw_report_name).strip())
                    or str(raw_report_name)
                )

                if canonical_name in REPORT_BY_NAME and isinstance(parameter_values, list):
                    normalized_parameters = _normalize_report_parameters(
                        canonical_name,
                        REPORT_BY_NAME[canonical_name]["id"],
                        parameter_values
                    )
                    canonical_parameters_by_name[canonical_name] = normalized_parameters
                    canonical_parameters_by_id[REPORT_BY_NAME[canonical_name]["id"]] = normalized_parameters

        if isinstance(raw_parameters_by_id, dict):
            for raw_report_id, parameter_values in raw_parameters_by_id.items():
                raw_report_id = str(raw_report_id).strip()

                if raw_report_id in REPORT_BY_ID and isinstance(parameter_values, list):
                    report_name = REPORT_BY_ID[raw_report_id]["name"]
                    normalized_parameters = _normalize_report_parameters(
                        report_name,
                        raw_report_id,
                        parameter_values
                    )
                    canonical_parameters_by_name[report_name] = normalized_parameters
                    canonical_parameters_by_id[raw_report_id] = normalized_parameters

        # Only keep parameters for reports selected in this request.
        selected_report_ids = {report["id"] for report in selected_report_objects}
        selected_report_names = {report["name"] for report in selected_report_objects}
        canonical_parameters_by_name = {
            report_name: params
            for report_name, params in canonical_parameters_by_name.items()
            if report_name in selected_report_names
        }
        canonical_parameters_by_id = {
            report_id: params
            for report_id, params in canonical_parameters_by_id.items()
            if report_id in selected_report_ids
        }

        payload = {
            "email": email,
            "title": title,
            # Kept for backward compatibility with the old working flow.
            "reports": reports,
            # Use this in Power Automate Filter array for stable matching.
            "reportIds": [report["id"] for report in selected_report_objects],
            # RDL parameter values to be used by Power Automate during export.
            "parameters": canonical_parameters_by_name,
            "parametersById": canonical_parameters_by_id,
            # Optional metadata if the flow needs type/name without another API lookup.
            "reportMeta": [
                {
                    "id": report["id"],
                    "name": report["name"],
                    "title": report["title"],
                    "type": report["type"],
                    "format": report["format"],
                    "parameters": canonical_parameters_by_id.get(report["id"], [])
                }
                for report in selected_report_objects
            ]
        }

        logger.info(
            "Power Automate export requested | %s",
            {
                "email_hash": _hash_text(email),
                "title_hash": _hash_text(title),
                "report_count": len(selected_report_objects),
                "report_ids": [report["id"] for report in selected_report_objects],
            },
        )

        response = requests.post(
            POWER_AUTOMATE_URL,
            json=payload,
            headers={
                "Content-Type": "application/json"
            }
        )

        logger.info("Power Automate response | %s", {"status_code": response.status_code, "body_hash": _hash_text(response.text)})

        if response.status_code not in [200, 202]:
            return jsonify({
                "error": "Power Automate failed",
                "details": response.text
            }), response.status_code

        return jsonify({
                "message": "Report request submitted successfully. A download link will be sent to your email within 2–4 minutes.",
                "note": "If you do not see the email in your inbox, please check your Spam or Junk folder."
                        })

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500

# ======================
# RUN
# ======================

if __name__ == "__main__":
    app.run(debug=True)