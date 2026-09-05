"""Fetch the PDF corpus described by configs/documents.yaml.

Idempotent and verifiable:
  - a file already on disk with a matching checksum is skipped
  - a file on disk whose checksum DISAGREES with the manifest is an error, not a
    silent overwrite - that means the source changed under us
  - the first successful fetch pins the checksum back into the manifest

    uv run python scripts/download_docs.py
"""

import os
import sys

import httpx
from sqlalchemy.dialects.postgresql import insert
from tenacity import retry, stop_after_attempt, wait_exponential

from analyst.config import get_settings
from analyst.db import session_scope
from analyst.logging import configure_logging, get_logger
from analyst.manifest import (
    DEFAULT_MANIFEST,
    DocumentSpec,
    FetchMode,
    load_manifest,
    pin_checksums,
    pin_key,
    sha256_file,
)
from analyst.models import Document
from analyst.provenance import make_document_id

log = get_logger("download_docs")

# Some IR sites serve a challenge page to non-browser agents. A realistic UA is
# not evasion - it is the minimum needed for an ordinary public download. Sites
# that still refuse are marked fetch: manual rather than fought.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=20))
def download(spec: DocumentSpec, dest_tmp: str) -> None:
    with httpx.stream(
        "GET", spec.url, headers=HEADERS, follow_redirects=True, timeout=120.0
    ) as r:
        r.raise_for_status()
        ctype = r.headers.get("content-type", "")
        if "pdf" not in ctype.lower():
            raise ValueError(f"expected a PDF, got content-type={ctype!r}")
        with open(dest_tmp, "wb") as fh:
            for chunk in r.iter_bytes(1 << 16):
                fh.write(chunk)


def main() -> None:
    configure_logging()
    settings = get_settings()
    specs = load_manifest()
    newly_pinned: dict[str, str] = {}
    missing_manual: list[DocumentSpec] = []
    ok = 0

    for spec in specs:
        path = spec.local_path(settings.data_dir)
        path.parent.mkdir(parents=True, exist_ok=True)

        if path.exists():
            digest = sha256_file(path)
            if spec.sha256 and digest != spec.sha256:
                log.error(
                    "checksum.mismatch",
                    doc=spec.filename,
                    expected=spec.sha256[:12],
                    found=digest[:12],
                )
                sys.exit(1)
            if not spec.sha256:
                newly_pinned[pin_key(spec)] = digest
            log.info("skip.cached", doc=spec.filename, sha=digest[:12])
        elif spec.fetch is FetchMode.MANUAL:
            missing_manual.append(spec)
            continue
        else:
            tmp = str(path) + ".part"
            download(spec, tmp)
            # Rename only after a complete download, so an interrupted run never
            # leaves a truncated PDF that looks cached on the next run.
            os.replace(tmp, path)
            digest = sha256_file(path)
            newly_pinned[pin_key(spec)] = digest
            log.info(
                "downloaded",
                doc=spec.filename,
                mb=round(path.stat().st_size / 1048576, 1),
                sha=digest[:12],
            )

        with session_scope() as s:
            doc_id = make_document_id(spec.ticker, spec.doc_type, spec.fiscal_year, digest)
            values = {
                "document_id": doc_id,
                "ticker": spec.ticker,
                "doc_type": spec.doc_type,
                "fiscal_year": spec.fiscal_year,
                "title": spec.title,
                "source_url": spec.url,
                "sha256": digest,
                "local_path": str(path),
                "size_bytes": path.stat().st_size,
            }
            stmt = insert(Document).values(**values)
            s.execute(
                stmt.on_conflict_do_update(
                    constraint="uq_documents_identity",
                    set_={k: v for k, v in values.items() if k != "document_id"},
                )
            )
        ok += 1

    if newly_pinned:
        pin_checksums(DEFAULT_MANIFEST, newly_pinned)
        log.info("checksums.pinned", n=len(newly_pinned))

    log.info("done", available=ok, manual_pending=len(missing_manual))

    if missing_manual:
        print("\n" + "=" * 74)
        print("MANUAL DOWNLOADS REQUIRED (these IR sites block automated requests)")
        print("=" * 74)
        for spec in missing_manual:
            print(f"\n  {spec.ticker} FY{spec.fiscal_year} - {spec.title}")
            print(f"    open : {spec.url}")
            print(f"    save : {spec.local_path(get_settings().data_dir)}")
        print("\nThen re-run this script - the checksum gets pinned automatically.\n")


if __name__ == "__main__":
    main()
