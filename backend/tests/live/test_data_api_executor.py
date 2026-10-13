"""The executor contract against Aurora through the RDS Data API: ``pytest -m live``.

Needs the deployed cluster (Phase 7) and AWS credentials that may call the Data API
with the analytics_reader secret. Configure ``NLSQL_DB_CLUSTER_ARN`` and
``NLSQL_DB_SECRET_ARN`` (``terraform output``). Skips when they aren't set. A paused
cluster is resumed first, which can take 20-90 s.
"""

import time

import pytest

from olist_nlsql.config import load_settings
from olist_nlsql.db import DatabaseResumingError
from olist_nlsql.db.data_api import DataApiExecutor
from olist_nlsql.dbsetup.env import load_dotenv
from tests.executor_contract import *  # noqa: F403 - pytest collects the contract tests

pytestmark = pytest.mark.live

RESUME_LIMIT_S = 180


@pytest.fixture(scope="module")
def executor() -> DataApiExecutor:
    load_dotenv()
    settings = load_settings()
    if not (settings.db_cluster_arn and settings.db_secret_arn):
        pytest.skip("NLSQL_DB_CLUSTER_ARN / NLSQL_DB_SECRET_ARN not set (deployed cluster only)")
    executor = DataApiExecutor(
        settings.db_cluster_arn,
        settings.db_secret_arn,
        settings.db_name,
        region=settings.aws_region,
    )
    deadline = time.monotonic() + RESUME_LIMIT_S
    while True:  # wake a paused cluster before the contract runs
        try:
            executor.execute("SELECT 1", max_rows=1)
            return executor
        except DatabaseResumingError:
            if time.monotonic() > deadline:
                pytest.fail(f"cluster did not resume within {RESUME_LIMIT_S} s")
            time.sleep(3)
