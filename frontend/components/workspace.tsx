"use client";

import { CircleAlert, History, LoaderCircle, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { AnswerCard } from "@/components/answer/answer-card";
import { AskBox } from "@/components/ask-box";
import { askHref, examples } from "@/lib/examples";
import type { Answer } from "@/lib/types";

type Item = { id: number; question: string; answer?: Answer; error?: string };

// Recent questions live in localStorage - an external store, so React reads it through
// useSyncExternalStore (empty on the server, real list after hydration, no mismatch).
const RECENT = "pramaan:recent";
const parse = (raw: string | null): string[] => {
  try {
    return JSON.parse(raw ?? "[]");
  } catch {
    return [];
  }
};
const readRecent = () => parse(localStorage.getItem(RECENT));
const writeRecent = (list: string[]) => {
  localStorage.setItem(RECENT, JSON.stringify(list));
  window.dispatchEvent(new Event(RECENT));
};
const subscribe = (cb: () => void) => {
  window.addEventListener(RECENT, cb);
  window.addEventListener("storage", cb); // other tabs
  return () => {
    window.removeEventListener(RECENT, cb);
    window.removeEventListener("storage", cb);
  };
};

// What went wrong, in terms of what the user can do next.
function errorText(status: number, detail: unknown) {
  if (status === 422) return "Questions need between 3 and 500 characters.";
  if (detail === "LLM provider unavailable")
    return "The language model is busy or offline (a rate limit, usually). Try again in a minute.";
  if (status === 503) return "The analyst service is offline right now. Try again shortly.";
  return "Something failed on the server while answering. Try rephrasing, or try again.";
}

export function Workspace({ initial }: { initial?: string }) {
  const [items, setItems] = useState<Item[]>([]);
  const raw = useSyncExternalStore(subscribe, () => localStorage.getItem(RECENT), () => null);
  const recent = useMemo(() => parse(raw), [raw]);
  const [announce, setAnnounce] = useState("");
  const asked = useRef(false);
  const busy = items.some((i) => !i.answer && !i.error);

  const ask = useCallback(async (question: string) => {
    const id = Date.now();
    setItems((xs) => [{ id, question }, ...xs]);
    window.history.replaceState(null, "", askHref(question)); // shareable link to this question
    window.scrollTo({ top: 0, behavior: "smooth" });
    writeRecent([question, ...readRecent().filter((r) => r !== question)].slice(0, 8));

    let patch: Partial<Item>;
    try {
      const r = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      // A crash upstream can return plain text, so never assume JSON.
      const body = await r.json().catch(() => null);
      patch = r.ok ? { answer: body as Answer } : { error: errorText(r.status, body?.detail) };
    } catch {
      patch = { error: "Couldn't reach the server. Check your connection and try again." };
    }
    setItems((xs) => xs.map((x) => (x.id === id ? { ...x, ...patch } : x)));
    setAnnounce(patch.answer ? (patch.answer.abstained ? "Declined." : "Answer ready.") : "Failed.");
  }, []);

  useEffect(() => {
    if (initial && !asked.current) {
      asked.current = true; // Strict Mode runs effects twice in dev; ask once
      ask(initial);
    }
  }, [initial, ask]);

  return (
    // minmax(0, …): an implicit grid column grows to fit long trace/snippet lines on phones.
    <div className="container-page grid grid-cols-1 gap-10 py-8 lg:grid-cols-[minmax(0,1fr)_15rem]">
      <div className="min-w-0 space-y-6">
        <h1 className="sr-only">Analyst</h1>
        <AskBox onAsk={ask} busy={busy} autoFocus={!initial} />
        <p aria-live="polite" className="sr-only">
          {announce}
        </p>
        {items.length === 0 ? (
          <Empty onAsk={ask} />
        ) : (
          items.map((it) =>
            it.answer ? (
              <AnswerCard key={it.id} a={it.answer} />
            ) : it.error ? (
              <Failed
                key={it.id}
                item={it}
                onRetry={() => {
                  setItems((xs) => xs.filter((x) => x.id !== it.id)); // the retry replaces the failure
                  ask(it.question);
                }}
              />
            ) : (
              <Pending key={it.id} question={it.question} />
            ),
          )
        )}
      </div>

      <aside className="space-y-8 lg:sticky lg:top-24 lg:self-start">
        {/* The empty state already shows the examples; repeat them only once answers push them away. */}
        <section hidden={items.length === 0}>
          <h2 className="eyebrow">Try</h2>
          <ul className="mt-3 space-y-1">
            {examples.map((e) => (
              <li key={e.question}>
                <button
                  onClick={() => ask(e.question)}
                  disabled={busy}
                  className="w-full rounded-md px-2 py-1.5 text-left text-sm text-ink-2 hover:bg-sunken hover:text-ink disabled:opacity-50"
                >
                  {e.question}
                </button>
              </li>
            ))}
          </ul>
        </section>
        {recent.length > 0 && (
          <section>
            <div className="flex items-center justify-between">
              <h2 className="eyebrow flex items-center gap-1.5">
                <History className="size-3.5" /> Recent
              </h2>
              <button
                onClick={() => writeRecent([])}
                className="text-xs text-muted hover:text-ink"
              >
                Clear
              </button>
            </div>
            <ul className="mt-3 space-y-1">
              {recent.map((q) => (
                <li key={q}>
                  <button
                    onClick={() => ask(q)}
                    disabled={busy}
                    className="w-full truncate rounded-md px-2 py-1.5 text-left text-sm text-muted hover:bg-sunken hover:text-ink disabled:opacity-50"
                  >
                    {q}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}
      </aside>
    </div>
  );
}

function Empty({ onAsk }: { onAsk: (q: string) => void }) {
  return (
    <div className="py-6">
      <h2 className="font-display text-4xl sm:text-5xl">What do you want to check?</h2>
      <p className="mt-3 max-w-prose text-ink-2">
        Ask for a figure from an annual report, or how one changed between years. Every number
        comes back with the page it is printed on — or the question is declined.
      </p>
      <div className="mt-8 grid gap-3 sm:grid-cols-2">
        {examples.map((e) => (
          <button
            key={e.question}
            onClick={() => onAsk(e.question)}
            className="card p-4 text-left transition-colors hover:border-line-strong"
          >
            <span className={`eyebrow ${e.kind === "Declined" ? "text-warn" : "text-brand"}`}>
              {e.kind}
            </span>
            <span className="mt-1.5 block text-ink">{e.question}</span>
          </button>
        ))}
      </div>
      <p className="mt-6 text-sm text-muted">
        Figures come from 6 indexed annual reports.{" "}
        <Link href="/coverage" className="text-brand underline-offset-4 hover:underline">
          See what&apos;s covered
        </Link>
      </p>
    </div>
  );
}

function Pending({ question }: { question: string }) {
  const [ms, setMs] = useState(0);
  useEffect(() => {
    const t0 = Date.now();
    const h = setInterval(() => setMs(Date.now() - t0), 100);
    return () => clearInterval(h);
  }, []);
  return (
    <article className="card p-6" aria-busy="true">
      <div className="flex items-center gap-2 text-sm text-muted">
        <LoaderCircle className="size-4 animate-spin text-brand" />
        Working · <span className="font-mono">{(ms / 1000).toFixed(1)} s</span>
      </div>
      <p className="mt-3 text-lg">{question}</p>
      {/* Not live progress (the API does not stream) - the stages every answer passes. */}
      <ol className="mt-5 flex flex-wrap items-center gap-2 text-sm text-muted">
        {["Route", "Retrieve", "Extract", "Verify"].map((s, i) => (
          <li key={s} className="flex items-center gap-2">
            {i > 0 && <span aria-hidden="true">→</span>}
            <span className="animate-pulse rounded-full bg-sunken px-3 py-1" style={{ animationDelay: `${i * 200}ms` }}>
              {s}
            </span>
          </li>
        ))}
      </ol>
      <p className="mt-5 text-xs text-muted">
        The local model usually answers in a few seconds; repeated questions come from cache.
      </p>
    </article>
  );
}

function Failed({ item, onRetry }: { item: Item; onRetry: () => void }) {
  return (
    <article className="card border-danger/30 bg-danger-soft p-6">
      <div className="flex items-center gap-2 text-sm font-medium text-danger">
        <CircleAlert className="size-4" /> Couldn&apos;t answer
      </div>
      <p className="mt-2 text-sm text-muted">{item.question}</p>
      <p className="mt-3 text-ink-2">{item.error}</p>
      <button onClick={onRetry} className="btn btn-ghost mt-4">
        <RotateCcw className="size-4" /> Try again
      </button>
    </article>
  );
}
