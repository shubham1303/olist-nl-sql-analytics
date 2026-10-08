"""Local command line for the NL-to-SQL pipeline.

python -m olist_nlsql ask "What was merchandise revenue in 2017?"
python -m olist_nlsql ask "..." --json
python -m olist_nlsql ask "..." --fake-sql "SELECT SUM(revenue) FROM orders"
python -m olist_nlsql prompt --stats
"""

import argparse
import json
import logging
import sys
from collections.abc import Sequence

from olist_nlsql.config import ConfigError, Settings, load_settings
from olist_nlsql.db.postgres import PostgresExecutor
from olist_nlsql.dbsetup.env import MissingSettingError, load_dotenv, reader_conninfo
from olist_nlsql.llm.bedrock import BedrockModelClient
from olist_nlsql.llm.client import ModelClient, ModelRequest
from olist_nlsql.llm.fake import FakeModelClient, reply_json
from olist_nlsql.llm.output import OUTPUT_SCHEMA
from olist_nlsql.llm.prompts import PROMPT_VERSION, prompt_stats, question_message, system_prompt
from olist_nlsql.pipeline import NlSqlPipeline, PipelineResult, to_dict
from olist_nlsql.sqlsafety import SqlValidator

MAX_DISPLAY_ROWS = 25


def _table(result: PipelineResult) -> str:
    headers = [c.name for c in result.columns]
    shown = [["" if v is None else str(v) for v in row] for row in result.rows[:MAX_DISPLAY_ROWS]]
    widths = [max([len(h)] + [len(r[i]) for r in shown]) for i, h in enumerate(headers)]
    lines = [
        "  ".join(h.ljust(w) for h, w in zip(headers, widths, strict=True)),
        "  ".join("-" * w for w in widths),
    ]
    lines += ["  ".join(v.ljust(w) for v, w in zip(r, widths, strict=True)) for r in shown]
    if result.row_count > MAX_DISPLAY_ROWS:
        lines.append(f"... {result.row_count - MAX_DISPLAY_ROWS} more rows (use --json for all)")
    return "\n".join(lines)


def render_text(result: PipelineResult) -> str:
    out = [f"Question:       {result.question}", f"Status:         {result.status}"]
    if result.interpretation:
        out.append(f"Interpretation: {result.interpretation}")
    if result.assumptions:
        out.append("Assumptions:")
        out.extend(f"  - {a}" for a in result.assumptions)
    if result.metrics_used:
        out.append(f"Metrics:        {', '.join(result.metrics_used)}")
    source = result.answer_source or "-"
    out.append(
        f"Repair:         {'yes' if result.repair_attempted else 'no'} (answer from {source})"
    )
    if result.validated_sql:
        out += ["", "Validated SQL (executed):", result.validated_sql]
    elif result.generated_sql:
        out += ["", "Generated SQL (not executed):", result.generated_sql]
    if result.error:
        out += ["", f"Error [{result.error.stage} / {result.error.code}]: {result.error.message}"]
    if result.status == "answered":
        truncated = " (truncated)" if result.truncated else ""
        out += ["", f"Result: {result.row_count} rows{truncated}", _table(result)]
    for warning in result.warnings:
        out.append(f"Warning: {warning}")
    t = result.timings
    parts = [
        f"prompt {t.prompt_build_ms:.1f}",
        f"model {t.model_generation_ms:.0f}",
        f"repair {t.repair_generation_ms:.0f}" if t.repair_generation_ms is not None else None,
        f"validation {t.validation_ms:.1f}",
        f"execution {t.execution_ms:.1f}" if t.execution_ms is not None else None,
        f"total {t.total_ms:.0f}",
    ]
    out += ["", "Timings (ms):   " + " | ".join(p for p in parts if p)]
    out.append(f"Model:          {result.model_id} (prompt {result.prompt_version})")
    return "\n".join(out)


def _model(settings: Settings, fake_sql: Sequence[str] | None) -> ModelClient:
    if fake_sql:
        replies = [
            reply_json(sql, interpretation="Offline run with --fake-sql.") for sql in fake_sql
        ]
        return FakeModelClient(list(replies), model_id="fake (--fake-sql)")
    return BedrockModelClient(settings)


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="python -m olist_nlsql")
    sub = parser.add_subparsers(dest="command", required=True)
    ask = sub.add_parser("ask", help="answer a question end to end")
    ask.add_argument("question")
    ask.add_argument("--json", action="store_true", help="print the result as JSON")
    ask.add_argument("--show-prompt", action="store_true", help="print the model request first")
    ask.add_argument(
        "--fake-sql",
        action="append",
        metavar="SQL",
        help="skip Bedrock: use this SQL as the model's reply (repeat to script a repair)",
    )
    prompt = sub.add_parser("prompt", help="print the system prompt")
    prompt.add_argument("--stats", action="store_true", help="print section sizes only")
    args = parser.parse_args(argv)

    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.command == "prompt":
        if args.stats:
            print(
                json.dumps({"prompt_version": PROMPT_VERSION, **prompt_stats(settings)}, indent=2)
            )
        else:
            print(system_prompt(settings))
        return 0

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    try:
        executor = PostgresExecutor(reader_conninfo())
    except MissingSettingError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    model = _model(settings, args.fake_sql)
    if args.show_prompt:
        request = ModelRequest(
            system_prompt(settings), question_message(args.question), OUTPUT_SCHEMA
        )
        print(f"--- system ({len(request.system)} chars) ---\n{request.system}")
        print(f"--- user ---\n{request.user}\n--- end of prompt ---\n")
    pipeline = NlSqlPipeline(
        model, SqlValidator.from_catalog(settings=settings), executor, settings
    )
    result = pipeline.ask(args.question)
    if args.json:
        print(json.dumps(to_dict(result), indent=2, default=str))
    else:
        print(render_text(result))
    return 0 if result.status in ("answered", "unanswerable") else 1
