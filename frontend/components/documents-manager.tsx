"use client";

import {
  ArrowRight,
  CircleAlert,
  FileText,
  LoaderCircle,
  LogOut,
  Trash2,
  UploadCloud,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import type { Upload } from "@/lib/types";

const STAGE: Record<Upload["status"], string> = {
  queued: "Waiting",
  parsing: "Reading pages",
  indexing: "Indexing passages",
  ready: "Ready",
  failed: "Failed",
};
const TONE: Record<Upload["status"], string> = {
  queued: "bg-sunken text-ink-2",
  parsing: "bg-sunken text-ink-2",
  indexing: "bg-sunken text-ink-2",
  ready: "bg-brand-soft text-brand",
  failed: "bg-danger-soft text-danger",
};
const active = (d: Upload) => d.status !== "ready" && d.status !== "failed";

// Fixed locale AND time zone, so the server render and the browser render agree.
const when = new Intl.DateTimeFormat("en-IN", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "Asia/Kolkata",
});
const size = (b: number) => (b < 1024 ** 2 ? `${Math.ceil(b / 1024)} KB` : `${(b / 1024 ** 2).toFixed(1)} MB`);

type Sending = { name: string; pct: number; error?: string };

// fetch() cannot report upload progress, XMLHttpRequest can - and a 50 MB PDF needs it.
function send(file: File, onPct: (pct: number) => void): Promise<{ ok: boolean; body: unknown }> {
  return new Promise((resolve) => {
    const xhr = new XMLHttpRequest();
    const form = new FormData();
    form.append("file", file);
    xhr.upload.onprogress = (e) => e.lengthComputable && onPct(e.loaded / e.total);
    xhr.onload = () => {
      let body: unknown = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {}
      resolve({ ok: xhr.status >= 200 && xhr.status < 300, body });
    };
    xhr.onerror = () => resolve({ ok: false, body: { detail: "The upload was interrupted." } });
    xhr.open("POST", "/api/documents");
    xhr.send(form);
  });
}

export function DocumentsManager({ initial, offline }: { initial: Upload[]; offline: boolean }) {
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  const depth = useRef(0); // dragenter/leave fire for every child element; count them
  const [docs, setDocs] = useState(initial);
  const [sending, setSending] = useState<Sending[]>([]);
  const [dragging, setDragging] = useState(false);
  const [notice, setNotice] = useState<string | null>(offline ? "The analyst API is offline." : null);

  const refresh = useCallback(async () => {
    const r = await fetch("/api/documents").catch(() => null);
    if (r?.status === 401) {
      router.replace("/login?next=/documents"); // the session expired
      return;
    }
    if (r?.ok) {
      setDocs(await r.json());
      setNotice(null);
    } else setNotice("The analyst API is offline.");
  }, [router]);

  // Poll only while something is being processed.
  const busy = docs.some(active);
  useEffect(() => {
    if (!busy) return;
    const h = setInterval(refresh, 2000);
    return () => clearInterval(h);
  }, [busy, refresh]);

  async function upload(files: FileList | File[]) {
    for (const file of Array.from(files)) {
      // Checked here for a fast answer; the API checks the bytes again.
      if (file.size > 50 * 1024 ** 2) {
        setSending((s) => [...s, { name: file.name, pct: 0, error: "Over 50 MB." }]);
        continue;
      }
      setSending((s) => [...s, { name: file.name, pct: 0 }]);
      const set = (patch: Partial<Sending>) =>
        setSending((s) => s.map((x) => (x.name === file.name ? { ...x, ...patch } : x)));
      const { ok, body } = await send(file, (pct) => set({ pct }));
      if (ok) {
        setSending((s) => s.filter((x) => x.name !== file.name));
        await refresh();
      } else {
        const detail = (body as { detail?: unknown } | null)?.detail;
        set({ error: typeof detail === "string" ? detail : "The upload failed." });
      }
    }
  }

  async function remove(d: Upload) {
    if (!window.confirm(`Delete "${d.title}"? Its pages and index are removed too.`)) return;
    const r = await fetch(`/api/documents/${encodeURIComponent(d.document_id)}`, { method: "DELETE" });
    if (!r.ok) setNotice((await r.json().catch(() => null))?.detail ?? "Could not delete it.");
    await refresh();
  }

  async function signOut() {
    await fetch("/api/session", { method: "DELETE" });
    router.replace("/");
    router.refresh();
  }

  return (
    <div className="container-page max-w-4xl py-12">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="eyebrow">Private</p>
          <h1 className="mt-2 font-display text-5xl">Your documents</h1>
          <p className="mt-3 max-w-xl text-ink-2">
            Upload a PDF, then ask about it in the Analyst. Answers come only from that document,
            and every figure is checked against the page it cites. Only you can see these.
          </p>
        </div>
        <button onClick={signOut} className="btn btn-ghost">
          <LogOut className="size-4" /> Sign out
        </button>
      </div>

      <div
        onDragEnter={(e) => {
          e.preventDefault();
          depth.current += 1;
          setDragging(true);
        }}
        onDragLeave={() => {
          depth.current -= 1;
          if (depth.current === 0) setDragging(false);
        }}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          depth.current = 0;
          setDragging(false);
          upload(e.dataTransfer.files);
        }}
        className={`mt-8 rounded-xl border-2 border-dashed p-8 text-center transition-colors ${
          dragging ? "border-brand bg-brand-soft" : "border-line-strong bg-surface"
        }`}
      >
        <UploadCloud className="mx-auto size-8 text-brand" aria-hidden="true" />
        <p className="mt-3 font-medium">
          Drop PDFs here, or{" "}
          <button
            onClick={() => input.current?.click()}
            className="text-brand underline-offset-4 hover:underline"
          >
            choose files
          </button>
        </p>
        <p className="mt-1 text-sm text-muted">
          PDFs with a text layer · up to 50 MB and 1,000 pages · text and tables are indexed;
          images and scanned pages are not
        </p>
        <input
          ref={input}
          type="file"
          accept="application/pdf,.pdf"
          multiple
          hidden
          onChange={(e) => {
            if (e.target.files) upload(e.target.files);
            e.target.value = ""; // so choosing the same file again still fires
          }}
        />
      </div>

      {notice && (
        <p role="alert" className="mt-4 flex items-center gap-2 text-sm text-danger">
          <CircleAlert className="size-4" /> {notice}
        </p>
      )}

      <ul className="mt-8 space-y-3" aria-live="polite">
        {sending.map((s) => (
          <li key={s.name} className="card p-4">
            <div className="flex items-center gap-3 text-sm">
              {s.error ? (
                <CircleAlert className="size-4 text-danger" />
              ) : (
                <LoaderCircle className="size-4 animate-spin text-brand" />
              )}
              <span className="flex-1 truncate font-medium">{s.name}</span>
              {s.error ? (
                <button
                  onClick={() => setSending((x) => x.filter((y) => y.name !== s.name))}
                  className="text-muted hover:text-ink"
                >
                  Dismiss
                </button>
              ) : (
                <span className="font-mono text-muted">Uploading {Math.round(s.pct * 100)}%</span>
              )}
            </div>
            {s.error ? (
              <p className="mt-2 text-sm text-danger">{s.error}</p>
            ) : (
              <Bar value={s.pct} />
            )}
          </li>
        ))}

        {docs.map((d) => (
          <li key={d.document_id} className="card p-4">
            <div className="flex flex-wrap items-start gap-3">
              <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-sunken">
                <FileText className="size-5 text-muted" aria-hidden="true" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{d.title}</p>
                <p className="mt-0.5 text-sm text-muted">
                  {[
                    d.pages && `${d.pages} pages`,
                    d.chunks && `${d.chunks.toLocaleString("en-IN")} passages`,
                    size(d.size_bytes),
                    when.format(new Date(d.uploaded_at)),
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              </div>
              <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${TONE[d.status]}`}>
                {STAGE[d.status]}
              </span>
            </div>

            {active(d) && (
              <div className="mt-3">
                <Bar value={d.progress} />
                <p className="mt-1.5 text-xs text-muted">
                  {STAGE[d.status]}
                  {d.status !== "queued" && ` · ${Math.round(d.progress * 100)}%`}
                </p>
              </div>
            )}
            {d.status === "failed" && (
              <p className="mt-3 text-sm text-danger">
                {d.error} Upload the file again to retry.
              </p>
            )}

            <div className="mt-3 flex justify-end gap-2">
              {d.status === "ready" && (
                <Link href={`/analyst?doc=${encodeURIComponent(d.document_id)}`} className="btn btn-ghost h-9">
                  Ask <ArrowRight className="size-4" />
                </Link>
              )}
              {d.status !== "parsing" && d.status !== "indexing" && (
                <button
                  onClick={() => remove(d)}
                  aria-label={`Delete ${d.title}`}
                  className="btn h-9 text-muted hover:bg-danger-soft hover:text-danger"
                >
                  <Trash2 className="size-4" /> Delete
                </button>
              )}
            </div>
          </li>
        ))}

        {docs.length === 0 && sending.length === 0 && !notice && (
          <li className="py-10 text-center text-muted">No documents yet.</li>
        )}
      </ul>
    </div>
  );
}

function Bar({ value }: { value: number }) {
  return (
    <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-sunken" role="progressbar"
      aria-valuenow={Math.round(value * 100)} aria-valuemin={0} aria-valuemax={100}>
      <div className="h-full rounded-full bg-brand transition-[width]" style={{ width: `${Math.max(2, value * 100)}%` }} />
    </div>
  );
}
