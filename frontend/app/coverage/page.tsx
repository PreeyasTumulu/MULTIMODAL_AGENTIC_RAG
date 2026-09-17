import { ArrowRight, FileText } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { getJson } from "@/lib/api";
import { askHref, companyQuestion } from "@/lib/examples";
import type { Company } from "@/lib/types";

export const metadata: Metadata = {
  title: "Coverage",
  description: "The companies, sectors and annual reports Pramaan can answer from.",
};

export default async function CoveragePage() {
  const companies = await getJson<Company[]>("/api/v1/companies");
  // Group by sector, keeping the corpus order (configs/companies.yaml).
  const sectors = Map.groupBy(companies ?? [], (c) => c.sector || "Other");
  const filed = companies?.filter((c) => c.filing_years.length).length ?? 0;

  return (
    <div className="container-page py-14">
      <p className="eyebrow">Coverage</p>
      <h1 className="mt-3 font-display text-5xl">What Pramaan can read</h1>
      <p className="mt-4 max-w-2xl text-ink-2">
        Daily closing prices and reported financials for every company below. Figures are answered
        only from an <strong className="font-medium text-ink">indexed annual report</strong> — {filed} of{" "}
        {companies?.length ?? 0} companies today. TCS and Infosys block scripted downloads, so their
        reports are a manual step that has not been done yet.
      </p>

      {!companies ? (
        <p className="card mt-10 p-6 text-danger">
          The analyst API is offline, so coverage can&apos;t be loaded right now.
        </p>
      ) : (
        <div className="mt-12 space-y-12">
          {[...sectors].map(([sector, list]) => (
            <section key={sector}>
              <h2 className="eyebrow">
                {sector} · {list.length}
              </h2>
              <ul className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {list.map((c) => (
                  <li key={c.ticker} className="card flex flex-col p-5">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-mono text-sm font-semibold">{c.ticker}</p>
                        <p className="mt-0.5 text-ink-2">{c.name}</p>
                      </div>
                      <FileText
                        className={`size-5 shrink-0 ${c.filing_years.length ? "text-brand" : "text-line-strong"}`}
                        aria-hidden="true"
                      />
                    </div>
                    <div className="mt-4 flex flex-wrap gap-1.5 text-xs">
                      {c.filing_years.length ? (
                        c.filing_years.map((y) => (
                          <span key={y} className="rounded-full bg-brand-soft px-2 py-0.5 font-medium text-brand">
                            FY{y} report
                          </span>
                        ))
                      ) : (
                        <span className="rounded-full bg-sunken px-2 py-0.5 text-muted">Prices only</span>
                      )}
                    </div>
                    {companyQuestion[c.ticker] && (
                      <Link
                        href={askHref(companyQuestion[c.ticker])}
                        className="group mt-4 flex items-start gap-2 border-t border-line pt-3 text-sm text-ink-2 hover:text-ink"
                      >
                        <span className="flex-1">{companyQuestion[c.ticker]}</span>
                        <ArrowRight className="mt-0.5 size-4 shrink-0 text-brand transition-transform group-hover:translate-x-0.5" />
                      </Link>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
