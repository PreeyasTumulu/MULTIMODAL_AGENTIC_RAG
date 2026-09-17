"use client";

import { KeyRound, LoaderCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

export function LoginForm({ next, enabled }: { next: string; enabled: boolean }) {
  const router = useRouter();
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const r = await fetch("/api/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key }),
    }).catch(() => null);
    if (r?.ok) {
      router.replace(next);
      router.refresh(); // server components re-read the new cookie
      return;
    }
    setBusy(false);
    setError((await r?.json().catch(() => null))?.detail ?? "Could not reach the server.");
  }

  return (
    <div className="container-page flex justify-center py-20">
      <form onSubmit={submit} className="card w-full max-w-sm p-6">
        <span className="grid size-10 place-items-center rounded-lg bg-brand-soft text-brand">
          <KeyRound className="size-5" aria-hidden="true" />
        </span>
        <h1 className="mt-4 font-display text-3xl">Private documents</h1>
        <p className="mt-2 text-sm text-ink-2">
          Uploading and asking about your own PDFs is private to the owner of this deployment.
        </p>
        {enabled ? (
          <>
            <label htmlFor="key" className="mt-6 block text-sm font-medium">
              Access key
            </label>
            <input
              id="key"
              type="password"
              autoComplete="current-password"
              autoFocus
              required
              value={key}
              onChange={(e) => setKey(e.target.value)}
              className="mt-1.5 h-11 w-full rounded-lg border border-line bg-bg px-3 outline-none focus:border-line-strong"
            />
            <p className="mt-1.5 text-xs text-muted">The ADMIN_API_KEY from the server&apos;s .env.</p>
            {error && (
              <p role="alert" className="mt-3 text-sm text-danger">
                {error}
              </p>
            )}
            <button type="submit" disabled={busy || !key} className="btn btn-primary mt-5 w-full">
              {busy && <LoaderCircle className="size-4 animate-spin" />}
              Sign in
            </button>
          </>
        ) : (
          <p className="mt-6 rounded-lg bg-warn-soft p-3 text-sm text-ink-2">
            Uploads are switched off on this server: set <code>ADMIN_API_KEY</code> to enable them.
          </p>
        )}
      </form>
    </div>
  );
}
