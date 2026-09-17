// Mirrors the API models (src/analyst/agent.py, tools.py, api.py). Kept in sync by hand:
// there is no shared schema between the two languages.

export type Citation = {
  document_id: string;
  ticker: string | null; // null when the source is an uploaded document
  fiscal_year: number | null;
  pages: number[];
  element_ids: string[];
  type: string;
  snippet: string;
};

export type Computation = { expression: string; result: string; unit: string };

export type Step = { step: string; ms: number; detail: Record<string, unknown> };

export type Route = {
  intent: string;
  tickers: string[];
  fiscal_years: number[];
  concept: string | null;
  start: string | null;
  end: string | null;
};

export type Answer = {
  question: string;
  answer: string | null;
  abstained: boolean;
  abstain_reason: string | null;
  values: string[];
  citations: Citation[];
  computations: Computation[];
  route: Route | null;
  trace: Step[];
  llm_calls: number;
  tokens: number;
  ms: number;
};

export type Company = { ticker: string; name: string; filing_years: number[]; sector: string };

export type ElementDetail = {
  element_id: string;
  document_id: string;
  title: string | null;
  page: number;
  type: string;
  text: string | null;
  table_json: { header?: string[]; rows?: string[][] } | null;
  figure: { kind: string; description: string; described_by: string } | null;
};

// src/analyst/uploads.py Upload
export type Upload = {
  document_id: string;
  title: string;
  status: "queued" | "parsing" | "indexing" | "ready" | "failed";
  progress: number;
  pages: number | null;
  chunks: number | null;
  size_bytes: number;
  error: string | null;
  uploaded_at: string;
};

export type Health = {
  status: "ok" | "degraded";
  dependencies: Record<string, string>;
  llm: string;
};
