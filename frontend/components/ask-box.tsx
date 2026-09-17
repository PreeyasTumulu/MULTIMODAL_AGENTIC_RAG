"use client";

import { ArrowUp, LoaderCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { askHref } from "@/lib/examples";

type Props = { onAsk?: (q: string) => void; busy?: boolean; autoFocus?: boolean };

// One input for the whole product. Without onAsk (landing page) it opens the Analyst.
// Enter asks, Shift+Enter adds a line, "/" focuses it from anywhere on the page.
export function AskBox({ onAsk, busy = false, autoFocus = false }: Props) {
  const router = useRouter();
  const ref = useRef<HTMLTextAreaElement>(null);
  const [q, setQ] = useState("");
  const ok = q.trim().length >= 3 && !busy; // the API rejects < 3 chars

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = (e.target as HTMLElement).closest("input, textarea, [contenteditable]");
      if (e.key === "/" && !typing) {
        e.preventDefault();
        ref.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  function submit(e?: { preventDefault(): void }) {
    e?.preventDefault();
    if (!ok) return;
    const question = q.trim();
    if (onAsk) {
      onAsk(question);
      setQ("");
    } else router.push(askHref(question));
  }

  return (
    <form
      onSubmit={submit}
      className="card flex items-end gap-2 p-2 shadow-sm transition-shadow focus-within:border-line-strong focus-within:shadow-md"
    >
      <label htmlFor="ask" className="sr-only">
        Ask about a company&apos;s annual report
      </label>
      <textarea
        id="ask"
        ref={ref}
        rows={1}
        maxLength={500}
        autoFocus={autoFocus}
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) submit(e);
        }}
        placeholder="Ask about a company's annual report…"
        className="field-sizing-content max-h-40 min-h-11 flex-1 resize-none bg-transparent px-3 py-2.5 text-base outline-none placeholder:text-muted"
      />
      <kbd className="mb-3 hidden rounded border border-line px-1.5 font-mono text-xs text-muted sm:block">
        /
      </kbd>
      <button
        type="submit"
        disabled={!ok}
        aria-label="Ask"
        className="grid size-11 shrink-0 place-items-center rounded-lg bg-brand text-brand-ink transition-opacity disabled:opacity-40"
      >
        {busy ? <LoaderCircle className="size-5 animate-spin" /> : <ArrowUp className="size-5" />}
      </button>
    </form>
  );
}
