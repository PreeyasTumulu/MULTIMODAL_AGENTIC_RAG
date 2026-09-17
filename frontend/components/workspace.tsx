"use client";

import { CircleAlert, FileText, History, LoaderCircle, Lock, RotateCcw, Upload } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { AnswerCard } from "@/components/answer/answer-card";
import { AskBox } from "@/components/ask-box";
import { askHref, examples } from "@/lib/examples";
import type { Answer } from "@/lib/types";

type Doc = { id: string; title: string };
type Item = { id: number; question: string; doc: Doc | null; answer?: Answer; error?: string };

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
  if (status === 401) return "Your session has ended. Sign in again to ask about your documents.";
  // Document errors ("still being processed", "could not be processed: …") are already
  // written for people.
  if ((status === 404 || status === 409) && typeof detail === "string") return detail;
  if (detail === "LLM provider unavailable")
    return "The language model is busy or offline (a rate limit, usually). Try again in a minute.";
  if (status === 503) return "The analyst service is offline right now. Try again shortly.";
  return "Something failed on the server while answering. Try rephrasing, or try again.";
}

type Props = {
  initial?: string;
  documents: Doc[]; // the owner's ready uploads; empty for everyone else
  initialScope: string | null;
  owner: boolean;
};

export function Workspace({ initial, documents, initialScope, owner }: Props) {
  const [items, setItems] = useState<Item[]>([]);
  const [scope, setScope] = useState<Doc | null>(
    documents.find((d) => d.id === initialScope) ?? null,
  );
  const raw = useSyncExternalStore(subscribe, () => localStorage.getItem(RECENT), () => null);
  const recent = useMemo(() => parse(raw), [raw]);
  const [announce, setAnnounce] = useState("");
  const asked = useRef(false);
  const busy = items.some((i) => !i.answer && !i.error);

  const ask = useCallback(async (question: string, doc: Doc | null) => {
    const id = Date.now();
    setItems((xs) => [{ id, question, doc }, ...xs]);
    window.history.replaceState(null, "", askHref(question, doc?.id)); // a shareable link
    window.scrollTo({ top: 0, behavior: "smooth" });
    writeRecent([question, ...readRecent().filter((r) => r !== question)].slice(0, 8));

    let patch: Partial<Item>;
    try {
      const r = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, document_id: doc?.id }),
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
      ask(initial, documents.find((d) => d.id === initialScope) ?? null);
    }
  }, [initial, initialScope, documents, ask]);

  function choose(id: string) {
    const doc = documents.find((d) => d.id === id) ?? null;
    setScope(doc);
    window.history.replaceState(null, "", doc ? `/analyst?doc=${encodeURIComponent(doc.id)}` : "/analyst");
  }

  const askHere = (q: string) => ask(q, scope);

  return (
    // minmax(0, …): an implicit grid column grows to fit long trace/snippet lines on phones.
    <div className="container-page grid grid-cols-1 gap-10 py-8 lg:grid-cols-[minmax(0,1fr)_15rem]">
      <div className="min-w-0 space-y-4">
        <h1 className="sr-only">Analyst</h1>
        <Scope documents={documents} scope={scope} owner={owner} onChoose={choose} />
        <AskBox onAsk={askHere} busy={busy} autoFocus={!initial} />
        <p aria-live="polite" className="sr-only">
          {announce}
        </p>
        <div className="space-y-6 pt-2">
          {items.length === 0 ? (
            scope ? <EmptyDocument doc={scope} /> : <Empty onAsk={askHere} />
          ) : (
            items.map((it) =>
              it.answer ? (
                <AnswerCard key={it.id} a={it.answer} documentTitle={it.doc?.title} />
              ) : it.error ? (
                <Failed
                  key={it.id}
                  item={it}
                  onRetry={() => {
                    setItems((xs) => xs.filter((x) => x.id !== it.id)); // the retry replaces the failure
                    ask(it.question, it.doc);
                  }}
                />
              ) : (
                <Pending key={it.id} question={it.question} doc={it.doc} />
              ),
            )
          )}
        </div>
      </div>

      <aside className="space-y-8 lg:sticky lg:top-24 lg:self-start">
        {/* The empty state already shows the examples; repeat them only once answers push them
            away - and never for a document, which they are not about. */}
        <section hidden={items.length === 0 || scope !== null}>
          <h2 className="eyebrow">Try</h2>
          <ul className="mt-3 space-y-1">
            {examples.map((e) => (
              <li key={e.question}>
                <button
                  onClick={() => ask(e.question, null)}
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
                    onClick={() => askHere(q)}
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

// What a question is asked about. The public sees only the annual reports and a way in;
// the owner gets a native select over their ready uploads.
function Scope({ documents, scope, owner, onChoose }: {
  documents: Doc[];
  scope: Doc | null;
  owner: boolean;
  onChoose: (id: string) => void;
}) {
  if (!owner) {
    return (
      <p className="flex items-center gap-1.5 text-sm text-muted">
        Asking the indexed annual reports ·
        <Link href="/login?next=/analyst" className="inline-flex items-center gap-1 hover:text-ink">
          <Lock className="size-3.5" /> sign in to ask your own PDFs
        </Link>
      </p>
    );
  }
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-sm">
      <label htmlFor="scope" className="text-muted">
        Ask about
      </label>
      <select
        id="scope"
        value={scope?.id ?? ""}
        onChange={(e) => onChoose(e.target.value)}
        className="h-9 max-w-full min-w-0 flex-1 rounded-lg border border-line bg-surface px-2.5 text-ink sm:flex-none"
      >
        <option value="">Annual reports · 12 companies</option>
        {documents.map((d) => (
          <option key={d.id} value={d.id}>
            {d.title}
          </option>
        ))}
      </select>
      <Link href="/documents" className="inline-flex items-center gap-1 text-muted hover:text-ink">
        <Upload className="size-3.5" /> {documents.length ? "Manage uploads" : "Upload a PDF"}
      </Link>
    </div>
  );
}

function EmptyDocument({ doc }: { doc: Doc }) {
  return (
    <div className="py-6">
      <span className="grid size-10 place-items-center rounded-lg bg-brand-soft text-brand">
        <FileText className="size-5" aria-hidden="true" />
      </span>
      <h2 className="mt-4 font-display text-4xl sm:text-5xl">{doc.title}</h2>
      <p className="mt-3 max-w-prose text-ink-2">
        Answers come only from this PDF. Any figure in an answer is checked against the page it
        cites; when nothing on its pages answers the question, it is declined. Growth
        calculations are not done in document mode.
      </p>
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

function Pending({ question, doc }: { question: string; doc: Doc | null }) {
  // Document mode has no routing step: there is no company or year to find.
  const stages = doc ? ["Retrieve", "Extract", "Verify"] : ["Route", "Retrieve", "Extract", "Verify"];
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
      {doc && <p className="mt-1 text-sm text-muted">in {doc.title}</p>}
      {/* Not live progress (the API does not stream) - the stages every answer passes. */}
      <ol className="mt-5 flex flex-wrap items-center gap-2 text-sm text-muted">
        {stages.map((s, i) => (
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
