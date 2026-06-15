from __future__ import annotations

AGNO_TABLE_NAMES: dict[str, str] = {
    "session_table": "agno_sessions",
    "memory_table": "agno_memories",
    "metrics_table": "agno_metrics",
    "eval_table": "agno_evals",
    "versions_table": "agno_schema_versions",
    "schedules_table": "agno_schedules",
    "schedule_runs_table": "agno_schedule_runs",
}

AGNO_DATA_TABLES: tuple[str, ...] = (
    AGNO_TABLE_NAMES["schedule_runs_table"],
    AGNO_TABLE_NAMES["schedules_table"],
    AGNO_TABLE_NAMES["session_table"],
    AGNO_TABLE_NAMES["memory_table"],
    AGNO_TABLE_NAMES["metrics_table"],
    AGNO_TABLE_NAMES["eval_table"],
)
