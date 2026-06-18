"""
prompt_builder.py
-----------------
Builds production-grade, hallucination-resistant prompts for each pipeline stage.

This module implements:
  1. Intent detection prompt — classifies the question before SQL generation.
  2. SQL generation prompt — grounds model in ONLY the relevant schema slice.
  3. SQL repair prompt — self-healing pass with the specific error message.
  4. Answer summarisation prompt — converts raw SQL results into business prose.
"""

from __future__ import annotations

from .schema_retriever import build_schema_block, get_relevant_views


# ──────────────────────────────────────────────
# 1. Intent detection prompt
# ──────────────────────────────────────────────

INTENT_SYSTEM = """
You are an intent classifier for a business intelligence system.

Classify the user's question into exactly ONE of these categories:

TRADE         — imports, exports, trade balance, trading partners, commodities
MACRO         — GDP, inflation, foreign reserves, exchange rate, economic indicators
SUPPLY_CHAIN  — shipping, delivery, orders, products, late deliveries, profit, sales
GENERAL       — greetings, thanks, capability questions
UNANSWERABLE  — question cannot be answered from this database

Return ONLY the category word. No explanation. No punctuation.
""".strip()


def build_intent_prompt(question: str) -> str:
    return question


# ──────────────────────────────────────────────
# 2. SQL generation prompt
# ──────────────────────────────────────────────

SQL_SYSTEM = """
You are a T-SQL query generator for SQL Server.
Output ONLY executable T-SQL. No explanations. No comments. No markdown.
If the question cannot be answered from the provided schema, output exactly:
CANNOT_ANSWER
""".strip()


def build_sql_prompt(question: str, intent: str) -> str:
    """
    Build a grounded SQL generation prompt.

    The schema block contains ONLY the views relevant to the question's intent,
    preventing the model from touching the wrong views.
    """
    relevant_views = get_relevant_views(question)
    schema_block = build_schema_block(relevant_views)
    intent_hint = _get_intent_hint(intent)

    prompt = f"""
=== DATABASE ===
{schema_block}

=== SYNTAX RULES ===
1. SQL Server T-SQL only — never MySQL or PostgreSQL syntax.
2. Use TOP N only for ranking/list questions such as top/highest/lowest/most/least. Do NOT use TOP for time-series trend queries that group/order by year, month, or quarter.
3. Never use LIMIT.
4. Query ONLY the views listed above — never raw tables.
5. Use exact view names only. Do NOT prefix views with database names, schema names, or dbo.
   Correct: FROM vw_fact_trade_flows AS tf
   Wrong: FROM EgyptBI_DWH1.vw_fact_trade_flows AS tf
   Wrong: FROM dbo.vw_fact_trade_flows AS tf
6. Never SELECT * — always name every column you use.
7. Always alias every column (e.g. SUM(trade_value_usd) AS total_trade_usd).
8. Always alias every view (e.g. FROM vw_fact_trade_flows AS tf).
9. Always include GROUP BY when SELECT contains non-aggregate columns.
10. Join dimension views whenever a human-readable name is needed.
11. Use INNER JOIN unless a LEFT JOIN is semantically required.
12. Output starts with SELECT or WITH — nothing else before it.

=== REFUSAL RULE ===
If the question asks about data, columns, or views NOT listed in the schema above,
output exactly this token and nothing else:
CANNOT_ANSWER

=== DOMAIN HINT ===
{intent_hint}

=== QUESTION ===
{question}

=== YOUR SQL ===
""".strip()

    return prompt


def _get_intent_hint(intent: str) -> str:
    hints = {
        "TRADE": (
            "The question is about trade flows. "
            "Use vw_fact_trade_flows as the fact table. "
            "IMPORTANT: flow_type uses coded values, not words. "
            "Use UPPER(LTRIM(RTRIM(flow_type))) = 'X' for exports. "
            "Use UPPER(LTRIM(RTRIM(flow_type))) = 'M' for imports. "
            "When calculating trade balance, exports are positive and imports are negative. "
            "When calculating trade balance, alias it as trade_balance_usd, not trade_balance. "
            "Always SUM(trade_value_usd) for trade value totals. "
            "Always include _usd in aliases for monetary values. "
            "Join vw_dim_country for country names, vw_dim_commodity for product names, "
            "vw_dim_date for year/quarter/month filtering."
        ),
        "MACRO": (
                "The question is about macro-economic indicators. "
                "Use vw_dim_egypt_macro as the primary view. "
                "Join vw_dim_date for year, quarter, or month filtering. "
                "IMPORTANT: When showing a yearly macro trend, return one row per year only. "
                "Use GROUP BY dd.year with AVG(metric) or MAX(metric), or use DISTINCT when the metric is already repeated per year. "
                "Do not return repeated rows for the same year. "
                "For GDP growth trend, use dd.year and AVG(gdp_growth_pct) AS gdp_growth_pct grouped by dd.year. "
                "Do NOT join to vw_fact_trade_flows — macro and trade are separate domains."
        ),
        "SUPPLY_CHAIN": (
            "The question is about supply chain / order performance. "
            "Use vw_fact_supply_chain as the fact table. "
            "Join vw_dim_product for product names. "
            "Join vw_dim_country for country names. "
            "is_late = 1 means late delivery. "
            "Use AVG(shipping_delay_days) for average shipping delay. "
            "Use SUM(sales_usd) for revenue and SUM(profit_usd) for profit."
        ),
        "GENERAL": "This is a general question — no SQL needed.",
        "UNANSWERABLE": "This question cannot be answered from the available schema.",
    }

    return hints.get(intent, hints["TRADE"])


# ──────────────────────────────────────────────
# 3. SQL repair prompt
# ──────────────────────────────────────────────

SQL_REPAIR_SYSTEM = """
You are a T-SQL repair specialist for SQL Server.
You will receive a broken SQL query and the exact error message.
Return ONLY the corrected T-SQL query. No explanation. No comments. No markdown.
If the query cannot be repaired, output exactly:
CANNOT_REPAIR
""".strip()


def build_repair_prompt(
    original_sql: str,
    error_message: str,
    question: str,
) -> str:
    relevant_views = get_relevant_views(question)
    schema_block = build_schema_block(relevant_views)

    return f"""
=== SCHEMA (ground truth — use only these views and columns) ===
{schema_block}

=== ORIGINAL SQL (broken) ===
{original_sql}

=== ERROR MESSAGE ===
{error_message}

=== TASK ===
Fix the SQL so it:
1. Executes without errors on SQL Server.
2. Uses only the views and columns listed in the schema above.
3. Answers the original question: "{question}".
4. Follows all T-SQL rules: use TOP only for ranking/list queries, never LIMIT, no SELECT *, proper GROUP BY.
5. Uses exact view names only; do not prefix views with database names, schema names, or dbo.
6. Uses flow_type code 'X' for exports and 'M' for imports when trade flow direction is needed.

=== REPAIRED SQL ===
""".strip()


# ──────────────────────────────────────────────
# 4. Answer summarisation prompt
# ──────────────────────────────────────────────

SUMMARY_SYSTEM = """
You are a business intelligence analyst for Egypt Trade and Supply Chain dashboards.
Convert raw SQL results into a clear, concise business insight.

Rules:
1. Write only 1–2 short sentences.
2. Only use facts that exist in the query results.
3. Do not invent causes, risks, or business explanations that are not in the data.
4. If the result is a ranking table, mention only the top item and the main comparison.
5. If many rows have the same value, summarize them as a tie instead of listing many names.
6. Use USD formatting only for monetary columns such as trade_value_usd, sales_usd, profit_usd, revenue_usd, total_*_usd, or trade_balance_usd.
7. Format delay columns as days.
8. Never treat keys, IDs, HS codes, years, or flags as business metrics.
""".strip()


def build_summary_prompt(question: str, sql: str, records: list[dict]) -> str:
    # Send at most 5 records to the summariser — we only need context, not all rows
    sample = records[:20]

    return f"""
Original question: {question}

SQL that was executed:
{sql}

Query results shown to the user ({len(sample)} of {len(records)} rows):
{sample}

Write a concise 1–2 sentence insight.
If this is a trend result, use all rows provided to identify the real highest, lowest, increase, or decline.
If this is a ranking result, mention the top item and summarize ties or patterns briefly.
Do not repeat every row because the table will already show the detailed values.
Only format a number as currency if the column name clearly represents money.
Never claim a peak, minimum, increase, or decrease unless it is supported by the provided rows.
""".strip()