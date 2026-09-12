"""Streamlit front end - a thin client of the HTTP API, exactly as it is deployed.

Run:  uv run streamlit run src/analyst/ui.py      (with the API running)
"""

import httpx
import streamlit as st

from analyst.config import get_settings

API = get_settings().api_url
REASONS = {
    "insufficient_evidence": "the retrieved pages do not contain the answer.",
    "not_grounded": "the figure could not be verified on the page it cited.",
    "out_of_corpus": "that company or year is not in the indexed annual reports.",
    "unsupported_question": "it cannot be answered from filings or prices (advice, forecasts).",
}

st.set_page_config(page_title="Indian Equity Research Analyst", layout="wide")
st.title("Indian Equity Research Analyst")
st.caption("Answers from annual reports and daily prices. Every figure is checked against the "
           "page it cites; when it cannot be, the system declines instead of guessing.")

question = st.text_input("Ask a question",
                         placeholder="What was ICICI Bank's net profit in FY2024?")
if question:
    with st.spinner("Routing, retrieving, verifying..."):
        r = httpx.post(f"{API}/api/v1/ask", json={"question": question}, timeout=300)
    if r.status_code != 200:
        st.error(f"The service could not answer ({r.status_code}). {r.text[:200]}")
        st.stop()
    a = r.json()
    if a["abstained"]:
        st.warning(f"Declined: {REASONS.get(a['abstain_reason'], a['abstain_reason'])}")
    else:
        st.success(a["answer"])
    for c in a["computations"]:
        st.code(f"{c['expression']} = {c['result']} {c['unit']}", language="text")
    for c in a["citations"]:
        pages = ", ".join(map(str, c["pages"]))
        with st.expander(f"Source: {c['ticker']} FY{c['fiscal_year']} report, page {pages} "
                         f"({c['type']})"):
            if c["type"] == "figure":
                st.image(httpx.get(f"{API}/api/v1/figures/{c['element_ids'][0]}").content)
                st.caption("Description written by a vision model, not quoted from the report.")
            st.text(c["snippet"])
    with st.expander(f"How this was answered: {a['llm_calls']} LLM calls, {a['tokens']} tokens, "
                     f"{a['ms'] / 1000:.1f} s"):
        st.dataframe([{"step": s["step"], "ms": s["ms"], "detail": str(s["detail"])[:160]}
                      for s in a["trace"]])
