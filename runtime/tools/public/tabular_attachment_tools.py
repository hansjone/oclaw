from __future__ import annotations

from typing import Any

from oclaw.platform.files.tabular_attachment_store import (
    aggregate_table,
    analyze_table_full_scan,
    query_table,
    run_table_sql,
)
from oclaw.runtime.tools.base import ToolSpec


def query_tabular_attachment_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        table_id = str(args.get("table_id") or "").strip()
        if not table_id:
            return {"ok": False, "error": "table_id_required"}
        raw_cols = args.get("columns")
        cols = [str(x) for x in raw_cols] if isinstance(raw_cols, list) else None
        sheet = str(args.get("sheet") or "").strip() or None
        where_contains = args.get("where_contains") if isinstance(args.get("where_contains"), dict) else None
        aggregate = args.get("aggregate") if isinstance(args.get("aggregate"), dict) else None
        if aggregate:
            return aggregate_table(
                table_id=table_id,
                metric=str(aggregate.get("metric") or ""),
                target_column=str(aggregate.get("target_column") or "").strip() or None,
                group_by=str(aggregate.get("group_by") or "").strip() or None,
                where_contains=where_contains,
                top_n=int(aggregate.get("top_n") or 20),
                sheet=sheet,
            )
        return query_table(
            table_id=table_id,
            columns=cols,
            limit=int(args.get("limit") or 50),
            offset=int(args.get("offset") or 0),
            where_contains=where_contains,
            sheet=sheet,
        )

    return ToolSpec(
        name="query_tabular_attachment",
        description="Query rows from a large uploaded table by table_id with optional column selection and keyword filter.",
        parameters={
            "type": "object",
            "properties": {
                "table_id": {"type": "string"},
                "sheet": {"type": "string"},
                "columns": {"type": "array", "items": {"type": "string"}},
                "limit": {"type": "integer", "minimum": 1, "maximum": 200},
                "offset": {"type": "integer", "minimum": 0},
                "where_contains": {
                    "type": "object",
                    "properties": {
                        "column": {"type": "string"},
                        "keyword": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
                "aggregate": {
                    "type": "object",
                    "properties": {
                        "metric": {"type": "string", "enum": ["count", "sum", "avg"]},
                        "target_column": {"type": "string"},
                        "group_by": {"type": "string"},
                        "top_n": {"type": "integer", "minimum": 1, "maximum": 200},
                    },
                    "required": ["metric"],
                    "additionalProperties": False,
                },
            },
            "required": ["table_id"],
            "additionalProperties": False,
        },
        handler=handler,
        read_only=True,
    )


def run_tabular_sql_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        table_id = str(args.get("table_id") or "").strip()
        sql = str(args.get("sql") or "").strip()
        sheet = str(args.get("sheet") or "").strip() or None
        if not table_id:
            return {"ok": False, "error": "table_id_required"}
        return run_table_sql(
            table_id=table_id,
            sql=sql,
            limit=int(args.get("limit") or 200),
            sheet=sheet,
        )

    return ToolSpec(
        name="run_tabular_sql",
        description="Run a READ-ONLY SQL query against uploaded table by table_id. Only SELECT/WITH allowed.",
        parameters={
            "type": "object",
            "properties": {
                "table_id": {"type": "string"},
                "sheet": {"type": "string"},
                "sql": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 500},
            },
            "required": ["table_id", "sql"],
            "additionalProperties": False,
        },
        handler=handler,
        read_only=True,
    )


def analyze_tabular_attachment_full_scan_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        table_id = str(args.get("table_id") or "").strip()
        if not table_id:
            return {"ok": False, "error": "table_id_required"}
        raw_cols = args.get("columns")
        cols = [str(x) for x in raw_cols] if isinstance(raw_cols, list) else None
        sheet = str(args.get("sheet") or "").strip() or None
        return analyze_table_full_scan(
            table_id=table_id,
            columns=cols,
            sheet=sheet,
            top_values_limit=int(args.get("top_values_limit") or 3),
        )

    return ToolSpec(
        name="analyze_tabular_attachment_full_scan",
        description="Run a full-table scan for selected columns and return concise profiling stats with audit evidence.",
        parameters={
            "type": "object",
            "properties": {
                "table_id": {"type": "string"},
                "sheet": {"type": "string"},
                "columns": {"type": "array", "items": {"type": "string"}},
                "top_values_limit": {"type": "integer", "minimum": 0, "maximum": 10},
            },
            "required": ["table_id"],
            "additionalProperties": False,
        },
        handler=handler,
        read_only=True,
    )


__all__ = ["query_tabular_attachment_tool", "run_tabular_sql_tool", "analyze_tabular_attachment_full_scan_tool"]
