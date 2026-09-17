import type { Metadata } from "next";
import Link from "next/link";
import { answers, corpus, retrieval } from "@/lib/metrics";
import { pct, seconds } from "@/lib/format";
import { repoFile } from "@/lib/site";

export const metadata: Metadata = {
  title: "Methodology",
  description: "How Pramaan answers, the decisions behind it, and how it was measured.",
};

const adr = (n: string, slug: string) => repoFile(`docs/adr/${n}-${slug}.md`);

const decisions = [
  ["The model points; Python verifies", "A figure is shown only if it is printed in the evidence block the model cited, and a unit only if that block prints it.", adr("0009", "answer-generation")],
  ["Provenance from the first parse", "Every element carries document, page, element id and bounding box from extraction onwards, so every answer can cite a page.", adr("0003", "provenance-schema")],
  ["A generated benchmark, graded without an LLM", "Reported financials are the oracle: find a known number in the report and you have a labelled question. Grading is a comparison, not an opinion.", adr("0001", "domain-and-corpus")],
  ["Context beat bigger models", "Prefixing chunks with company and year took Recall@5 from 0.068 to 0.318. Three larger embedding models moved two questions.", adr("0008", "contextual-chunk-prefixes")],
  ["Rejected: a cross-encoder reranker", "It lowered Recall@5 from 0.318 to 0.204 and cost ~44× the latency — a web-trained reranker does not read grids of numbers.", adr("0007", "retrieval-strategy")],
  ["Figures are triaged before they are trusted", "A small vision model invented charts for blank images, so blank images are skipped and numbers in a description can never verify an answer.", adr("0010", "figures")],
  ["Private uploads get the same verification, not a shortcut", "A PDF you upload is chunked into its own index and answered by the same point-then-verify pipeline as the measured corpus — never a plainer \"just generate\" path.", repoFile("src/analyst/uploads.py")],
  ["Prices through fixed, read-only queries", "The model supplies a ticker and dates, never SQL, and every query runs in a READ ONLY transaction.", repoFile("src/analyst/tools.py")],
  ["Plain Python orchestration", "Route, retrieve, extract, verify and compute are ordinary functions — no agent framework to hide control flow.", repoFile("src/analyst/agent.py")],
];

const stack = [
  ["Parsing", "PyMuPDF", "30–60× faster than pdfplumber for the same text (ADR-004)"],
  ["Storage", "PostgreSQL 17", "Elements with provenance, prices, and the evaluation oracle"],
  ["Vectors", "Qdrant 1.12", "Payload filters by company and fiscal year (ADR-005)"],
  ["Embeddings", "bge-small-en-v1.5 · fastembed", "ONNX on CPU; the deploy target has no GPU (ADR-006)"],
  ["Answering", "llama3.2 (Ollama) · gpt-oss-120b (Groq)", "Local by default, hosted when accuracy matters (ADR-002, ADR-009)"],
  ["Figures", "gemma3:4b", "Kind triage: only charts, tables, infographics and diagrams are indexed"],
  ["Serving", "FastAPI · Next.js 16 · Tailwind CSS 4", "The web app proxies the API server-side"],
  ["Infrastructure", "Docker Compose", "Postgres, Qdrant, API and web app as one stack"],
];

const limits = [
  `The benchmark is small and templated: ${corpus.questions} questions, one source element each.`,
  "The verifier cannot catch a printed figure taken from the wrong row or column — the most common failure today.",
  "Only figures are verified. Prose is not, and figures under four significant digits are declined.",
  "Figures are checked against the chunk text stored with the vectors, not re-read from Postgres.",
  "Vector-drawn charts are not extracted, and vision-model figure descriptions remain unreliable.",
  "The local 3B model routes relative dates (\"last year\") unreliably, so price answers can use the wrong window. Prices are not in the benchmark.",
  "Financials come from Yahoo Finance, a normalisation of the filed statements.",
  "In document mode, the verifier can accept a real printed figure that answers a different question than the one asked — a worked example in the prompt reduces this, measured on one case, but it is a prompt fix, not a structural guarantee.",
];

const th = "px-4 py-3 text-left font-medium";
const td = "px-4 py-3 font-mono";

export default function MethodologyPage() {
  return (
    <div className="container-page max-w-4xl py-14">
      <p className="eyebrow">Methodology</p>
      <h1 className="mt-3 font-display text-5xl">How it answers, and how we know.</h1>
      <p className="mt-4 text-lg text-ink-2">
        Pramaan is a retrieval-augmented agent over {corpus.reports} annual reports from{" "}
        {corpus.reportCompanies} Indian companies ({corpus.pages.toLocaleString("en-IN")} pages,{" "}
        {corpus.elements.toLocaleString("en-IN")} parsed elements) plus prices for{" "}
        {corpus.companies}. Every number on this page comes from the project&apos;s results ledger.
      </p>

      <section className="mt-14">
        <h2 className="font-display text-3xl">The pipeline</h2>
        <ol className="mt-6 space-y-2 font-mono text-sm">
          {[
            ["Route", "LLM → JSON: intent, company, years, concept; each checked against Postgres"],
            ["↳ advice · no filing", "decline, with the reason"],
            ["↳ price", "fixed read-only query → change computed in Python"],
            ["Retrieve", "Qdrant · bge-small · query expansion · filtered by company and year · k=10"],
            ["Extract", "LLM names the figure as printed and the evidence block holding it"],
            ["Verify", "Python: printed in that block? unit printed? — else retry at k=20, then decline"],
            ["Compute", "growth in Python → answer + citations + trace"],
          ].map(([k, v]) => {
            const branch = k.startsWith("↳"); // indented, with a label column narrower by the indent
            return (
            <li key={k} className={`card flex flex-col gap-1 px-4 py-3 sm:flex-row sm:gap-4 ${branch ? "ml-6 bg-bg" : ""}`}>
              <span className={`shrink-0 font-semibold ${branch ? "sm:w-50" : "sm:w-56"}`}>{k}</span>
              <span className="text-ink-2">{v}</span>
            </li>
            );
          })}
        </ol>
      </section>

      <section className="mt-16">
        <h2 className="font-display text-3xl">Decisions</h2>
        <div className="mt-6 grid gap-3 sm:grid-cols-2">
          {decisions.map(([title, body, href]) => (
            <a key={title} href={href} className="card p-5 transition-colors hover:border-line-strong">
              <h3 className="font-medium">{title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-ink-2">{body}</p>
            </a>
          ))}
        </div>
      </section>

      <section className="mt-16">
        <h2 className="font-display text-3xl">Retrieval</h2>
        <p className="mt-2 text-ink-2">
          {corpus.questions} generated questions; does the answer&apos;s source element come back?
        </p>
        <div className="card mt-6 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-sunken text-muted">
              <tr><th className={th}>Configuration</th><th className={th}>Recall@5</th><th className={th}>MRR</th><th className={th}>Recall@200</th></tr>
            </thead>
            <tbody>
              {retrieval.map((r, i) => (
                <tr key={r.step} className={`border-t border-line ${i === retrieval.length - 1 ? "font-semibold" : ""}`}>
                  <td className="px-4 py-3">{r.step}</td>
                  <td className={td}>{r.r5.toFixed(3)}</td>
                  <td className={td}>{r.mrr.toFixed(3)}</td>
                  <td className={td}>{r.r200.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="mt-16">
        <h2 className="font-display text-3xl">Answers</h2>
        <p className="mt-2 text-ink-2">
          The same {corpus.questions} questions plus {corpus.unanswerable} generated unanswerable ones.
          Graded numerically — no LLM judge.
        </p>
        <div className="card mt-6 overflow-x-auto">
          <table className="w-full text-sm whitespace-nowrap">
            <thead className="bg-sunken text-muted">
              <tr>
                <th className={th}>Model</th><th className={th}>Accuracy</th><th className={th}>Wrong</th>
                <th className={th}>False refusal</th><th className={th}>Unanswerable declined</th>
                <th className={th}>Calls / q</th><th className={th}>p50</th>
              </tr>
            </thead>
            <tbody>
              {answers.map((a) => (
                <tr key={a.llm} className="border-t border-line">
                  <td className="px-4 py-3">{a.llm}</td>
                  <td className={td}>{pct(a.acc)}</td>
                  <td className={td}>{pct(a.wrong)}</td>
                  <td className={td}>{pct(a.falseRefusal)}</td>
                  <td className={td}>{pct(a.refusal)}</td>
                  <td className={td}>{a.calls}</td>
                  <td className={td}>{seconds(a.p50 * 1000)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-4 text-sm text-ink-2">
          Every figure shown was printed on its cited page, on both models. The larger model nearly
          doubled accuracy and removed false refusals. Of its 27 wrong answers, 5 cited the right
          table and misread it — all Sun Pharma questions.
        </p>
      </section>

      <section className="mt-16">
        <h2 className="font-display text-3xl">Private documents</h2>
        <p className="mt-2 max-w-3xl text-ink-2">
          Beside the measured corpus above, you can upload your own PDF and ask about it —
          answered by the same pipeline, not a shortcut. The document is chunked into its own
          index, so retrieval never mixes it with the indexed reports. Asking it skips Route
          entirely (there is only one document to search) and goes straight to Extract →
          Verify → Compute. It has no growth maths across documents, no figures, and no OCR
          for scanned pages. The whole surface — upload, ask, delete, even an uploaded page&apos;s
          existence — is private to whoever holds the deployment&apos;s access key.
        </p>
        <p className="mt-3 max-w-3xl text-sm text-ink-2">
          A worked example had to be added to the extraction prompt after live testing showed
          the model would answer an off-topic question with an unrelated but genuinely printed
          figure from the retrieved evidence — the verifier cannot catch this, since the number
          really is on the page. See it in <Link href="/documents" className="text-brand hover:underline">Documents</Link>.
        </p>
      </section>

      <section className="mt-16">
        <h2 className="font-display text-3xl">Limitations</h2>
        <ul className="mt-6 space-y-3">
          {limits.map((l) => (
            <li key={l} className="flex gap-3 text-ink-2">
              <span className="mt-2 size-1.5 shrink-0 rounded-full bg-warn" aria-hidden="true" />
              {l}
            </li>
          ))}
        </ul>
      </section>

      <section className="mt-16">
        <h2 className="font-display text-3xl">Stack</h2>
        <dl className="card mt-6 divide-y divide-line">
          {stack.map(([layer, tech, why]) => (
            <div key={layer} className="grid gap-1 px-5 py-4 sm:grid-cols-[8rem_1fr]">
              <dt className="eyebrow pt-0.5">{layer}</dt>
              <dd>
                <span className="font-medium">{tech}</span>
                <span className="block text-sm text-muted">{why}</span>
              </dd>
            </div>
          ))}
        </dl>
      </section>

      <p className="mt-16 text-sm text-muted">
        Full write-ups: the <a href={repoFile("README.md")} className="text-brand hover:underline">README</a>,
        the <a href={repoFile("docs/adr")} className="text-brand hover:underline">decision records</a>, and the{" "}
        <a href={repoFile("results/leaderboard.md")} className="text-brand hover:underline">results ledger</a>.{" "}
        <Link href="/analyst" className="text-brand hover:underline">Try it →</Link>
      </p>
    </div>
  );
}
