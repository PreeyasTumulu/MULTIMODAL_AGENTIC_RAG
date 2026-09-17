// Measured numbers, copied from results/leaderboard.md and results/answers.md (the README's
// "Results"). They are measurements, not targets: change them only from a new ledger run.

export const corpus = {
  companies: 12,
  sectors: 4,
  reports: 6,
  reportCompanies: 4,
  pages: 2056,
  elements: 46241,
  figures: 418,
  figuresIndexed: 16,
  questions: 44,
  unanswerable: 16,
};

export const retrieval = [
  { step: "Dense retrieval baseline", r5: 0.045, mrr: 0.039, r200: 0.432 },
  { step: "+ query expansion (ADR-007)", r5: 0.068, mrr: 0.056, r200: 0.682 },
  { step: "+ company/year chunk prefix (ADR-008)", r5: 0.318, mrr: 0.243, r200: 1.0 },
];

export const answers = [
  { llm: "llama3.2 · 3B, local", acc: 0.227, wrong: 0.568, falseRefusal: 0.205, refusal: 1, calls: 2.1, p50: 4.6 },
  { llm: "gpt-oss-120b · Groq", acc: 0.386, wrong: 0.614, falseRefusal: 0, refusal: 1, calls: 1.9, p50: 5.5 },
];
