"use client";

import { Moon, Sun } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useLayoutEffect, useState } from "react";
import { nav } from "@/lib/site";
import type { Health } from "@/lib/types";

export function NavLinks() {
  const path = usePathname();
  return (
    <nav aria-label="Main" className="flex items-center gap-1">
      {nav.map(({ href, label }) => {
        const active = path.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={`rounded-md px-3 py-1.5 text-sm transition-colors ${
              active ? "bg-sunken text-ink" : "text-muted hover:text-ink"
            }`}
          >
            {label}
          </Link>
        );
      })}
    </nav>
  );
}

export function ThemeToggle() {
  // Dev Strict Mode remounts <html> and drops the attribute the inline script set;
  // re-apply before paint (a no-op in production).
  useLayoutEffect(() => {
    const t = localStorage.getItem("theme");
    if (t) document.documentElement.dataset.theme = t;
  }, []);

  function toggle() {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    localStorage.setItem("theme", next);
  }

  // Both icons render and CSS picks one, so server and client markup always match.
  return (
    <button
      onClick={toggle}
      aria-label="Toggle dark mode"
      className="grid size-9 place-items-center rounded-md text-muted transition-colors hover:bg-sunken hover:text-ink"
    >
      <Moon className="size-4 dark:hidden" />
      <Sun className="hidden size-4 dark:block" />
    </button>
  );
}

type State = "checking" | "offline" | Health;

// Live backend status: the product says plainly when its engine is down.
export function StatusPill() {
  const [s, setS] = useState<State>("checking");
  useEffect(() => {
    fetch("/api/health")
      .then((r) => r.json())
      .then((h: Health) => setS(h.dependencies ? h : "offline"))
      .catch(() => setS("offline"));
  }, []);

  const [dot, label, title] =
    s === "checking"
      ? ["bg-line-strong", "Checking", "Checking the analyst API"]
      : s === "offline"
        ? ["bg-danger", "Offline", "The analyst API is unreachable"]
        : s.status === "ok"
          ? ["bg-brand", s.llm, `Live · Postgres and Qdrant OK · answering with ${s.llm}`]
          : ["bg-warn", "Degraded", `Degraded: ${JSON.stringify(s.dependencies)}`];

  return (
    <span
      title={title}
      role="status"
      className="hidden items-center gap-2 rounded-full border border-line px-2.5 py-1 font-mono text-xs text-muted sm:inline-flex"
    >
      <span className={`size-1.5 rounded-full ${dot}`} />
      {label}
    </span>
  );
}
