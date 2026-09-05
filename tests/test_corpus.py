from analyst.corpus import load_corpus


def test_corpus_loads_and_is_internally_consistent() -> None:
    cs = load_corpus()
    assert len(cs) >= 12
    assert len({c.ticker for c in cs}) == len(cs), "duplicate ticker"
    assert len({c.yf_symbol for c in cs}) == len(cs), "duplicate yahoo symbol"
    assert all(c.yf_symbol.endswith((".NS", ".BO")) for c in cs)
    assert len({c.sector for c in cs}) >= 3, "need multiple sectors to exercise routing"
