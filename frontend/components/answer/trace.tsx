import { seconds } from "@/lib/format";
import type { Step } from "@/lib/types";

const LABEL: Record<string, string> = {
  route: "Route",
  retrieve: "Retrieve",
  extract: "Extract",
  verify: "Verify",
  prices: "Price query",
};

const show = (v: unknown) =>
  Array.isArray(v) ? v.join(", ") : typeof v === "object" ? JSON.stringify(v) : String(v);

// The agent's audit trail (agent.Step): what ran, how long it took, what it returned.
// A failed "verify" followed by a second retrieve is the wider k=20 retry, visible here.
export function Trace({ steps }: { steps: Step[] }) {
  const max = Math.max(...steps.map((s) => s.ms), 1);
  return (
    <ol className="space-y-3">
      {steps.map((s, i) => {
        const { cached, ...detail } = s.detail;
        const failed = s.step === "verify";
        return (
          <li key={i} className="grid gap-1 sm:grid-cols-[7.5rem_1fr]">
            <div className="flex items-center gap-2 text-sm font-medium">
              <span className="font-mono text-xs text-muted">{String(i + 1).padStart(2, "0")}</span>
              <span className={failed ? "text-warn" : ""}>{LABEL[s.step] ?? s.step}</span>
            </div>
            <div className="min-w-0 space-y-1.5">
              <div className="flex items-center gap-2">
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-sunken">
                  <div
                    className={`h-full rounded-full ${failed ? "bg-warn" : "bg-brand"}`}
                    style={{ width: `${Math.max(2, (s.ms / max) * 100)}%` }}
                  />
                </div>
                <span className="w-20 text-right font-mono text-xs text-muted">
                  {cached ? "cached" : seconds(s.ms)}
                </span>
              </div>
              <dl className="flex flex-wrap gap-x-4 gap-y-0.5 font-mono text-xs text-muted">
                {Object.entries(detail)
                  .filter(([, v]) => v !== null && v !== "")
                  .map(([k, v]) => (
                    <div key={k} className="flex max-w-full min-w-0 gap-1">
                      <dt className="shrink-0">{k}</dt>
                      <dd className="truncate text-ink-2" title={show(v)}>
                        {show(v)}
                      </dd>
                    </div>
                  ))}
              </dl>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
