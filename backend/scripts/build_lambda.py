"""Build the Lambda deployment zip for Python 3.13 on arm64 (Graviton).

    uv run python scripts/build_lambda.py            # -> backend/build/lambda.zip

Installs the locked runtime dependencies as Linux arm64 wheels, never building from
source, so the zip is the same whether it's built on Windows, macOS or in CI (plan.md
§6, "Lambda packaging from Windows"). Then adds the olist_nlsql package with its
catalog. Dev tools and the local-only psycopg extra are left out. File order and
timestamps are fixed, so an unchanged build gives the same zip and Terraform sees no
change.
"""

import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
OUT = BACKEND / "build" / "lambda.zip"
PLATFORM = "aarch64-manylinux_2_28"  # Lambda python3.13 runs on Amazon Linux 2023
PYTHON = "3.13"
FIXED_TIME = (2026, 1, 1, 0, 0, 0)
SKIP_DIRS = {"__pycache__", "tests", "test", "bin"}  # bin: console scripts
SKIP_FILES = {".lock"}  # uv's install lock
SKIP_SUFFIXES = {".pyc", ".pyi"}
MAX_UNZIPPED_MB = 250  # Lambda limit for a zip package


def run(*args: str) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True, cwd=BACKEND).stdout  # noqa: S603


def build(out: Path = OUT) -> Path:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        requirements = root / "requirements.txt"
        requirements.write_text(
            run("uv", "export", "--frozen", "--no-dev", "--no-emit-project", "--no-hashes"),
            encoding="utf-8",
        )
        site = root / "site"
        run(
            "uv", "pip", "install",
            "--target", str(site),
            "--python-platform", PLATFORM,
            "--python-version", PYTHON,
            "--no-build",  # wheels only: nothing compiled for the build machine
            "--requirement", str(requirements),
        )  # fmt: skip
        shutil.copytree(BACKEND / "src" / "olist_nlsql", site / "olist_nlsql", dirs_exist_ok=True)

        files = sorted(
            p
            for p in site.rglob("*")
            if p.is_file()
            and not SKIP_DIRS.intersection(p.relative_to(site).parts)
            and p.suffix not in SKIP_SUFFIXES
            and p.name not in SKIP_FILES
        )
        unzipped = sum(p.stat().st_size for p in files)
        if unzipped > MAX_UNZIPPED_MB * 1024 * 1024:
            raise SystemExit(
                f"package is {unzipped / 2**20:.0f} MB unzipped, over {MAX_UNZIPPED_MB} MB"
            )
        out.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in files:
                info = zipfile.ZipInfo(path.relative_to(site).as_posix(), FIXED_TIME)
                info.external_attr = 0o644 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, path.read_bytes())
    print(f"wrote {out} ({out.stat().st_size / 2**20:.1f} MB, {unzipped / 2**20:.1f} MB unzipped)")
    return out


if __name__ == "__main__":
    build(Path(sys.argv[1]) if len(sys.argv) > 1 else OUT)
