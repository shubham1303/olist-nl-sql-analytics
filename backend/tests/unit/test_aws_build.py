"""The Aurora build through the Data API, against fake AWS clients (no AWS)."""

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
import sqlglot
from botocore.exceptions import ClientError

from olist_nlsql.dbsetup import aws_build
from olist_nlsql.dbsetup.aws_build import AwsBuilder, AwsDb, literal, read_sql, split_statements
from olist_nlsql.dbsetup.dataset import SOURCE_FILES

DB = AwsDb(
    cluster_arn="arn:aws:rds:us-east-1:ACCOUNT:cluster:olist",
    master_secret_arn="master",  # noqa: S106 - a fake secret ARN
    owner_secret_arn="owner",  # noqa: S106 - a fake secret ARN
    reader_secret_arn="reader",  # noqa: S106 - a fake secret ARN
    database="olist",
    bucket="olist-data",
    region="us-east-1",
)
ROWS = {s.table: s.rows for s in SOURCE_FILES}


def error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": code}}, "ExecuteStatement")


@dataclass
class FakeData:
    """Records statements; counts report the pinned rows once a table was imported."""

    fail_first: dict[str, str] = field(default_factory=dict)  # sql substring -> error code
    wrong_count: str | None = None
    calls: list[tuple[str, str, bool]] = field(default_factory=list)
    imported: set[str] = field(default_factory=set)

    def execute_statement(self, **kw: Any) -> Mapping[str, Any]:
        sql, secret = kw["sql"], kw["secretArn"]
        self.calls.append((secret, sql, kw.get("continueAfterTimeout", False)))
        for marker, code in list(self.fail_first.items()):
            if marker in sql:
                del self.fail_first[marker]
                if code != "StatementTimeoutException":
                    raise error(code)
                if (m := re.search(r"'raw\.(\w+)'", sql)) is not None:
                    self.imported.add(m.group(1))  # it keeps running on the server
                raise error(code)
        if (m := re.search(r"'raw\.(\w+)'", sql)) is not None:
            self.imported.add(m.group(1))
        if (m := re.match(r"SELECT count\(\*\) FROM raw\.(\w+)", sql)) is not None:
            table = m.group(1)
            rows = ROWS[table] + 1 if table == self.wrong_count else ROWS[table]
            return {"records": [[{"longValue": rows if table in self.imported else 0}]]}
        return {}


@dataclass
class FakeS3:
    uploads: list[tuple[str, str]] = field(default_factory=list)

    def upload_file(self, Filename: str, Bucket: str, Key: str) -> None:
        self.uploads.append((Bucket, Key))


@dataclass
class FakeSecrets:
    def get_secret_value(self, SecretId: str) -> Mapping[str, Any]:
        return {"SecretString": json.dumps({"username": SecretId, "password": f"pw'{SecretId}"})}


def builder(data: FakeData, s3: FakeS3 | None = None) -> AwsBuilder:
    return AwsBuilder(
        DB, data, s3 or FakeS3(), FakeSecrets(), log=lambda _: None, sleep=lambda _: None
    )


@pytest.mark.parametrize(
    "name",
    ["010_raw_tables.sql", "020_raw_constraints.sql", "030_analytics_views.sql", "040_grants.sql"],
)
def test_sql_files_split_into_statements_that_each_parse(name: str) -> None:
    statements = split_statements(read_sql(name))
    assert statements
    for statement in statements:
        assert not statement.endswith(";")
        assert len(sqlglot.parse(statement, read="postgres")) == 1


def test_splitter_respects_quotes_and_comments() -> None:
    text = "SELECT 'a;b' AS \"x;y\"; -- comment; here\n/* block; */ SELECT 2;\n\n"
    assert split_statements(text) == ["SELECT 'a;b' AS \"x;y\"", "SELECT 2"]


def test_literal_escapes_quotes() -> None:
    assert literal("it's") == "'it''s'"


def test_build_order_secrets_and_imports(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(aws_build, "verify", lambda _d: None)
    data, s3 = FakeData(), FakeS3()
    builder(data, s3).build(tmp_path)

    assert s3.uploads == [("olist-data", f"raw/{s.filename}") for s in SOURCE_FILES]
    secrets = [secret for secret, _, _ in data.calls]
    first_owner = secrets.index("owner")
    assert set(secrets[:first_owner]) == {"master"}  # bootstrap first, as master
    assert set(secrets[first_owner:]) == {"owner"}  # everything else as olist_owner
    sqls = [sql for _, sql, _ in data.calls]
    assert "CREATE EXTENSION IF NOT EXISTS aws_s3 CASCADE" in sqls
    assert any("PASSWORD 'pw''owner'" in s for s in sqls)  # quoted, never raw
    imports = [s for s in sqls if "table_import_from_s3" in s]
    assert len(imports) == len(SOURCE_FILES)
    assert (
        "aws_commons.create_s3_uri('olist-data', 'raw/olist_orders_dataset.csv', 'us-east-1')"
        in imports[2]
    )
    # constraints and views come after every import
    last_import = max(i for i, s in enumerate(sqls) if "table_import_from_s3" in s)
    assert sqls.index("ANALYZE") > last_import
    assert any(
        s.startswith("GRANT SELECT ON ALL TABLES IN SCHEMA analytics") for s in sqls[last_import:]
    )


def test_import_that_outlives_the_call_is_verified_by_count(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(aws_build, "verify", lambda _d: None)
    data = FakeData(fail_first={"'raw.geolocation'": "StatementTimeoutException"})
    builder(data).build(tmp_path)
    assert "geolocation" in data.imported


def test_wrong_row_count_stops_the_build(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(aws_build, "verify", lambda _d: None)
    with pytest.raises(RuntimeError, match=r"raw\.orders: .* expected 99441"):
        builder(FakeData(wrong_count="orders")).build(tmp_path)


def test_a_paused_cluster_is_waited_for() -> None:
    data = FakeData(fail_first={"SELECT 1": "DatabaseResumingException"})
    builder(data).run("owner", "SELECT 1")
    assert [sql for _, sql, _ in data.calls] == ["SELECT 1", "SELECT 1"]


def test_other_errors_are_not_retried() -> None:
    data = FakeData(fail_first={"SELECT 1": "BadRequestException"})
    with pytest.raises(ClientError):
        builder(data).run("owner", "SELECT 1")
    assert len(data.calls) == 1


def test_settings_come_from_terraform_outputs() -> None:
    env = {
        "NLSQL_DB_CLUSTER_ARN": "c",
        "NLSQL_DB_MASTER_SECRET_ARN": "m",
        "NLSQL_DB_OWNER_SECRET_ARN": "o",
        "NLSQL_DB_SECRET_ARN": "r",
        "NLSQL_DATA_BUCKET": "b",
    }
    db = AwsDb.from_env(env)
    assert (db.cluster_arn, db.reader_secret_arn, db.database) == ("c", "r", "olist")
    with pytest.raises(ValueError, match="NLSQL_DATA_BUCKET"):
        AwsDb.from_env({k: v for k, v in env.items() if k != "NLSQL_DATA_BUCKET"})
