"""
sql_validator.py
----------------
Multi-stage SQL validation layer that sits between generation and execution.

This validator:
  1. Blocks dangerous patterns.
  2. Checks referenced views exist in the schema.
  3. Checks referenced columns heuristically.
  4. Warns about likely GROUP BY issues.
  5. Allows missing TOP for time-series trend queries.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .schema_retriever import get_all_valid_views, get_all_valid_columns


# ──────────────────────────────────────────────
# Data model
# ──────────────────────────────────────────────

@dataclass
class ValidationResult:
    is_valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def fail(self, reason: str) -> "ValidationResult":
        self.is_valid = False
        self.errors.append(reason)
        return self

    def warn(self, reason: str) -> "ValidationResult":
        self.warnings.append(reason)
        return self


# ──────────────────────────────────────────────
# 1. Security blocklist
# ──────────────────────────────────────────────

_BLOCKED_TOKENS: list[str] = [
    # DDL
    "DROP", "CREATE", "ALTER", "TRUNCATE", "RENAME",
    # DML
    "DELETE", "INSERT", "UPDATE", "MERGE", "REPLACE",
    # Execution
    "EXEC", "EXECUTE", "CALL", "SP_", "XP_",
    # Dangerous functions / operations
    "OPENROWSET", "OPENDATASOURCE", "OPENQUERY", "BULK",
    "LINKED SERVER", "DBCC", "RESTORE", "BACKUP",
    # Script injection
    "WAITFOR", "SLEEP", "BENCHMARK",
    "--", "/*",
    "SHUTDOWN", "RECONFIGURE", "KILL",
    # Stacked query attempt
    ";SELECT", ";DROP", ";INSERT", ";DELETE", ";UPDATE",
]

_BLOCKED_RE = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in _BLOCKED_TOKENS) + r")\b",
    re.IGNORECASE,
)

_SEMICOLON_RE = re.compile(r";(?!\s*$)")


def _check_security(sql: str, result: ValidationResult) -> None:
    match = _BLOCKED_RE.search(sql)

    if match:
        result.fail(f"Blocked token: '{match.group()}'")

    if _SEMICOLON_RE.search(sql):
        result.fail("Stacked queries detected (semicolon mid-statement)")

    if "--" in sql or "/*" in sql:
        result.fail("SQL comments are not permitted in generated queries")


# ──────────────────────────────────────────────
# 2. Structure checks
# ──────────────────────────────────────────────

_SELECT_START_RE = re.compile(r"^\s*(SELECT|WITH)\s", re.IGNORECASE)
_LIMIT_RE = re.compile(r"\bLIMIT\s+\d+", re.IGNORECASE)
_SELECT_STAR_RE = re.compile(r"SELECT\s+\*", re.IGNORECASE)
_TOP_RE = re.compile(r"\bTOP\s+\d+", re.IGNORECASE)


def _is_time_series_query(sql: str) -> bool:
    """Trend queries grouped or ordered by year/month/quarter do not need TOP."""
    s = sql.lower()

    has_time_group = bool(
        re.search(r"group\s+by[\s\S]*(\byear\b|\bmonth\b|\bquarter\b|dd\.year|dd\.month|dd\.quarter)", s)
    )

    has_time_order = bool(
        re.search(r"order\s+by[\s\S]*(\byear\b|\bmonth\b|\bquarter\b|dd\.year|dd\.month|dd\.quarter)", s)
    )

    return has_time_group or has_time_order


def _check_structure(sql: str, result: ValidationResult) -> None:
    if not _SELECT_START_RE.match(sql):
        result.fail("Query must start with SELECT or WITH")

    if _LIMIT_RE.search(sql):
        result.fail("LIMIT is not valid SQL Server syntax — use TOP N")

    if _SELECT_STAR_RE.search(sql):
        result.fail("SELECT * is forbidden — enumerate required columns")

    if not _TOP_RE.search(sql) and not _is_time_series_query(sql):
        result.warn("Query has no TOP clause — consider adding TOP 20 for ranking/list queries")


# ──────────────────────────────────────────────
# 3. View existence check
# ──────────────────────────────────────────────

_FROM_JOIN_RE = re.compile(
    r"\b(?:FROM|JOIN)\s+(\[?vw_\w+\]?)",
    re.IGNORECASE,
)


def _check_views(sql: str, result: ValidationResult) -> None:
    valid_views = get_all_valid_views()
    referenced = _FROM_JOIN_RE.findall(sql)

    for raw in referenced:
        vname = raw.strip("[]")

        if vname not in valid_views:
            result.fail(f"Unknown view: '{vname}' — not in schema")


# ──────────────────────────────────────────────
# 4. Column existence check (heuristic)
# ──────────────────────────────────────────────

_COL_RE = re.compile(
    r"(?:SELECT|,)\s+(?:TOP\s+\d+\s+)?(?:\w+\.)?([\w]+)\s*(?:AS\s+\w+)?",
    re.IGNORECASE,
)

_SQL_KEYWORDS = {
    "SUM", "COUNT", "AVG", "MAX", "MIN", "CAST", "CONVERT", "ISNULL",
    "COALESCE", "CASE", "WHEN", "THEN", "ELSE", "END", "DISTINCT",
    "TOP", "AS", "FROM", "WHERE", "AND", "OR", "NOT", "NULL", "INT",
    "VARCHAR", "DECIMAL", "FLOAT", "YEAR", "MONTH", "DAY", "DATEPART",
    "DATENAME", "GETDATE", "ROUND", "ABS", "LEN", "UPPER", "LOWER",
    "LTRIM", "RTRIM", "TRIM", "SUBSTRING", "CHARINDEX", "REPLACE",
    "STUFF", "IIF", "OVER", "PARTITION", "ORDER", "BY", "GROUP",
    "HAVING", "ON", "INNER", "LEFT", "RIGHT", "OUTER", "FULL",
    "CROSS", "APPLY", "EXISTS", "IN", "BETWEEN", "LIKE", "IS",
    "DESC", "ASC", "1", "100",
}


def _check_columns(sql: str, result: ValidationResult) -> None:
    valid_cols = get_all_valid_columns()
    found = _COL_RE.findall(sql)

    for col in found:
        if col.upper() in _SQL_KEYWORDS:
            continue

        if col.isdigit():
            continue

        if col not in valid_cols:
            result.warn(
                f"Column '{col}' was not found in schema — verify it exists"
            )


# ──────────────────────────────────────────────
# 5. GROUP BY completeness check
# ──────────────────────────────────────────────

_AGG_RE = re.compile(r"\b(SUM|COUNT|AVG|MAX|MIN)\s*\(", re.IGNORECASE)
_GROUP_BY_RE = re.compile(r"\bGROUP\s+BY\b", re.IGNORECASE)


def _check_group_by(sql: str, result: ValidationResult) -> None:
    has_agg = bool(_AGG_RE.search(sql))
    has_group_by = bool(_GROUP_BY_RE.search(sql))

    if has_agg and not has_group_by:
        if re.search(r"\bJOIN\b", sql, re.IGNORECASE):
            result.warn(
                "Aggregate with JOIN but no GROUP BY — verify this is intentional"
            )


# ──────────────────────────────────────────────
# 6. Public interface
# ──────────────────────────────────────────────

def validate_sql(sql: str) -> ValidationResult:
    """Run all validation stages and return a ValidationResult."""
    result = ValidationResult()

    _check_security(sql, result)

    if not result.is_valid:
        return result

    _check_structure(sql, result)
    _check_views(sql, result)
    _check_columns(sql, result)
    _check_group_by(sql, result)

    return result
