from pathlib import Path

import pytest

from olist_nlsql.dbsetup.dataset import SOURCE_FILES, DatasetError, sha256_of, verify
from olist_nlsql.dbsetup.env import LocalDb, MissingSettingError, load_dotenv


def test_manifest_covers_all_nine_source_files() -> None:
    assert len(SOURCE_FILES) == 9
    assert len({s.table for s in SOURCE_FILES}) == 9
    assert all(len(s.sha256) == 64 for s in SOURCE_FILES)


def test_verify_reports_missing_files(tmp_path: Path) -> None:
    with pytest.raises(DatasetError, match="missing"):
        verify(tmp_path)


def test_verify_reports_checksum_mismatch(tmp_path: Path) -> None:
    for source in SOURCE_FILES:
        (tmp_path / source.filename).write_text("tampered")
    with pytest.raises(DatasetError, match="checksum mismatch"):
        verify(tmp_path)


def test_sha256_of(tmp_path: Path) -> None:
    path = tmp_path / "f"
    path.write_bytes(b"abc")
    assert sha256_of(path) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_dotenv_does_not_override_existing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("# comment\nNLSQL_TEST_A=from_file\nNLSQL_TEST_B=from_file\n\n")
    monkeypatch.setenv("NLSQL_TEST_A", "from_env")
    monkeypatch.delenv("NLSQL_TEST_B", raising=False)
    load_dotenv(env_file)
    import os

    assert os.environ["NLSQL_TEST_A"] == "from_env"
    assert os.environ["NLSQL_TEST_B"] == "from_file"
    monkeypatch.delenv("NLSQL_TEST_B")


def test_local_db_requires_passwords() -> None:
    with pytest.raises(MissingSettingError, match="POSTGRES_PASSWORD"):
        LocalDb.from_env({})


def test_local_db_defaults_to_ipv4_loopback() -> None:
    db = LocalDb.from_env(
        {"POSTGRES_PASSWORD": "a", "NLSQL_OWNER_PASSWORD": "b", "NLSQL_READER_PASSWORD": "c"}
    )
    assert db.host == "127.0.0.1"
    assert "user=analytics_reader" in db.reader_conninfo()
