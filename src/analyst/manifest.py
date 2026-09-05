"""The document manifest: what PDFs make up the corpus, and how to get them."""

import hashlib
from enum import StrEnum
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

DEFAULT_MANIFEST = Path("configs/documents.yaml")
HASH_CHUNK = 1 << 20  # 1 MiB


class FetchMode(StrEnum):
    AUTO = "auto"
    MANUAL = "manual"


class DocumentSpec(BaseModel):
    ticker: str = Field(pattern=r"^[A-Z0-9&-]+$")
    doc_type: Literal["annual_report", "investor_presentation", "quarterly_result"]
    fiscal_year: int = Field(ge=2000, le=2100)
    title: str
    url: str
    fetch: FetchMode = FetchMode.AUTO
    sha256: str | None = None

    @property
    def filename(self) -> str:
        return f"{self.ticker}_{self.doc_type}_FY{self.fiscal_year}.pdf"

    def local_path(self, data_dir: Path) -> Path:
        return data_dir / "raw" / self.ticker / self.filename


class Manifest(BaseModel):
    documents: list[DocumentSpec]


def load_manifest(path: Path = DEFAULT_MANIFEST) -> list[DocumentSpec]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Manifest.model_validate(data).documents


def sha256_file(path: Path) -> str:
    """Streamed so a 15 MB annual report never lands in memory twice."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(HASH_CHUNK):
            h.update(chunk)
    return h.hexdigest()


def pin_checksums(path: Path, resolved: dict[str, str]) -> None:
    """Write freshly computed checksums back into the manifest.

    Rewritten with a targeted line edit rather than yaml.dump so the file keeps
    its comments and ordering - a manifest whose comments get wiped on every run
    stops being documentation.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    current: str | None = None
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- ticker:"):
            current = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("fiscal_year:") and current:
            current = f"{current}:{stripped.split(':', 1)[1].strip()}"
        if stripped.startswith("sha256:") and current and current in resolved:
            indent = line[: len(line) - len(line.lstrip())]
            out.append(f"{indent}sha256: {resolved[current]}")
            continue
        out.append(line)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def pin_key(spec: DocumentSpec) -> str:
    return f"{spec.ticker}:{spec.fiscal_year}"
