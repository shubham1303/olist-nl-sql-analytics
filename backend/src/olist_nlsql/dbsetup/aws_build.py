"""Build the Aurora database through the RDS Data API (Phase 7, ADR 0001).

The same steps and SQL files as the local ``build``, adapted to the Data API:

1. upload the pinned CSVs to the private data bucket (``raw/<file>``),
2. bootstrap as the master user: the two roles with their passwords from Secrets
   Manager, the reader's session settings, database grants, and the ``aws_s3``
   extension for the owner,
3. rebuild as ``olist_owner``: raw tables, ``aws_s3.table_import_from_s3`` per CSV (the
   cluster reads S3 through its IAM role and the S3 gateway endpoint), constraints,
   ANALYZE, analytics views and grants.

The Data API runs one statement per call, so the SQL files are split here. A call
waits at most 45 s, but importing the largest CSV can take longer. Imports run with
``continueAfterTimeout`` and the row count is polled until it matches the pinned
count. Each import is one statement, so the count is 0 until it commits.

Unlike the local build this isn't one transaction. A failed run leaves a partial
schema, and running it again rebuilds from scratch.
"""

import json
import time
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Protocol

from olist_nlsql.dbsetup.build import (  # the same settings and files as the local build
    ANALYTICS_VIEWS_SQL,
    GRANTS_SQL,
    RAW_CONSTRAINTS_SQL,
    RAW_TABLES_SQL,
    READER_CONNECTION_LIMIT,
    READER_IDLE_IN_TRANSACTION_TIMEOUT,
    READER_STATEMENT_TIMEOUT,
)
from olist_nlsql.dbsetup.dataset import SOURCE_FILES, SourceFile, verify
from olist_nlsql.dbsetup.env import OWNER_ROLE, READER_ROLE

SQL_FILES = (RAW_TABLES_SQL, RAW_CONSTRAINTS_SQL)
VIEW_FILES = (ANALYTICS_VIEWS_SQL, GRANTS_SQL)
IMPORT_TIMEOUT_S = 600
RESUME_TIMEOUT_S = 240

Log = Callable[[str], None]


class DataClient(Protocol):
    def execute_statement(self, **kwargs: Any) -> Mapping[str, Any]: ...


class S3Client(Protocol):
    def upload_file(self, Filename: str, Bucket: str, Key: str) -> None: ...


class SecretsClient(Protocol):
    def get_secret_value(self, SecretId: str) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class AwsDb:
    cluster_arn: str
    master_secret_arn: str
    owner_secret_arn: str
    reader_secret_arn: str
    database: str
    bucket: str
    region: str

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "AwsDb":
        names = {
            "cluster_arn": "NLSQL_DB_CLUSTER_ARN",
            "master_secret_arn": "NLSQL_DB_MASTER_SECRET_ARN",
            "owner_secret_arn": "NLSQL_DB_OWNER_SECRET_ARN",
            "reader_secret_arn": "NLSQL_DB_SECRET_ARN",
            "bucket": "NLSQL_DATA_BUCKET",
        }
        missing = [v for v in names.values() if not env.get(v)]
        if missing:
            raise ValueError(f"set {', '.join(missing)} (from `terraform output`)")
        return cls(
            **{k: env[v] for k, v in names.items()},
            database=env.get("NLSQL_DB_NAME", "olist"),
            region=env.get("NLSQL_AWS_REGION", "us-east-1"),
        )


def split_statements(text: str) -> list[str]:
    """Split SQL on top-level ';', respecting quotes and comments (no $$ bodies here)."""
    statements: list[str] = []
    current: list[str] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "-" and text.startswith("--", i):
            end = text.find("\n", i)
            i = n if end < 0 else end  # drop the comment, keep the newline
            continue
        if ch == "/" and text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        if ch in ("'", '"'):
            j = i + 1
            while j < n:
                if text[j] == ch:
                    if j + 1 < n and text[j + 1] == ch:  # doubled quote escapes itself
                        j += 2
                        continue
                    break
                j += 1
            current.append(text[i : j + 1])
            i = j + 1
            continue
        if ch == ";":
            statements.append("".join(current))
            current = []
        else:
            current.append(ch)
        i += 1
    statements.append("".join(current))
    return [s.strip() for s in statements if s.strip()]


def literal(value: str) -> str:
    """A SQL string literal. Only used for passwords and S3 names from our own config."""
    return "'" + value.replace("'", "''") + "'"


def read_sql(name: str) -> str:
    return resources.files("olist_nlsql.dbsetup").joinpath("sql", name).read_text(encoding="utf-8")


class AwsBuilder:
    def __init__(
        self,
        db: AwsDb,
        data: DataClient,
        s3: S3Client,
        secrets: SecretsClient,
        log: Log = print,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.db, self.data, self.s3, self.secrets = db, data, s3, secrets
        self.log, self.sleep, self.clock = log, sleep, clock

    # Data API

    def run(self, secret_arn: str, sql: str, *, long: bool = False) -> Mapping[str, Any]:
        """One statement. ``long``: let it finish on the server after the call times out."""
        deadline = self.clock() + RESUME_TIMEOUT_S
        while True:
            try:
                return self.data.execute_statement(
                    resourceArn=self.db.cluster_arn,
                    secretArn=secret_arn,
                    database=self.db.database,
                    sql=sql,
                    continueAfterTimeout=long,
                )
            except Exception as exc:
                code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
                if code == "DatabaseResumingException" and self.clock() < deadline:
                    self.log("  database resuming, waiting...")
                    self.sleep(5)
                    continue
                if code == "StatementTimeoutException" and long:
                    return {}  # still running on the server; the caller verifies
                raise

    def scalar(self, secret_arn: str, sql: str) -> int:
        records = self.run(secret_arn, sql).get("records") or [[{"longValue": 0}]]
        field = records[0][0]
        return int(field.get("longValue", field.get("stringValue", 0)))

    def statements(self, secret_arn: str, names: tuple[str, ...]) -> None:
        for name in names:
            for statement in split_statements(read_sql(name)):
                self.run(secret_arn, statement, long=True)

    # steps

    def upload(self, data_dir: Path) -> None:
        verify(data_dir)
        for source in SOURCE_FILES:
            self.s3.upload_file(str(data_dir / source.filename), self.db.bucket, _key(source))
            self.log(f"  s3://{self.db.bucket}/{_key(source)}")

    def password(self, secret_arn: str) -> str:
        secret = json.loads(self.secrets.get_secret_value(SecretId=secret_arn)["SecretString"])
        return str(secret["password"])

    def bootstrap_statements(self) -> Iterator[str]:
        owner_pw = self.password(self.db.owner_secret_arn)
        reader_pw = self.password(self.db.reader_secret_arn)
        for role, pw in ((OWNER_ROLE, owner_pw), (READER_ROLE, reader_pw)):
            options = (
                f"LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD {literal(pw)}"
            )
            # role names are constants; the password goes through literal()
            yield (
                f"DO $do$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') "  # noqa: S608
                f"THEN ALTER ROLE {role} WITH {options}; "
                f"ELSE CREATE ROLE {role} WITH {options}; END IF; END $do$"
            )
        yield f"ALTER ROLE {READER_ROLE} CONNECTION LIMIT {READER_CONNECTION_LIMIT}"
        yield f"ALTER ROLE {READER_ROLE} SET default_transaction_read_only = on"
        yield f"ALTER ROLE {READER_ROLE} SET statement_timeout = '{READER_STATEMENT_TIMEOUT}'"
        yield (
            f"ALTER ROLE {READER_ROLE} SET idle_in_transaction_session_timeout = "
            f"'{READER_IDLE_IN_TRANSACTION_TIMEOUT}'"
        )
        yield f"ALTER ROLE {READER_ROLE} SET search_path = analytics"
        database = self.db.database
        yield f"REVOKE ALL ON DATABASE {database} FROM PUBLIC"
        yield f"GRANT CONNECT, CREATE ON DATABASE {database} TO {OWNER_ROLE}"
        yield f"GRANT CONNECT ON DATABASE {database} TO {READER_ROLE}"
        yield "REVOKE ALL ON SCHEMA public FROM PUBLIC"
        # aws_s3 needs rds_superuser to install; the owner only gets to call it
        yield "CREATE EXTENSION IF NOT EXISTS aws_s3 CASCADE"
        yield f"GRANT USAGE ON SCHEMA aws_s3, aws_commons TO {OWNER_ROLE}"
        yield f"GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA aws_s3, aws_commons TO {OWNER_ROLE}"

    def bootstrap(self) -> None:
        self.log("bootstrap: roles, settings, grants, aws_s3 (as master)")
        for statement in self.bootstrap_statements():
            self.run(self.db.master_secret_arn, statement)

    def import_sql(self, source: SourceFile) -> str:
        return (
            f"SELECT aws_s3.table_import_from_s3('raw.{source.table}', '', "
            "'(format csv, header true, encoding ''UTF8'')', "
            f"aws_commons.create_s3_uri({literal(self.db.bucket)}, {literal(_key(source))}, "
            f"{literal(self.db.region)}))"
        )

    def load(self, source: SourceFile) -> None:
        owner = self.db.owner_secret_arn
        self.run(owner, self.import_sql(source), long=True)
        count_sql = f"SELECT count(*) FROM raw.{source.table}"  # noqa: S608 - pinned table names
        deadline = self.clock() + IMPORT_TIMEOUT_S
        while (loaded := self.scalar(owner, count_sql)) != source.rows:
            if loaded > source.rows or self.clock() > deadline:
                raise RuntimeError(f"raw.{source.table}: {loaded} rows, expected {source.rows}")
            self.sleep(5)
        self.log(f"  raw.{source.table}: {loaded:,} rows")

    def build(self, data_dir: Path) -> None:
        self.log("upload: CSVs to S3")
        self.upload(data_dir)
        self.bootstrap()
        owner = self.db.owner_secret_arn
        self.log("build: raw schema (as olist_owner)")
        for schema in ("analytics", "analytics_internal", "raw"):
            self.run(owner, f"DROP SCHEMA IF EXISTS {schema} CASCADE", long=True)
        self.statements(owner, SQL_FILES[:1])
        for source in SOURCE_FILES:
            self.load(source)
        self.log("build: raw constraints, ANALYZE")
        self.statements(owner, SQL_FILES[1:])
        self.run(owner, "ANALYZE", long=True)
        self.views()
        self.log("build: done")

    def views(self) -> None:
        self.log("views: analytics views and grants")
        owner = self.db.owner_secret_arn
        for schema in ("analytics", "analytics_internal"):
            self.run(owner, f"DROP SCHEMA IF EXISTS {schema} CASCADE", long=True)
        self.statements(owner, VIEW_FILES)


def _key(source: SourceFile) -> str:
    return f"raw/{source.filename}"


def builder_from_env(env: Mapping[str, str], log: Log = print) -> AwsBuilder:
    import boto3

    db = AwsDb.from_env(env)
    session = boto3.Session(region_name=db.region)
    return AwsBuilder(
        db,
        data=session.client("rds-data"),  # type: ignore[arg-type]
        s3=session.client("s3"),
        secrets=session.client("secretsmanager"),
        log=log,
    )
