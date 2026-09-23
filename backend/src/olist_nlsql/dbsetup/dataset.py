"""Olist source files: download, copy and checksum verification.

The dataset is CC BY-NC-SA 4.0 and is never committed. Every file is pinned by
SHA-256, so a changed upstream file fails verification instead of silently
changing results.
"""

import hashlib
import shutil
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

KAGGLE_URL = "https://www.kaggle.com/api/v1/datasets/download/olistbr/brazilian-ecommerce"

# SHA-256 of the Kaggle archive as of 2026-09-23. Informational only: the
# per-file hashes below are authoritative, because re-zipping changes this value.
ARCHIVE_SHA256 = "967e41e04fc306fe604e2a693f488995a8b41e5047418f8a5c8e4abd6deca784"


@dataclass(frozen=True, slots=True)
class SourceFile:
    filename: str
    table: str  # table in the raw schema
    sha256: str
    rows: int  # data rows, excluding the header


SOURCE_FILES: tuple[SourceFile, ...] = (
    SourceFile(
        "olist_customers_dataset.csv",
        "customers",
        "983a422239e1712ded753b3bf9ecf47dc73f144d306029dcfa99e70a226883d2",
        99_441,
    ),
    SourceFile(
        "olist_geolocation_dataset.csv",
        "geolocation",
        "b514f6fc991b9566aeba02aa5d67e2c3630f034b60a0e05aa0d082a3b66d88d6",
        1_000_163,
    ),
    SourceFile(
        "olist_orders_dataset.csv",
        "orders",
        "8df58ef3d2d7e9944010f7beecd9b75367f5588ec6e3c91cec19ae3345ef9ecf",
        99_441,
    ),
    SourceFile(
        "olist_order_items_dataset.csv",
        "order_items",
        "0bc4d068c4fe38cbb01bd90e8746e3c613fe7b4baef75fab7b0e329701c3e279",
        112_650,
    ),
    SourceFile(
        "olist_order_payments_dataset.csv",
        "order_payments",
        "4f713964f2815dbbaa40b9488268c55aac3627bfce5aa96cf58d1f3616de3cc0",
        103_886,
    ),
    SourceFile(
        "olist_order_reviews_dataset.csv",
        "order_reviews",
        "012b61c7593e34f51fa614efdf802b9c7056ce6aae5307ddb93236e7cfc797d7",
        99_224,
    ),
    SourceFile(
        "olist_products_dataset.csv",
        "products",
        "3e6569628a17fbc75fd206ee357b59e20364b9afa90f5b6cd5b4d624c58aa9cc",
        32_951,
    ),
    SourceFile(
        "olist_sellers_dataset.csv",
        "sellers",
        "1f643d2b950373b85735e7794b20986f528d7a000432e7c6f9bcbb44d0846a0e",
        3_095,
    ),
    SourceFile(
        "product_category_name_translation.csv",
        "product_category_name_translation",
        "a81f0d1f27b27e7293f761bc79e3ce8f348ee39c4b3ed3e49bde38f478586278",
        71,
    ),
)


class DatasetError(RuntimeError):
    pass


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(directory: Path) -> None:
    """Raise ``DatasetError`` unless every source file is present with the pinned hash."""
    problems: list[str] = []
    for source in SOURCE_FILES:
        path = directory / source.filename
        if not path.is_file():
            problems.append(f"missing: {path}")
        elif (actual := sha256_of(path)) != source.sha256:
            problems.append(f"checksum mismatch: {path.name} ({actual})")
    if problems:
        raise DatasetError("Dataset verification failed:\n  " + "\n  ".join(problems))


def copy_from(source_dir: Path, directory: Path) -> None:
    """Copy the source files from an existing local directory, then verify them."""
    directory.mkdir(parents=True, exist_ok=True)
    for source in SOURCE_FILES:
        shutil.copyfile(source_dir / source.filename, directory / source.filename)
    verify(directory)


def download(directory: Path) -> str:
    """Download the Kaggle archive, extract the source files and verify them.

    Returns the archive's SHA-256.
    """
    directory.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(KAGGLE_URL, headers={"User-Agent": "olist-nlsql/0.1"})
    with tempfile.TemporaryDirectory(dir=directory) as tmp:
        archive = Path(tmp) / "olist.zip"
        # Constant https URL; no user input reaches urlopen.
        with (
            urllib.request.urlopen(request, timeout=120) as response,  # noqa: S310
            archive.open("wb") as handle,
        ):
            shutil.copyfileobj(response, handle)
        archive_sha = sha256_of(archive)
        with zipfile.ZipFile(archive) as zf:
            for source in SOURCE_FILES:
                with (
                    zf.open(source.filename) as src,
                    (directory / source.filename).open("wb") as dst,
                ):
                    shutil.copyfileobj(src, dst)
    verify(directory)
    return archive_sha
