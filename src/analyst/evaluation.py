"""Retrieval evaluation, and the ledger that makes runs comparable.

Every metric so far lived in a notebook output cell. That is fine for one number
and useless for a comparison: a claim you cannot diff is a claim you cannot
defend. So a run is a *record* - config + benchmark hash + git rev + metrics -
appended to `results/runs.jsonl`, which is committed (`data/` is not).

**The retriever is injected, not imported.** `evaluate()` takes a callable, so
dense, hybrid and reranked retrieval are scored by identical code on identical
questions. That is what makes the deltas mean anything, and it lets the tests
run with a fake retriever and no Qdrant.
"""

import hashlib
import subprocess
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from analyst.benchmark import BenchmarkQuestion

K_VALUES: tuple[int, ...] = (1, 3, 5, 10)
# Where this curve flattens is the ceiling for anything that only *reorders*
# results - a cross-encoder reranker included.
DEPTHS: tuple[int, ...] = (1, 5, 10, 20, 50, 100, 200)

LEDGER = Path("results") / "runs.jsonl"
LEADERBOARD = Path("results") / "leaderboard.md"


class Retrieved(Protocol):
    """The two fields scoring needs; `vectorstore.Hit` satisfies it.

    Read-only members: a frozen dataclass field is not a settable attribute.
    """

    @property
    def element_ids(self) -> list[str]: ...
    @property
    def pages(self) -> list[int]: ...


SearchFn = Callable[[BenchmarkQuestion, int], Sequence[Retrieved]]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class QuestionResult(_Frozen):
    """`rank` is None when the answer never appeared - kept, not dropped."""

    question_id: str
    question_type: str
    ticker: str
    rank: int | None
    page_rank: int | None
    ms: float


class RunConfig(_Frozen):
    """What was measured. Two runs are comparable iff only this differs."""

    retriever: str  # "dense" | "hybrid" | "dense+rerank"
    model: str  # key from analyst.embedding.MODELS
    use_filters: bool
    limit: int
    notes: str = ""


class Metrics(_Frozen):
    n: int
    recall_at: dict[int, float]
    mrr: float
    page_recall_at_5: float
    p50_ms: float


class Run(_Frozen):
    run_id: str
    created_at: datetime
    git_rev: str
    config: RunConfig
    bench_sha: str  # which questions; a silent regeneration shows up as a mismatch
    metrics: Metrics
    depth_curve: dict[int, float] = Field(default_factory=dict)

    def row(self) -> dict[str, object]:
        """One flat row for a DataFrame."""
        return {
            "run": self.run_id, "retriever": self.config.retriever,
            "model": self.config.model, "filters": self.config.use_filters,
            **{f"R@{k}": v for k, v in sorted(self.metrics.recall_at.items())},
            "MRR": self.metrics.mrr, "pR@5": self.metrics.page_recall_at_5,
            "p50_ms": self.metrics.p50_ms, "bench": self.bench_sha[:8],
            "git": self.git_rev,
        }


def _rank[T](want: set[T], got: Sequence[Sequence[T]]) -> int | None:
    """1-based position of the first list intersecting `want`."""
    return next((i for i, ids in enumerate(got, 1) if want & set(ids)), None)


def evaluate(qs: Sequence[BenchmarkQuestion], search: SearchFn, limit: int) -> list[QuestionResult]:
    """Score one retriever over the benchmark. Zero LLM calls."""
    out = []
    for q in qs:
        t0 = time.perf_counter()
        hits = search(q, limit)
        ms = (time.perf_counter() - t0) * 1000
        out.append(QuestionResult(
            question_id=q.question_id, question_type=q.question_type, ticker=q.ticker,
            rank=_rank(set(q.expected_element_ids), [h.element_ids for h in hits]),
            page_rank=_rank(set(q.expected_pages), [h.pages for h in hits]),
            ms=ms,
        ))
    return out


def _recall(ranks: Sequence[int | None], k: int, n: int) -> float:
    """Fraction found within k. A miss scores 0 - it is not dropped from the
    denominator, because averaging over the questions that worked only flatters."""
    return round(sum(r is not None and r <= k for r in ranks) / n, 4)


def summarise(rs: Sequence[QuestionResult], ks: Sequence[int] = K_VALUES) -> Metrics:
    n = len(rs) or 1
    ranks = [r.rank for r in rs]
    ms = sorted(r.ms for r in rs) or [0.0]
    return Metrics(
        n=len(rs),
        recall_at={k: _recall(ranks, k, n) for k in ks},
        mrr=round(sum(1 / r for r in ranks if r) / n, 4),
        page_recall_at_5=_recall([r.page_rank for r in rs], 5, n),
        p50_ms=round(ms[len(ms) // 2], 1),
    )


def depth_curve(rs: Sequence[QuestionResult], depths: Sequence[int] = DEPTHS) -> dict[int, float]:
    n = len(rs) or 1
    ranks = [r.rank for r in rs]
    return {d: _recall(ranks, d, n) for d in depths}


def bench_sha(qs: Sequence[BenchmarkQuestion]) -> str:
    """Content hash, order-independent, so a reshuffle still compares equal."""
    h = hashlib.sha256()
    for q in sorted(qs, key=lambda q: q.question_id):
        h.update(q.model_dump_json().encode())
    return h.hexdigest()[:16]


def git_rev(root: Path | None = None) -> str:
    """Short SHA, `-dirty` when uncommitted: that run is not reproducible."""
    def run(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=root or Path.cwd(), check=True,
                              capture_output=True, text=True, timeout=10).stdout.strip()
    try:
        return run("rev-parse", "--short", "HEAD") + ("-dirty" if run("status", "-s") else "")
    except (subprocess.SubprocessError, OSError):
        return "unknown"


def build_run(cfg: RunConfig, rs: Sequence[QuestionResult], qs: Sequence[BenchmarkQuestion],
              deep: Sequence[QuestionResult] | None = None, root: Path | None = None) -> Run:
    """Assemble a self-describing record. `deep` = a separate wider search."""
    now = datetime.now(UTC)
    digest = hashlib.sha256((cfg.model_dump_json() + now.isoformat()).encode()).hexdigest()[:8]
    return Run(
        run_id=f"{cfg.retriever}-{cfg.model}-{digest}", created_at=now, git_rev=git_rev(root),
        config=cfg, bench_sha=bench_sha(qs), metrics=summarise(rs),
        depth_curve=depth_curve(deep) if deep else {},
    )


def append_run(run: Run, path: Path = LEDGER) -> Path:
    """Append-only: a bad run is evidence too."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(run.model_dump_json() + "\n")
    return path


def load_runs(path: Path = LEDGER) -> list[Run]:
    if not path.exists():
        return []
    return [Run.model_validate_json(x) for x in path.read_text("utf-8").splitlines() if x.strip()]


def load_questions(path: Path) -> list[BenchmarkQuestion]:
    text = path.read_text(encoding="utf-8")
    return [BenchmarkQuestion.model_validate_json(x) for x in text.splitlines() if x.strip()]


def _table(rows: Sequence[Sequence[str]]) -> list[str]:
    return ["| " + " | ".join(rows[0]) + " |", "|" + "|".join(["---"] * len(rows[0])) + "|",
            *["| " + " | ".join(r) + " |" for r in rows[1:]]]


def render_leaderboard(runs: Sequence[Run], ks: Sequence[int] = K_VALUES) -> str:
    """ASCII only - this console is cp1252 and a stray arrow raises."""
    out = ["# Retrieval leaderboard", "",
           "Generated from `results/runs.jsonl` by `analyst.evaluation`. Never edit by hand.", "",
           "> Ground truth is **single-anchor**: each question names one element holding the",
           "> answer, so a different page that also states it scores as a miss. Every row is",
           "> strict the same way, so the deltas are fair; no number here is absolute quality.",
           ""]
    if not runs:
        return "\n".join([*out, "_No runs recorded yet._", ""])

    head = ["run", "retriever", "model", "filters", *[f"R@{k}" for k in ks],
            "MRR", "pR@5", "p50 ms", "bench", "git"]
    body = [[r.run_id, r.config.retriever, f"`{r.config.model}`",
             "yes" if r.config.use_filters else "no",
             *[f"{r.metrics.recall_at.get(k, 0.0):.3f}" for k in ks],
             f"{r.metrics.mrr:.3f}", f"{r.metrics.page_recall_at_5:.3f}",
             f"{r.metrics.p50_ms:.0f}", f"`{r.bench_sha[:8]}`", f"`{r.git_rev}`"]
            for r in sorted(runs, key=lambda r: r.metrics.recall_at.get(5, 0.0), reverse=True)]
    out += _table([head, *body])

    if curves := [r for r in runs if r.depth_curve]:
        depths = sorted({d for r in curves for d in r.depth_curve})
        out += ["", "## Recall by search depth", "",
                "Where this flattens is the ceiling for anything that only reorders results.", ""]
        out += _table([["run", *map(str, depths)],
                       *[[r.run_id, *[f"{r.depth_curve.get(d, 0.0):.3f}" for d in depths]]
                         for r in curves]])
    return "\n".join([*out, ""])


def write_leaderboard(runs: Sequence[Run], path: Path = LEADERBOARD) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_leaderboard(runs), encoding="utf-8")
    return path
