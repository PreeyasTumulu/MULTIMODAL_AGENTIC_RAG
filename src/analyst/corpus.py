"""Load and validate the company list from configs/companies.yaml."""

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

DEFAULT_CONFIG = Path("configs/companies.yaml")


class CompanySpec(BaseModel):
    ticker: str = Field(pattern=r"^[A-Z0-9&-]+$")
    name: str
    sector: str
    yf_symbol: str


class CorpusSpec(BaseModel):
    companies: list[CompanySpec]


def load_corpus(path: Path = DEFAULT_CONFIG) -> list[CompanySpec]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return CorpusSpec.model_validate(data).companies
