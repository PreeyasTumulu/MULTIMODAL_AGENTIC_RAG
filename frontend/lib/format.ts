// Why an answer was declined, in the user's terms (keys = agent.py abstain reasons).
export const declineReasons: Record<string, { title: string; body: string }> = {
  insufficient_evidence: {
    title: "The retrieved pages don't contain the answer",
    body: "Nothing retrieved states what was asked. Try the wording the document itself uses, e.g. \"net profit\" rather than \"earnings\".",
  },
  not_grounded: {
    title: "The figure couldn't be verified on its page",
    body: "The model pointed at a number that is not printed in the evidence it cited, so it was rejected instead of shown.",
  },
  out_of_corpus: {
    title: "That company or year isn't indexed",
    body: "Figures can only come from an indexed annual report. See Coverage for the companies and years available.",
  },
  unsupported_question: {
    title: "This isn't a question filings can answer",
    body: "Buy/sell advice and forecasts are out of scope. Ask what a report states instead.",
  },
};

export const seconds = (ms: number) =>
  ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(ms < 10_000 ? 1 : 0)} s`;

export const plural = (n: number, word: string) => `${n.toLocaleString("en-IN")} ${word}${n === 1 ? "" : "s"}`;

export const pct = (x: number) => `${(x * 100).toFixed(1)}%`;

// Wraps each verified value in <mark>-able parts: [text, isValue][].
export function splitValues(text: string, values: string[]): [string, boolean][] {
  const vs = values.filter(Boolean).map((v) => v.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (!vs.length) return [[text, false]];
  return text
    .split(new RegExp(`(${vs.join("|")})`, "g"))
    .filter(Boolean)
    .map((part) => [part, values.includes(part)]);
}
