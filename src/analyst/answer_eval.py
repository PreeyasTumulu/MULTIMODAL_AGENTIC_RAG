"""Answer evaluation - scored against the oracle, with no LLM judge.

Retrieval evaluation asked whether the right chunk was found. This asks whether
the right NUMBER was said, with a citation - or whether the system correctly
refused. Every benchmark answer is a number with a known true value, so
correctness is a comparison, not an opinion: no LLM-as-judge, no quota spent on
grading, and no judge bias to argue about.
"""

import hashlib
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from statistics import median

from pydantic import BaseModel

from analyst.agent import Answer
from analyst.benchmark import BenchmarkQuestion
from analyst.config import ROOT
from analyst.evaluation import bench_sha, git_rev, markdown_table
from analyst.numfmt import find_value_tolerant
from analyst.tools import Company

LEDGER = ROOT / "results" / "answers.jsonl"
LEADERBOARD = ROOT / "results" / "answers.md"

# A growth rate built from two filed figures, graded against one built from two
# vendor figures. The benchmark accepts each figure within 0.5%; two such errors
# in opposite directions move a ~15% growth rate by ~1.15 points.
GROWTH_TOLERANCE_PP = 1.0


class Unanswerable(BaseModel):
    question_id: str
    question: str
    expected: str  # the abstain_reason a careful system would give


def unanswerable(corpus: Mapping[str, Company]) -> list[Unanswerable]:
    """Questions the system must refuse - generated, so the refusal rate is measured.

    - a company with prices but no indexed annual report  -> out_of_corpus
    - a FUTURE fiscal year (a past one could still be printed in some report's
      ten-year history table, which would make it answerable)  -> out_of_corpus
    - investment advice  -> unsupported_question
    """
    out: list[Unanswerable] = []
    for c in corpus.values():
        if not c.filing_years:
            out.append(Unanswerable(question_id=f"{c.ticker}-nofiling", expected="out_of_corpus",
                                    question=f"What was {c.name}'s net profit in FY2025?"))
            continue
        fy = max(c.filing_years) + 6
        out += [
            Unanswerable(question_id=f"{c.ticker}-FY{fy}", expected="out_of_corpus",
                         question=f"What was {c.name}'s total revenue in FY{fy}?"),
            Unanswerable(question_id=f"{c.ticker}-advice", expected="unsupported_question",
                         question=f"Should I buy {c.name} shares now?"),
        ]
    return out


class Grade(BaseModel):
    question_id: str
    kind: str  # value_lookup | growth | unanswerable
    correct: bool
    abstained: bool
    reason: str | None
    cited_expected: bool
    error: float | None  # relative error of a figure; percentage points for growth
    llm_calls: int
    tokens: int
    ms: float


def grade(q: BenchmarkQuestion | Unanswerable, a: Answer) -> Grade:
    """Correct = the true figure at ANY printed scale (exactly how the benchmark located
    it), a growth rate within GROWTH_TOLERANCE_PP, or a refusal of an unanswerable one."""
    if isinstance(q, Unanswerable):
        kind, error, correct, want = "unanswerable", None, a.abstained, set[str]()
    else:
        kind, error, want = q.question_type, _error(q, a), set(q.expected_element_ids)
        correct = error is not None and (kind != "growth" or error <= GROWTH_TOLERANCE_PP)
    return Grade(question_id=q.question_id, kind=kind, correct=correct, abstained=a.abstained,
                 reason=a.abstain_reason, error=error,
                 cited_expected=any(want & set(c.element_ids) for c in a.citations),
                 llm_calls=a.llm_calls, tokens=a.tokens, ms=a.ms)


def _error(q: BenchmarkQuestion, a: Answer) -> float | None:
    """How far off the answer is - None when it gave nothing comparable."""
    if a.abstained:
        return None
    if q.question_type == "growth":
        got = a.computations[-1].result if a.computations else None
        return float(abs(Decimal(got) - Decimal(q.answer_value))) if got else None
    hit = find_value_tolerant(Decimal(q.answer_value), a.values[0]) if a.values else None
    return float(hit[1]) if hit else None


def summarise(gs: Sequence[Grade]) -> dict[str, float]:
    ans = [g for g in gs if g.kind != "unanswerable"]

    def rate(xs: Sequence[Grade], f: Callable[[Grade], bool]) -> float:
        return round(sum(map(f, xs)) / len(xs), 4) if xs else 0.0

    return {
        "n": len(ans),
        "accuracy": rate(ans, lambda g: g.correct),
        "value_acc": rate([g for g in ans if g.kind == "value_lookup"], lambda g: g.correct),
        "growth_acc": rate([g for g in ans if g.kind == "growth"], lambda g: g.correct),
        # The number that matters most: answered, confidently, and wrong.
        "wrong_answer": rate(ans, lambda g: not g.abstained and not g.correct),
        "cited_expected": rate(ans, lambda g: g.cited_expected),
        "false_refusal": rate(ans, lambda g: g.abstained),
        "refusal": rate([g for g in gs if g.kind == "unanswerable"], lambda g: g.abstained),
        "calls_per_q": round(sum(g.llm_calls for g in gs) / len(gs), 2) if gs else 0.0,
        "tokens_per_q": round(sum(g.tokens for g in gs) / len(gs)) if gs else 0.0,
        "p50_ms": median(g.ms for g in gs) if gs else 0.0,
    }


class AnswerRun(BaseModel):
    """A run is a record, as in `evaluation.Run` - and it keeps every grade, so two runs
    can be diffed question by question, not just by their averages."""

    run_id: str
    created_at: datetime
    git_rev: str
    llm: str
    k: int
    bench_sha: str
    notes: str = ""
    metrics: dict[str, float]
    grades: list[Grade]


def build_run(llm: str, k: int, qs: Sequence[BenchmarkQuestion], gs: Sequence[Grade],
              notes: str = "") -> AnswerRun:
    now = datetime.now(UTC)
    digest = hashlib.sha256(f"{llm}{k}{now.isoformat()}".encode()).hexdigest()[:6]
    return AnswerRun(run_id=f"{llm.split('/')[-1]}-k{k}-{digest}", created_at=now,
                     git_rev=git_rev(ROOT), llm=llm, k=k, bench_sha=bench_sha(qs), notes=notes,
                     metrics=summarise(gs), grades=list(gs))


def append_run(run: AnswerRun, path: Path = LEDGER) -> Path:
    """Append-only: a bad run is evidence too."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(run.model_dump_json() + "\n")
    return path


def load_runs(path: Path = LEDGER) -> list[AnswerRun]:
    lines = path.read_text("utf-8").splitlines() if path.exists() else []
    return [AnswerRun.model_validate_json(x) for x in lines if x.strip()]


def render_leaderboard(runs: Sequence[AnswerRun]) -> str:
    """ASCII only - this console is cp1252."""
    rates = ("accuracy", "value_acc", "growth_acc", "wrong_answer", "cited_expected",
             "false_refusal", "refusal")
    head = ["run", "llm", "k", "acc", "value", "growth", "wrong", "cited", "false refusal",
            "refusal", "calls/q", "tokens/q", "p50 s", "bench", "git"]
    rows = [[r.run_id, f"`{r.llm}`", str(r.k), *(f"{r.metrics[m]:.3f}" for m in rates),
             f"{r.metrics['calls_per_q']:.1f}", f"{r.metrics['tokens_per_q']:.0f}",
             f"{r.metrics['p50_ms'] / 1000:.1f}", f"`{r.bench_sha[:8]}`", f"`{r.git_rev}`"]
            for r in sorted(runs, key=lambda r: r.metrics["accuracy"], reverse=True)]
    return "\n".join([
        "# Answer leaderboard", "",
        "Generated from `results/answers.jsonl` by `analyst.answer_eval`. Never edit by hand.",
        "",
        "> **acc** the true figure at any printed scale; growth within 1 point.",
        "> **wrong** answered but incorrect - the column that matters.",
        "> **cited** a citation names the benchmark's single anchor element, so it is strict.",
        "> **refusal** on generated unanswerable questions.",
        "", *(markdown_table([head, *rows]) if rows else ["_No runs recorded yet._"]), ""])


def write_leaderboard(runs: Sequence[AnswerRun], path: Path = LEADERBOARD) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_leaderboard(runs), encoding="utf-8")
    return path
