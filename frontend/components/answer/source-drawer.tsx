"use client";

import { LoaderCircle, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Marked } from "@/components/answer/marked";
import type { ElementDetail } from "@/lib/types";

type Props = { id: string | null; values: string[]; onClose: () => void };

// Label column gets room to read; figure columns stay on one line, right-aligned.
const CELL =
  "whitespace-pre-line first:min-w-44 [&:not(:first-child)]:text-right [&:not(:first-child)]:whitespace-nowrap";

// The cited element exactly as stored (GET /api/v1/elements/{id}): the structured table,
// the page text, or the figure. A native <dialog> gives focus trapping and Esc for free.
export function SourceDrawer({ id, values, onClose }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const [el, setEl] = useState<ElementDetail | "error" | null>(null);

  useEffect(() => {
    if (!id) return;
    const opener = document.activeElement as HTMLElement | null; // focus goes back here on close
    ref.current?.showModal();
    let live = true;
    fetch(`/api/elements/${encodeURIComponent(id)}`)
      .then((r) => (r.ok ? r.json() : "error"))
      .then((d) => live && setEl(d))
      .catch(() => live && setEl("error"));
    return () => {
      live = false;
      setEl(null);
      opener?.focus();
    };
  }, [id]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => e.target === ref.current && ref.current.close()}
      aria-label="Cited source"
      className="m-0 ml-auto h-dvh max-h-none w-full max-w-2xl border-l border-line bg-surface p-0 text-ink"
    >
      <div className="flex h-full flex-col">
        <header className="flex items-start justify-between gap-4 border-b border-line px-6 py-4">
          <div className="min-w-0">
            <p className="eyebrow">Cited source</p>
            <h2 className="mt-1 truncate font-medium">
              {el && el !== "error" ? (el.title ?? el.document_id) : "Loading…"}
            </h2>
            {el && el !== "error" && (
              <p className="mt-0.5 text-sm text-muted">
                Page {el.page} · {el.type}
              </p>
            )}
          </div>
          <button
            onClick={() => ref.current?.close()}
            aria-label="Close"
            className="grid size-9 shrink-0 place-items-center rounded-md text-muted hover:bg-sunken hover:text-ink"
          >
            <X className="size-4" />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-6 py-5">
          {!el && <LoaderCircle className="size-5 animate-spin text-muted" aria-label="Loading" />}
          {el === "error" && <p className="text-danger">This source could not be loaded.</p>}
          {el && el !== "error" && (
            <div className="space-y-5">
              {el.figure && (
                <figure className="space-y-3">
                  {/* eslint-disable-next-line @next/next/no-img-element -- bytes come from the API */}
                  <img
                    src={`/api/figures/${encodeURIComponent(el.element_id)}`}
                    alt={`${el.figure.kind} on page ${el.page}`}
                    className="w-full rounded-lg border border-line"
                  />
                  <figcaption className="rounded-lg bg-warn-soft p-3 text-sm text-ink-2">
                    <strong className="text-warn">Written by {el.figure.described_by}, not quoted
                    from the report.</strong>{" "}
                    Numbers in this description are never used to verify an answer.
                    <span className="mt-2 block">{el.figure.description}</span>
                  </figcaption>
                </figure>
              )}
              {el.table_json?.rows?.length ? (
                <div className="overflow-x-auto rounded-lg border border-line">
                  <table className="w-full text-sm">
                    {el.table_json.header && (
                      <thead className="bg-sunken text-left text-muted">
                        <tr>
                          {el.table_json.header.map((h, i) => (
                            <th key={i} className={`px-3 py-2 font-medium ${CELL}`}>
                              <Marked text={h} values={values} />
                            </th>
                          ))}
                        </tr>
                      </thead>
                    )}
                    <tbody>
                      {el.table_json.rows.map((row, i) => (
                        <tr key={i} className="border-t border-line">
                          {row.map((c, j) => (
                            <td key={j} className={`px-3 py-2 align-top ${CELL}`}>
                              <Marked text={c} values={values} />
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                el.text && (
                  <p className="text-sm leading-relaxed whitespace-pre-wrap text-ink-2">
                    <Marked text={el.text} values={values} />
                  </p>
                )
              )}
              <p className="font-mono text-xs break-all text-muted">element {el.element_id}</p>
            </div>
          )}
        </div>
      </div>
    </dialog>
  );
}
