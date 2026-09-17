"use client";

import {
  ArrowUpRight,
  Calculator,
  CircleCheck,
  FileText,
  Image as ImageIcon,
  ShieldAlert,
  Table2,
} from "lucide-react";
import { useState } from "react";
import { Marked } from "@/components/answer/marked";
import { SourceDrawer } from "@/components/answer/source-drawer";
import { Trace } from "@/components/answer/trace";
import { declineReasons, plural, seconds } from "@/lib/format";
import type { Answer, Citation } from "@/lib/types";

const INTENT: Record<string, string> = {
  value_lookup: "Figure lookup",
  growth: "Growth",
  narrative: "Narrative",
  price: "Price",
  unsupported: "Out of scope",
};
const TYPE_ICON = { table: Table2, figure: ImageIcon } as const;

// One answer, laid out as proof: verdict, answer, the arithmetic, then the pages behind it.
export function AnswerCard({ a, traceOpen = false }: { a: Answer; traceOpen?: boolean }) {
  const [source, setSource] = useState<string | null>(null);
  const r = a.route;
  const decline = a.abstain_reason ? declineReasons[a.abstain_reason] : undefined;
  // Same status, same colour, everywhere: green = checked on the page, amber = declined.
  const verdict = a.abstained
    ? { icon: ShieldAlert, text: "Declined", tone: "bg-warn-soft text-warn" }
    : a.values.length
      ? { icon: CircleCheck, text: "Verified on the cited page", tone: "bg-brand-soft text-brand" }
      : a.citations.length
        ? { icon: FileText, text: "Cited · prose not verified", tone: "bg-sunken text-ink-2" }
        : { icon: Calculator, text: "Computed from prices", tone: "bg-brand-soft text-brand" };

  return (
    <article className="card overflow-hidden">
      <div className="space-y-4 p-5 sm:p-6">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-medium ${verdict.tone}`}>
            <verdict.icon className="size-3.5" />
            {verdict.text}
          </span>
          {r && (
            <span className="font-mono text-muted">
              {[INTENT[r.intent] ?? r.intent, ...r.tickers, ...(r.fiscal_years ?? []).map((y) => `FY${y}`)].join(" · ")}
            </span>
          )}
          <span className="w-full font-mono text-muted sm:ml-auto sm:w-auto">
            {plural(a.llm_calls, "LLM call")} · {plural(a.tokens, "token")} · {seconds(a.ms)}
          </span>
        </div>

        <div>
          <p className="text-sm text-muted">{a.question}</p>
          {a.abstained ? (
            <div className="mt-2">
              <p className="font-display text-2xl leading-snug sm:text-3xl">
                {decline?.title ?? a.abstain_reason}
              </p>
              {decline && <p className="mt-2 max-w-prose text-ink-2">{decline.body}</p>}
            </div>
          ) : (
            <p className="mt-2 text-xl leading-snug font-medium sm:text-2xl">
              <Marked text={a.answer ?? ""} values={a.values} />
            </p>
          )}
        </div>

        {a.computations.map((c, i) => (
          <div key={i} className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg bg-sunken px-4 py-3 font-mono text-sm">
            <Calculator className="size-4 text-muted" aria-hidden="true" />
            <span className="text-ink-2">{c.expression.replaceAll(" * ", " × ")}</span>
            <span className="font-semibold">
              = {c.result}
              {c.unit === "percent" ? "%" : ` ${c.unit}`}
            </span>
            <span className="text-xs text-muted">computed in Python, not by the model</span>
          </div>
        ))}
      </div>

      {a.citations.length > 0 && (
        <section className="border-t border-line bg-bg/60 p-5 sm:p-6">
          <h3 className="eyebrow">Evidence · {a.citations.length}</h3>
          <ul className="mt-3 grid gap-3">
            {a.citations.map((c, i) => (
              <Evidence key={i} c={c} values={a.values} onOpen={() => setSource(c.element_ids[0])} />
            ))}
          </ul>
        </section>
      )}

      {a.trace.length > 0 && (
        <details open={traceOpen} className="group border-t border-line">
          <summary className="flex cursor-pointer list-none items-center justify-between px-5 py-3.5 text-sm text-muted hover:text-ink sm:px-6">
            How this answer was produced · {plural(a.trace.length, "step")}
            <span className="transition-transform group-open:rotate-90">›</span>
          </summary>
          <div className="px-5 pb-5 sm:px-6">
            <Trace steps={a.trace} />
          </div>
        </details>
      )}

      <SourceDrawer id={source} values={a.values} onClose={() => setSource(null)} />
    </article>
  );
}

function Evidence({ c, values, onOpen }: { c: Citation; values: string[]; onOpen: () => void }) {
  const Icon = TYPE_ICON[c.type as keyof typeof TYPE_ICON] ?? FileText;
  return (
    <li className="card p-4">
      <div className="flex items-start gap-3">
        <span className="grid size-8 shrink-0 place-items-center rounded-md bg-sunken">
          <Icon className="size-4 text-muted" aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1 leading-tight">
          <p className="text-sm font-medium">
            {c.ticker} · FY{c.fiscal_year} annual report
          </p>
          <p className="mt-0.5 text-xs text-muted capitalize">
            Page {c.pages.join(", ")} · {c.type}
          </p>
        </div>
        <button
          onClick={onOpen}
          className="inline-flex shrink-0 items-center gap-1 rounded-md px-2 py-1 text-sm text-brand hover:bg-brand-soft"
        >
          View source <ArrowUpRight className="size-3.5" />
        </button>
      </div>
      {c.type === "figure" && (
        // eslint-disable-next-line @next/next/no-img-element -- bytes come from the API
        <img
          src={`/api/figures/${encodeURIComponent(c.element_ids[0])}`}
          alt={`Figure cited from ${c.ticker} FY${c.fiscal_year}, page ${c.pages[0]}`}
          className="mt-3 max-h-64 rounded-lg border border-line"
        />
      )}
      <p className="mt-3 line-clamp-6 font-mono text-xs leading-relaxed whitespace-pre-wrap text-ink-2">
        <Marked text={c.snippet.trim()} values={values} />
      </p>
    </li>
  );
}
