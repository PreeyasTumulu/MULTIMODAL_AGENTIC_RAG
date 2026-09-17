// Demo prompts are chosen, not invented: each one was answered correctly (or declined
// correctly) by the default local model - in the measured run (results/answers.jsonl) or
// in a live check on 2026-09-17. Price questions are left out on purpose: llama3.2 does
// not route relative dates ("last year") reliably, and prices are not benchmarked.
export type Example = { kind: "Figure" | "Growth" | "Declined"; question: string };

export const examples: Example[] = [
  { kind: "Figure", question: "What was ICICI Bank's net profit in FY2024?" },
  { kind: "Figure", question: "What were ICICI Bank's total assets at the end of FY2025?" },
  {
    kind: "Growth",
    question: "By what percentage did Sun Pharma's net profit change from FY2024 to FY2025?",
  },
  { kind: "Declined", question: "Should I buy HDFC Bank shares now?" },
  { kind: "Declined", question: "What was TCS's net profit in FY2025?" },
];

// One question per company with a filing, for the Coverage page. The benchmark wording is
// kept on purpose (measured, and served from cache); Reliance has no llama3.2 hit, so it
// uses the one gpt-oss-120b answered correctly.
export const companyQuestion: Record<string, string> = {
  HDFCBANK: "What was HDFC Bank's net profit in FY2025?",
  ICICIBANK: "What were ICICI Bank's total assets at the end of FY2025?",
  RELIANCE: "What was the value of Reliance Industries's inventories at the end of FY2025?",
  SUNPHARMA: "What was Sun Pharmaceutical Industries's net profit in FY2025?",
};

export const askHref =(question: string) => `/analyst?q=${encodeURIComponent(question)}`;
