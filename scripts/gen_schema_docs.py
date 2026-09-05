"""Generate docs/data/schema.md from the live SQLAlchemy metadata.

Hand-written schema documentation is wrong within a week. This reads the actual
model definitions (and, if the database is reachable, live row counts) and
regenerates the reference, so the doc cannot drift from the code.

    uv run python scripts/gen_schema_docs.py
"""

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Table, UniqueConstraint, text
from sqlalchemy.exc import SQLAlchemyError

from analyst.db import session_scope
from analyst.models import Base

OUT = Path("docs/data/schema.md")

# One line each, explaining what the table is FOR - the part metadata cannot say.
PURPOSE: dict[str, str] = {
    "companies": "The corpus definition. Everything joins back to `ticker`.",
    "prices": "Daily OHLCV per company. The time-series half of the SQL Agent.",
    "facts": "Reported financial line items. **This table is the evaluation oracle.**",
    "documents": "One row per source PDF, with the checksum that makes it reproducible.",
    "elements": "Typed units extracted from each PDF, carrying page and bbox provenance.",
}

NOTES: dict[str, list[str]] = {
    "companies": [
        "`financial_currency` is **not** the quote currency. Infosys quotes in INR "
        "and reports its statements in USD; assuming the exchange implies the "
        "currency makes it look ~85x smaller than its peers.",
    ],
    "prices": [
        "Rows with a NaN close are dropped before insert - see `prices.drop_partial_bar`.",
        "`UNIQUE (ticker, trade_date)` is what makes re-ingestion idempotent.",
    ],
    "facts": [
        "`value` is stored in **absolute currency units**, never crore or million. "
        "Scaling happens at read time so no precision is lost at write time.",
        "`unit` is part of the fact's meaning: `INR`, `USD`, `INR/share`, `shares`, "
        "or `ratio`. Treating EPS as a currency amount silently corrupts every ratio.",
        "`Numeric(30,4)` not float: Reliance FY26 revenue is ~1.06e13, and float "
        "arithmetic on money is wrong in ways nobody notices.",
    ],
    "documents": [
        "`fiscal_year` is the year the Indian FY **ends** (FY2024-25 -> 2025), which "
        "equals `EXTRACT(YEAR FROM facts.period_end)`. That alignment is what lets "
        "documents join to the oracle with no mapping table.",
        "`local_path` points into `data/`, which is git-ignored. The PDF is "
        "reconstructed from `source_url` + verified against `sha256`.",
    ],
    "elements": [
        "`seq` is the reading order within a page. The column is not called `order` "
        "because that is a SQL keyword.",
        "`text` is what gets embedded. `table_json` holds the exact values. "
        "Arithmetic reads `table_json`, never `text`.",
        "`bbox` is `[x0, y0, x1, y1]` in PDF points, for highlighting a citation.",
    ],
}

TYPE_ALIAS = {"VARCHAR": "varchar", "DATETIME": "timestamptz", "TIMESTAMP": "timestamptz"}


def col_type(col: object) -> str:
    raw = str(getattr(col, "type", ""))
    for long, short in TYPE_ALIAS.items():
        raw = raw.replace(long, short)
    return raw


def mermaid(tables: list[Table]) -> str:
    lines = ["```mermaid", "erDiagram"]
    for t in tables:
        for fk in t.foreign_keys:
            parent = fk.column.table.name
            lines.append(f"    {parent} ||--o{{ {t.name} : has")
    for t in tables:
        lines.append(f"    {t.name} {{")
        for c in t.columns:
            key = "PK" if c.primary_key else ("FK" if c.foreign_keys else "")
            typ = col_type(c).split("(")[0].lower().replace(" ", "_")
            lines.append(f"        {typ} {c.name}{(' ' + key) if key else ''}")
        lines.append("    }")
    lines.append("```")
    return "\n".join(lines)


def row_counts(tables: list[Table]) -> dict[str, int | None]:
    counts: dict[str, int | None] = {}
    try:
        with session_scope() as s:
            for t in tables:
                counts[t.name] = int(s.execute(text(f"SELECT count(*) FROM {t.name}")).scalar_one())
    except SQLAlchemyError:
        for t in tables:
            counts[t.name] = None
    return counts


def main() -> None:
    order = ["companies", "documents", "elements", "facts", "prices"]
    tables = sorted(
        Base.metadata.tables.values(),
        key=lambda t: order.index(t.name) if t.name in order else 99,
    )
    counts = row_counts(tables)
    stamp = datetime.now(UTC).strftime("%Y-%m-%d")

    out: list[str] = [
        "# Database schema",
        "",
        "> **Generated file — do not edit by hand.**",
        "> Regenerate with `uv run python scripts/gen_schema_docs.py`.",
        f"> Last generated: {stamp}",
        "",
        "PostgreSQL 17, reached on host port **5433**. Schema changes are applied "
        "through Alembic migrations, never `create_all()`.",
        "",
        "## Entity relationships",
        "",
        mermaid(tables),
        "",
        "---",
        "",
    ]

    for t in tables:
        n = counts.get(t.name)
        rows = f"{n:,} rows" if n is not None else "not connected"
        out += [f"## `{t.name}`", "", f"*{PURPOSE.get(t.name, '')}*  — currently **{rows}**", ""]
        out += ["| Column | Type | Null | Key | Default |", "|---|---|---|---|---|"]
        for c in t.columns:
            key = "PK" if c.primary_key else ""
            if c.foreign_keys:
                target = next(iter(c.foreign_keys)).target_fullname
                key = (key + " FK→" + target).strip()
            default = ""
            if c.server_default is not None:
                # server_default is a DefaultClause for literals and a plain
                # FetchedValue for computed ones; only the former carries .arg.
                arg = getattr(c.server_default, "arg", None)
                default = f"`{arg}`" if arg is not None else "server-generated"
            elif c.autoincrement is True and c.primary_key:
                default = "auto"
            out.append(
                f"| `{c.name}` | {col_type(c)} | {'yes' if c.nullable else 'no'} "
                f"| {key} | {default} |"
            )
        out.append("")

        # isinstance, not a name check: only UniqueConstraint declares .columns,
        # and mypy needs the narrowing to prove it.
        uniques = [k for k in t.constraints if isinstance(k, UniqueConstraint)]
        if uniques or t.indexes:
            out += ["**Constraints and indexes**", ""]
            for uq in uniques:
                cols = ", ".join(f"`{col.name}`" for col in uq.columns)
                out.append(f"- `UNIQUE {uq.name}` on {cols}")
            for ix in sorted(t.indexes, key=lambda i: i.name or ""):
                cols = ", ".join(f"`{col.name}`" for col in ix.columns)
                out.append(f"- `INDEX {ix.name}` on {cols}")
            out.append("")

        if t.name in NOTES:
            out += ["**Notes**", ""]
            out += [f"- {n}" for n in NOTES[t.name]]
            out.append("")
        out += ["---", ""]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {OUT} ({len(tables)} tables)")


if __name__ == "__main__":
    main()
