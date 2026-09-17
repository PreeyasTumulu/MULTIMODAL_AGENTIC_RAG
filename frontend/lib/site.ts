// The product's identity in one place - renaming it here renames every page.
// "Pramaan" is Hindi/Sanskrit for proof: every figure comes with its page.
export const site = {
  name: "Pramaan",
  tagline: "Answers from annual reports, with the page to prove it.",
  description:
    "An AI research analyst for Indian listed companies. It cites the annual-report page " +
    "behind every figure, checks the figure is printed there, and declines when it cannot.",
  repo: "https://github.com/PreeyasTumulu/MULTIMODAL_AGENTIC_RAG",
  author: "Preeyas Tumulu",
};

export const nav = [
  { href: "/analyst", label: "Analyst" },
  { href: "/documents", label: "Documents", locked: true }, // private: behind sign-in
  { href: "/coverage", label: "Coverage" },
  { href: "/methodology", label: "Methodology" },
];

// Links into the repo, so every claim on the site points at its evidence.
export const repoFile = (path: string) => `${site.repo}/blob/main/${path}`;
