import {
  ArrowRight,
  Calculator,
  FileSearch,
  Route,
  ScanSearch,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { AnswerCard } from "@/components/answer/answer-card";
import { AskBox } from "@/components/ask-box";
import { askHref, examples } from "@/lib/examples";
import { corpus } from "@/lib/metrics";
import showcase from "@/lib/showcase.json";
import { site } from "@/lib/site";
import type { Answer } from "@/lib/types";

// Real API responses captured on 2026-09-17 (lib/showcase.json), not mock-ups.
const shots = showcase as unknown as Record<"figure" | "growth" | "declined", Answer>;

const steps: [LucideIcon, string, string][] = [
  [Route, "Route", "A language model turns the question into JSON — company, year, concept. Python checks each against the database."],
  [ScanSearch, "Retrieve", "Vector search over the report, filtered to that company and year, with the question rewritten in the report's own vocabulary."],
  [FileSearch, "Extract", "The model points at a figure and the evidence block it came from. It never does the arithmetic."],
  [ShieldCheck, "Verify", "Python checks the figure — and its unit — is printed in that block. If not: one wider search, then decline."],
  [Calculator, "Compute", "Growth and price changes are calculated in Python and shown as an expression you can check."],
];

const stats = [
  ["0.318", "Recall@5", "Share of questions whose source ranks in the top five results — up from 0.045."],
  ["1.000", "Recall@200", "The source of all 44 benchmark answers is found within the top 200."],
  ["16 / 16", "Declined", "Every generated unanswerable question was declined, on both models."],
  ["0.000", "False refusals", "gpt-oss-120b declined no answerable question (llama3.2: 0.205)."],
];

export default function Home() {
  return (
    <>
      <section className="container-page grid grid-cols-1 items-center gap-12 py-14 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] lg:py-24">
        <div>
          <p className="eyebrow">AI research analyst · Indian equities</p>
          <h1 className="mt-4 font-display text-5xl leading-[1.02] tracking-tight sm:text-6xl lg:text-7xl">
            Every figure,
            <br />
            <em className="text-brand">with its page.</em>
          </h1>
          <p className="mt-6 max-w-xl text-lg leading-relaxed text-ink-2">{site.description}</p>
          <div className="mt-8 max-w-xl">
            <AskBox />
          </div>
          <div className="mt-4 flex max-w-xl flex-wrap gap-2">
            {examples.slice(0, 3).map((e) => (
              <Link key={e.question} href={askHref(e.question)} className="chip">
                {e.question}
              </Link>
            ))}
          </div>
        </div>
        <div className="relative">
          <div aria-hidden="true" className="absolute -inset-x-2 -inset-y-6 -z-10 rounded-[2rem] bg-brand-soft blur-2xl lg:-inset-x-6" />
          <p className="mb-3 font-mono text-xs text-muted">Real response · served from the answer cache</p>
          <AnswerCard a={shots.figure} />
        </div>
      </section>

      <section className="border-y border-line bg-surface">
        <div className="container-page grid grid-cols-1 gap-12 py-20 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
          <div>
            <p className="eyebrow">How it works</p>
            <h2 className="mt-3 font-display text-4xl sm:text-5xl">The model points. Python checks.</h2>
            <p className="mt-4 max-w-lg text-ink-2">
              A chat-with-PDF app lets the model write the number. Here the model only says where
              the number is — and anything that isn&apos;t printed there never reaches you.
            </p>
            <ol className="mt-10 space-y-6">
              {steps.map(([Icon, title, body], i) => (
                <li key={title} className="flex gap-4">
                  <span className="grid size-10 shrink-0 place-items-center rounded-lg border border-line bg-bg">
                    <Icon className="size-5 text-brand" aria-hidden="true" />
                  </span>
                  <div>
                    <h3 className="font-medium">
                      <span className="mr-2 font-mono text-xs text-muted">0{i + 1}</span>
                      {title}
                    </h3>
                    <p className="mt-1 text-sm leading-relaxed text-ink-2">{body}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
          <div className="lg:pt-16">
            <p className="mb-3 font-mono text-xs text-muted">
              A real trace: verification failed once, so it searched wider and tried again
            </p>
            <AnswerCard a={shots.growth} traceOpen />
          </div>
        </div>
      </section>

      <section className="container-page grid grid-cols-1 items-center gap-12 py-20 lg:grid-cols-2">
        <div className="order-last lg:order-none">
          <AnswerCard a={shots.declined} />
        </div>
        <div>
          <p className="eyebrow">Declining is a feature</p>
          <h2 className="mt-3 font-display text-4xl sm:text-5xl">No figure beats a made-up one.</h2>
          <p className="mt-4 max-w-lg text-ink-2">
            Investment advice, forecasts, companies without an indexed report, figures it cannot
            find on the page — each is declined with the reason, instead of answered with
            confidence.
          </p>
          <Link href="/coverage" className="btn btn-ghost mt-6">
            See what&apos;s covered <ArrowRight className="size-4" />
          </Link>
        </div>
      </section>

      <section className="border-t border-line bg-surface">
        <div className="container-page py-20">
          <p className="eyebrow">Measured, not claimed</p>
          <h2 className="mt-3 max-w-2xl font-display text-4xl sm:text-5xl">
            Evaluated on a benchmark generated from reported financials.
          </h2>
          <dl className="mt-12 grid gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-2 lg:grid-cols-4">
            {stats.map(([value, label, body]) => (
              <div key={label} className="bg-surface p-6">
                <dt className="eyebrow">{label}</dt>
                <dd className="mt-3 font-display text-5xl">{value}</dd>
                <dd className="mt-3 text-sm leading-relaxed text-ink-2">{body}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-6 max-w-3xl text-sm text-muted">
            Answer accuracy is 0.386 with gpt-oss-120b and 0.227 with the local llama3.2, on{" "}
            {corpus.questions} questions over {corpus.reports} reports ({corpus.pages.toLocaleString("en-IN")}{" "}
            pages). The most common failure is a real printed figure taken from the wrong row or column —
            something the verifier cannot catch yet.{" "}
            <Link href="/methodology" className="text-brand underline-offset-4 hover:underline">
              Read the methodology
            </Link>
          </p>
        </div>
      </section>

      <section className="container-page py-20 text-center">
        <h2 className="font-display text-4xl sm:text-5xl">Check a figure yourself.</h2>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link href="/analyst" className="btn btn-primary">
            Open the analyst <ArrowRight className="size-4" />
          </Link>
          <a href={site.repo} className="btn btn-ghost">
            Read the code
          </a>
        </div>
      </section>
    </>
  );
}
