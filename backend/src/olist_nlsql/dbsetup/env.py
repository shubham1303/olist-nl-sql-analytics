"""Connection settings for the local database, read from the environment and ``.env``."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from psycopg.conninfo import make_conninfo

REPO_ROOT = Path(__file__).resolve().parents[4]

OWNER_ROLE = "olist_owner"
READER_ROLE = "analytics_reader"


def load_dotenv(path: Path = REPO_ROOT / ".env") -> None:
    """Load KEY=VALUE lines from ``path`` into ``os.environ`` without overriding.

    Deliberately minimal: no quoting, interpolation or export syntax.
    """
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def data_dir(env: Mapping[str, str] | None = None) -> Path:
    env = os.environ if env is None else env
    return Path(env.get("NLSQL_DATA_DIR", str(REPO_ROOT / "data" / "raw")))


class MissingSettingError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class LocalDb:
    host: str
    port: int
    dbname: str
    superuser: str
    superuser_password: str
    owner_password: str
    reader_password: str

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "LocalDb":
        env = os.environ if env is None else env

        def required(name: str) -> str:
            value = env.get(name, "")
            if not value:
                raise MissingSettingError(
                    f"{name} is not set. Copy .env.example to .env and fill it in."
                )
            return value

        return cls(
            # 127.0.0.1, not "localhost": the container port is bound to IPv4
            # loopback, and on Windows "localhost" tries ::1 first (~2 min stall).
            host=env.get("POSTGRES_HOST", "127.0.0.1"),
            port=int(env.get("POSTGRES_PORT", "5432")),
            dbname=env.get("POSTGRES_DB", "olist"),
            superuser=env.get("POSTGRES_USER", "postgres"),
            superuser_password=required("POSTGRES_PASSWORD"),
            owner_password=required("NLSQL_OWNER_PASSWORD"),
            reader_password=required("NLSQL_READER_PASSWORD"),
        )

    def _conninfo(self, user: str, password: str) -> str:
        return make_conninfo(
            host=self.host,
            port=self.port,
            dbname=self.dbname,
            user=user,
            password=password,
            application_name="olist-nlsql",
        )

    def superuser_conninfo(self) -> str:
        return self._conninfo(self.superuser, self.superuser_password)

    def owner_conninfo(self) -> str:
        return self._conninfo(OWNER_ROLE, self.owner_password)

    def reader_conninfo(self) -> str:
        return self._conninfo(READER_ROLE, self.reader_password)
