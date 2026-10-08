"""CLI: ``python -m olist_nlsql.evaluation {check,snapshot,show,verify,run,report}``.

check                          structure + every reference SQL passes the validator
snapshot --split dev           run reference SQL, store results (needs the database)
show --split dev ID...         print items for review
verify --split dev --by NAME ID...   record that a person checked SQL and result
run --split dev                run the pipeline on a split, write a run record
run --split test --checkpoint "why"  held-out run (always recorded)
report RESULTS.json            (re)write the markdown report, applying triage
"""

import argparse
import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path

from olist_nlsql.config import ConfigError, load_settings
from olist_nlsql.db import QueryExecutor
from olist_nlsql.dbsetup.env import MissingSettingError, load_dotenv, reader_conninfo
from olist_nlsql.evaluation import benchmark as bm
from olist_nlsql.evaluation import report, runner
from olist_nlsql.evaluation.compare import Table
from olist_nlsql.llm.client import ModelClient
from olist_nlsql.sqlsafety import SqlValidator

MAX_SHOW_ROWS = 20


def _validator() -> SqlValidator:
    return SqlValidator.from_catalog(settings=load_settings())


def check(benchmarks: dict[bm.Split, bm.Benchmark]) -> list[str]:
    """Problems that make a benchmark unusable. Empty means fine."""
    validator = _validator()
    problems = []
    for split, benchmark in benchmarks.items():
        expected = bm.EXPECTED_SIZES[split]
        if len(benchmark.items) != expected:
            problems.append(f"{split}: {len(benchmark.items)} items, ADR 0006 expects {expected}")
        for item in benchmark.items:
            result = validator.validate(item.reference_sql)
            if not result.ok:
                errors = "; ".join(f"{e.code}: {e.message}" for e in result.errors)
                problems.append(f"{item.id}: reference SQL rejected by the validator: {errors}")
    return problems


def _executor() -> QueryExecutor:
    from olist_nlsql.db.postgres import PostgresExecutor  # local driver, dev only

    return PostgresExecutor(reader_conninfo())


def snapshot_item(
    item: bm.BenchmarkItem, validator: SqlValidator, executor: QueryExecutor
) -> bm.BenchmarkItem:
    validation = validator.validate(item.reference_sql)
    if not validation.ok or validation.sql is None:
        raise bm.BenchmarkError(f"{item.id}: reference SQL rejected: {validation.codes}")
    data = executor.execute(validation.sql, max_rows=load_settings().max_result_rows)
    if data.truncated:
        raise bm.BenchmarkError(f"{item.id}: reference result is truncated; narrow the question")
    return item.with_result(Table(data.columns, data.rows))


def _table(result: Table | None) -> str:
    if result is None:
        return "  (no snapshot yet)"
    headers = [f"{c.name} ({c.type})" for c in result.columns]
    rows = [["NULL" if v is None else str(v) for v in r] for r in result.rows[:MAX_SHOW_ROWS]]
    widths = [max([len(h)] + [len(r[i]) for r in rows]) for i, h in enumerate(headers)]
    out = ["  " + "  ".join(h.ljust(w) for h, w in zip(headers, widths, strict=True))]
    out += ["  " + "  ".join(v.ljust(w) for v, w in zip(r, widths, strict=True)) for r in rows]
    if len(result.rows) > MAX_SHOW_ROWS:
        out.append(f"  ... {len(result.rows) - MAX_SHOW_ROWS} more rows")
    return "\n".join(out)


def show(item: bm.BenchmarkItem) -> str:
    state = (
        f"verified by {item.verified_by} on {item.verified_on}"
        if item.verified
        else "STALE: changed after verification"
        if item.verification_stale
        else "not verified"
    )
    compare = item.compare
    parts = [
        f"== {item.id} [{item.difficulty}; {', '.join(item.tags)}] {state}",
        f"Q: {item.question}",
    ]
    if item.notes:
        parts.append(f"Notes: {item.notes}")
    parts += [
        f"Compare: order_matters={compare.order_matters} abs_tol={compare.abs_tol} "
        f"rel_tol={compare.rel_tol} extra_columns={'ok' if compare.allow_extra_columns else 'no'} "
        f"percent={'ok' if compare.allow_percent else 'no'}",
        "SQL:",
        "\n".join("  " + line for line in item.reference_sql.splitlines()),
        f"Result ({len(item.reference_result.rows) if item.reference_result else 0} rows):",
        _table(item.reference_result),
    ]
    return "\n".join(parts)


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="python -m olist_nlsql.evaluation")
    parser.add_argument("--benchmark-dir", type=Path, default=bm.BENCHMARK_DIR)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="validate the benchmark files (no database needed)")
    for name, helptext in (("snapshot", "store reference results"), ("show", "print items")):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("--split", choices=bm.SPLITS, required=True)
        p.add_argument("ids", nargs="*", help="item ids (default: all)")
    v = sub.add_parser("verify", help="mark items as human-verified")
    v.add_argument("--split", choices=bm.SPLITS, required=True)
    v.add_argument("--by", required=True, help="who checked the SQL and the result")
    v.add_argument("ids", nargs="+")
    r = sub.add_parser("run", help="run the pipeline over a split")
    r.add_argument("--split", choices=bm.SPLITS, required=True)
    r.add_argument("--checkpoint", help="required for --split test: why this held-out run")
    r.add_argument(
        "--fake-reference",
        action="store_true",
        help="harness self-test: the 'model' answers with the reference SQL (no Bedrock)",
    )
    r.add_argument("--results-dir", type=Path, default=runner.RESULTS_DIR)
    r.add_argument("ids", nargs="*", help="only these items (default: all)")
    rep = sub.add_parser("report", help="write the markdown report for a run record")
    rep.add_argument("record", type=Path)
    rep.add_argument("--triage", type=Path, help="default: eval/triage/<run_id>.yaml")
    args = parser.parse_args(argv)

    try:
        if args.command == "check":
            benchmarks = bm.load_all(args.benchmark_dir)
            problems = check(benchmarks)
            for split, b in benchmarks.items():
                stale = sum(i.verification_stale for i in b.items)
                print(
                    f"{split}: {len(b.items)} items, {b.verified_count} verified"
                    + (f", {stale} STALE" if stale else "")
                )
            for problem in problems:
                print(f"problem: {problem}", file=sys.stderr)
            return 1 if problems else 0

        if args.command == "report":
            record = runner.from_json(args.record.read_text(encoding="utf-8"))
            triage = report.load_triage(args.triage or report.triage_path(record), record)
            md = args.record.with_suffix(".md")
            md.write_text(report.render(record, triage), encoding="utf-8")
            print(f"wrote {md}")
            return 0

        return _split_command(args, bm.load(args.split, args.benchmark_dir))
    except (bm.BenchmarkError, report.TriageError, ConfigError, MissingSettingError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _split_command(args: argparse.Namespace, benchmark: bm.Benchmark) -> int:
    if args.command == "show":
        items = [benchmark.item(i) for i in args.ids] if args.ids else benchmark.items
        print("\n\n".join(show(i) for i in items))
        return 0

    if args.command == "snapshot":
        validator, executor = _validator(), _executor()
        for item_id in args.ids or [i.id for i in benchmark.items]:
            old = benchmark.item(item_id)
            new = snapshot_item(old, validator, executor)
            if old.verified and not new.verified:
                print(f"{item_id}: result CHANGED, verification cleared")
            elif new.reference_result != old.reference_result:
                print(f"{item_id}: snapshot updated")
            benchmark = benchmark.replace_item(new)
        print(f"wrote {bm.save(benchmark)}")
        return 0

    if args.command == "verify":
        for item_id in args.ids:
            benchmark = benchmark.replace_item(
                benchmark.item(item_id).verify(args.by, date.today())
            )
        print(f"verified {len(args.ids)} item(s); wrote {bm.save(benchmark)}")
        return 0

    # run
    settings = load_settings()
    model_for: Callable[[bm.BenchmarkItem], ModelClient]
    if args.fake_reference:
        model_for = runner.reference_model
    else:
        from olist_nlsql.llm.bedrock import BedrockModelClient

        client = BedrockModelClient(settings)

        def model_for(_item: bm.BenchmarkItem) -> ModelClient:
            return client

    record = runner.run(
        benchmark,
        model_for=model_for,
        executor=_executor(),
        settings=settings,
        checkpoint=args.checkpoint,
        ids=args.ids,
        progress=lambda o: print(
            f"{o.id}: {o.status}, correct={o.correct} ({o.category})", flush=True
        ),
    )
    path = runner.save(record, args.results_dir)
    md = path.with_suffix(".md")
    md.write_text(report.render(record), encoding="utf-8")
    c = record.summary["counts"]
    print(f"\nscored {record.summary['scored']}: correct {c['correct']}")
    print(f"wrote {path}\nwrote {md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
