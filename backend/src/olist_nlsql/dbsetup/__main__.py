"""CLI: ``python -m olist_nlsql.dbsetup {download,verify,build,views}``."""

import argparse
import sys
from pathlib import Path

from olist_nlsql.dbsetup import build, dataset
from olist_nlsql.dbsetup.env import LocalDb, data_dir, load_dotenv


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="python -m olist_nlsql.dbsetup")
    parser.add_argument(
        "--data-dir", type=Path, default=data_dir(), help="where the Olist CSVs live"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    dl = sub.add_parser("download", help="fetch the dataset from Kaggle (or copy) and verify")
    dl.add_argument("--from-dir", type=Path, help="copy from a local directory instead")
    sub.add_parser("verify", help="check the CSVs against pinned SHA-256 hashes")
    sub.add_parser("build", help="rebuild roles, raw schema + data, analytics views, grants")
    sub.add_parser("views", help="rebuild only the analytics views and grants")
    args = parser.parse_args(argv)

    try:
        if args.command == "download":
            if args.from_dir:
                dataset.copy_from(args.from_dir, args.data_dir)
                print(f"copied and verified {len(dataset.SOURCE_FILES)} files")
            else:
                archive_sha = dataset.download(args.data_dir)
                note = "" if archive_sha == dataset.ARCHIVE_SHA256 else " (archive re-zipped)"
                print(f"downloaded and verified into {args.data_dir}{note}")
        elif args.command == "verify":
            dataset.verify(args.data_dir)
            print("all source files verified")
        elif args.command == "build":
            build.build(LocalDb.from_env(), args.data_dir)
        elif args.command == "views":
            build.rebuild_views(LocalDb.from_env())
    except (dataset.DatasetError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
