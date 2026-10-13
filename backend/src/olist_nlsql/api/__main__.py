"""CLI: ``python -m olist_nlsql.api {serve,hash-code}``.

serve                 run the local API on 127.0.0.1:8000 (Docker Postgres + Bedrock)
serve --fake-sql SQL  answer every question with SQL (no Bedrock), for UI work
serve --simulate-resume 20   act like a paused Aurora cluster for the first 20 s
hash-code             read an access code and print the NLSQL_ACCESS_CODE_SHA256 line
"""

import argparse
import getpass
import logging
import sys

from olist_nlsql.api.handlers import Api, hash_access_code
from olist_nlsql.api.local_app import FixedSqlModel, SimulatedResume, serve
from olist_nlsql.config import ConfigError, load_settings
from olist_nlsql.db import QueryExecutor
from olist_nlsql.dbsetup.env import MissingSettingError, load_dotenv, reader_conninfo
from olist_nlsql.llm.client import ModelClient
from olist_nlsql.pipeline import NlSqlPipeline
from olist_nlsql.sqlsafety import SqlValidator


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="python -m olist_nlsql.api")
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("serve", help="run the local API (dev only)")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--fake-sql", help="answer every question with this SQL (no Bedrock)")
    s.add_argument(
        "--simulate-resume",
        type=float,
        default=0,
        metavar="SECONDS",
        help="report the database as resuming for this long after the first request",
    )
    sub.add_parser("hash-code", help="hash an access code for NLSQL_ACCESS_CODE_SHA256")
    args = parser.parse_args(argv)

    if args.command == "hash-code":
        code = getpass.getpass("Access code: ") if sys.stdin.isatty() else sys.stdin.readline()
        code = code.strip()
        if len(code) < 12:
            print("error: use at least 12 characters", file=sys.stderr)
            return 2
        print(f"NLSQL_ACCESS_CODE_SHA256={hash_access_code(code)}")
        return 0

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        settings = load_settings()
        from olist_nlsql.db.postgres import PostgresExecutor

        executor: QueryExecutor = PostgresExecutor(reader_conninfo())
    except (ConfigError, MissingSettingError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.simulate_resume > 0:
        executor = SimulatedResume(executor, args.simulate_resume)
    model: ModelClient
    if args.fake_sql:
        model = FixedSqlModel(args.fake_sql)
    else:
        from olist_nlsql.llm.bedrock import BedrockModelClient

        model = BedrockModelClient(settings)
    validator = SqlValidator.from_catalog(settings=settings)
    try:
        api = Api(settings, NlSqlPipeline(model, validator, executor, settings), executor)
        server = serve(api, args.host, args.port)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"local API on http://{args.host}:{args.port} (model: {model.model_id}); Ctrl+C stops")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
