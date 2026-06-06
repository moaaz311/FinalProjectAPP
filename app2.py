from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from openai import OpenAI
from flask_mail import Mail

import hashlib
import html
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
    print("OpenRouter Error:", e)
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

    # Test real database connection
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

    print("Database Connected")

except Exception as e:
    print("Database Error:", e)
    engine = None

# ======================
# HOME
# ======================

@app.route("/")
def home():
    return render_template("index2.html")

# ======================
# REPORTS
# ======================

REPORTS = [
    {
        "name": "Full_Light_Mode_PowerBI",
        "url": "https://app.powerbi.com/reportEmbed?reportId=fd74639c-26b8-4245-927c-f5e5f7bfa1e4&autoAuth=true&ctid=ff4a48d6-4b5e-4fd3-8266-7eafc3e6e23e"
    },
    {
        "name": "StrategicDependency",
        "url": "https://app.powerbi.com/rdlEmbed?reportId=71e8e860-6d44-4983-87ab-ca5ea954c090&autoAuth=true&ctid=ff4a48d6-4b5e-4fd3-8266-7eafc3e6e23e&experience=power-bi"
    },
    {
        "name": "TradeExecutive",
        "url": "https://app.powerbi.com/rdlEmbed?reportId=e0d8797e-4b9c-4598-8cce-4d422f55d6f3&autoAuth=true&ctid=ff4a48d6-4b5e-4fd3-8266-7eafc3e6e23e&experience=power-bi"
    }
]

VALID_REPORTS = [
    "Full_Light_Mode_PowerBI",
    "StrategicDependency",
    "TradeExecutive"
]

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

        ranking_table_html = ""

        if len(df) > 1:
            ranking_table_html = f"""
<div style='margin-top:18px;color:#dbeafe;font-size:15px;font-weight:bold'>
{html.escape(table_title)}
</div>

<div style='margin-top:10px;overflow-x:auto'>
{build_formatted_table(df, display_cols, add_rank=True)}
</div>
"""

        return f"""
<div style='line-height:1.8'>

<div style='font-size:20px;font-weight:bold'>
📊 Business Insight
</div>

<div style='font-size:22px;font-weight:bold;color:#60a5fa;margin-top:15px'>
{html.escape(str(top[label_col]))}
</div>

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

# ======================
# CHAT
# ======================

@app.route("/chat", methods=["POST"])
def chat():
    try:
        total_start = time.time()

        data = request.json or {}
        question = data.get("message", "").strip()

        # Empty question check
        if not question:
            return jsonify({"error": "Question is empty"}), 400

        # Small-talk intercept — no LLM or DB call
        if question.lower() in _SMALL_TALK:
            return jsonify({
                "answer": _SMALL_TALK[question.lower()],
                "sql": "",
                "data": []
            })

        # Database availability check before spending AI tokens
        if engine is None:
            return jsonify({
                "answer": "⚠️ Database connection is not available. Please check SQL_SERVER and SQL_DATABASE in your .env file.",
                "sql": "",
                "data": []
            }), 500

        # OpenRouter availability check before spending DB work
        if client is None:
            return jsonify({
                "answer": "⚠️ AI client is not available. Please check OPENROUTER_API_KEY in your .env file.",
                "sql": "",
                "data": []
            }), 500

        # Cache check
        cache_key = hashlib.md5(question.lower().strip().encode()).hexdigest()

        if cache_key in _cache:
            cached = dict(_cache[cache_key])
            cached["cached"] = True
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

        print("\nGenerated SQL:\n", generated_sql)
        print("SQL Generation:", round(time.time() - sql_start, 2), "sec")

        if generated_sql.upper().startswith("CANNOT_ANSWER"):
            return jsonify({
                "answer": "⚠️ This question requires data not available in the current schema.",
                "sql": "",
                "data": []
            })

        # ======================
        # Stage 3: SQL Validation
        # ======================

        validation = validate_sql(generated_sql)

        if not validation.is_valid:
            print("Validation errors:", validation.errors)

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
                    print("SQL repaired after validation failure")
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
            print("SQL warnings:", validation.warnings)

        # ======================
        # Stage 4: SQL Execution
        # ======================

        df = None
        exec_error = None

        for attempt in range(_MAX_RETRIES + 1):
            try:
                query_start = time.time()

                df = pd.read_sql(generated_sql, engine)

                print("SQL Execution:", round(time.time() - query_start, 2), "sec")
                break

            except Exception as exc:
                exec_error = str(exc)
                print(f"Execution error (attempt {attempt + 1}):", exec_error)

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
                            print("SQL repaired, retrying execution")
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
                "data": []
            })

        # ======================
        # Stage 5: Clean Result
        # ======================

# Remove exact duplicate rows caused by joins or repeated calendar grain
        df = df.drop_duplicates()

        df = df.head(20)
        df = df.replace([np.nan, np.inf, -np.inf], None)
        records = df.to_dict(orient="records")

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

        print("TOTAL:", round(time.time() - total_start, 2), "sec")

        response_payload = {
            "answer": answer,
            "sql": generated_sql,
            "data": records
        }

        _cache[cache_key] = response_payload

        return jsonify(response_payload)

    except Exception as e:
        print(str(e))

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

        if not email:
            return jsonify({
                "error": "Email required"
            }), 400

        if len(reports) == 0:
            return jsonify({
                "error": "Select at least one report"
            }), 400

        reports = [
            r.strip()
            for r in reports
            if r.strip() in VALID_REPORTS
        ]

        if len(reports) == 0:
            return jsonify({
                "error": "No valid reports selected"
            }), 400

        if not POWER_AUTOMATE_URL:
            return jsonify({
                "error": "POWER_AUTOMATE_URL is missing in .env file"
            }), 500

        payload = {
            "email": email,
            "title": title,
            "reports": reports
        }

        print("Payload:")
        print(payload)

        response = requests.post(
            POWER_AUTOMATE_URL,
            json=payload,
            headers={
                "Content-Type": "application/json"
            }
        )

        print(response.text)

        if response.status_code not in [200, 202]:
            return jsonify({
                "error": "Power Automate failed",
                "details": response.text
            }), response.status_code

        return jsonify({
            "message": "PDF sent successfully"
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
