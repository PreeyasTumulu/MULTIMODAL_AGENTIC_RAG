"""Evaluation is scored with a fake retriever - no Qdrant, no embeddings.

That is the point of injecting the retriever: the metric code can be tested
against retrievals whose correct answer sits at a rank we chose.
"""

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from analyst.benchmark import BenchmarkQuestion
from analyst.evaluation import (
    Run,
    RunConfig,
    SearchFn,
    append_run,
    build_run,
    depth_curve,
    evaluate,
    load_runs,
    render_leaderboard,
    summarise,
)


@dataclass(frozen=True)
class FakeHit:
    element_ids: list[str] = field(default_factory=list)
    pages: list[int] = field(default_factory=list)


def question(qid: str = "q1", qtype: str = "value_lookup") -> BenchmarkQuestion:
    return BenchmarkQuestion(
        question_id=qid, question="What was X's net profit in FY2025?", question_type=qtype,
        ticker="SUNPHARMA", fiscal_year=2025, concept="Net Income", answer_value="1",
        answer_display="1", unit="INR", document_id="doc", expected_element_ids=["E"],
        expected_pages=[7], matched_as="1", match_kind="exact", evidence_type="table",
    )


def searcher_placing_answer_at(rank: int | None) -> SearchFn:
    """Hits where the correct element sits at `rank`; None means never found."""

    def search(q: BenchmarkQuestion, limit: int) -> list[FakeHit]:
        hits = [FakeHit(["other"], [99]) for _ in range(limit)]
        if rank is not None and rank <= limit:
            hits[rank - 1] = FakeHit(["E"], [7])
        return hits

    return search


def test_rank_and_page_rank_are_found_at_the_expected_position() -> None:
    (r,) = evaluate([question()], searcher_placing_answer_at(3), limit=10)
    assert (r.rank, r.page_rank) == (3, 3)


def test_a_miss_is_none_not_zero() -> None:
    """None and 0 are different claims: 'never found' vs 'found at rank 0'."""
    (r,) = evaluate([question()], searcher_placing_answer_at(None), limit=10)
    assert r.rank is None and r.page_rank is None


def test_answer_deeper_than_the_limit_is_a_miss() -> None:
    (r,) = evaluate([question()], searcher_placing_answer_at(50), limit=10)
    assert r.rank is None


@pytest.mark.parametrize(("rank", "r1", "r5", "mrr"), [(1, 1.0, 1.0, 1.0), (4, 0.0, 1.0, 0.25)])
def test_recall_and_mrr(rank: int, r1: float, r5: float, mrr: float) -> None:
    m = summarise(evaluate([question()], searcher_placing_answer_at(rank), limit=10))
    assert (m.recall_at[1], m.recall_at[5], m.mrr) == (r1, r5, mrr)


def test_misses_drag_the_average_down_rather_than_being_skipped() -> None:
    """The bug this guards: averaging over found ranks only reports the wins."""
    results = evaluate([question("a")], searcher_placing_answer_at(1), limit=10)
    results += evaluate([question("b")], searcher_placing_answer_at(None), limit=10)
    m = summarise(results)
    assert m.n == 2 and m.recall_at[5] == 0.5 and m.mrr == 0.5


def test_depth_curve_is_monotonic_and_flattens_at_the_ceiling() -> None:
    results = evaluate([question("a")], searcher_placing_answer_at(15), limit=200)
    results += evaluate([question("b")], searcher_placing_answer_at(None), limit=200)
    curve = depth_curve(results)
    assert curve[10] == 0.0 and curve[20] == 0.5 and curve[200] == 0.5
    assert sorted(curve.values()) == list(curve.values())


def test_empty_benchmark_does_not_divide_by_zero() -> None:
    assert summarise([]).n == 0 and depth_curve([])[5] == 0.0


def config(model: str = "bge-small") -> RunConfig:
    return RunConfig(retriever="dense", model=model, use_filters=True, limit=10)


def test_run_survives_the_json_round_trip_with_int_keyed_dicts() -> None:
    """recall_at/depth_curve are int-keyed; JSON keys are strings. Prove it holds."""
    qs = [question()]
    results = evaluate(qs, searcher_placing_answer_at(2), limit=200)
    run = build_run(config(), results, qs, deep=results)
    back = Run.model_validate_json(run.model_dump_json())
    assert back.metrics.recall_at[5] == 1.0 and back.depth_curve[200] == 1.0


def test_ledger_appends_and_reloads(tmp_path: Path) -> None:
    path = tmp_path / "runs.jsonl"
    qs = [question()]
    for model in ("bge-small", "bge-base"):
        results = evaluate(qs, searcher_placing_answer_at(1), limit=10)
        append_run(build_run(config(model), results, qs), path)
    runs = load_runs(path)
    assert [r.config.model for r in runs] == ["bge-small", "bge-base"]


def test_bench_sha_differs_when_the_questions_differ() -> None:
    """A silently regenerated benchmark must not look comparable."""
    qs = [question()]
    a = build_run(config(), evaluate(qs, searcher_placing_answer_at(1), 10), qs)
    other = [question(), question("q2")]
    b = build_run(config(), evaluate(other, searcher_placing_answer_at(1), 10), other)
    assert a.bench_sha != b.bench_sha


def test_leaderboard_is_ascii_and_ranks_best_first() -> None:
    """cp1252 console: a non-ASCII character here raises on print."""
    qs = [question()]
    good = build_run(config("bge-base"), evaluate(qs, searcher_placing_answer_at(1), 10), qs)
    bad = build_run(config("minilm"), evaluate(qs, searcher_placing_answer_at(None), 10), qs)
    md = render_leaderboard([bad, good])
    md.encode("ascii")
    assert md.index("bge-base") < md.index("minilm")


def test_leaderboard_with_no_runs_says_so() -> None:
    assert "No runs recorded yet" in render_leaderboard([])
