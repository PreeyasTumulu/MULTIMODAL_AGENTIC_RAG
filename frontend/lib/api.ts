import "server-only";
import { NextResponse } from "next/server";

// Server-only: in compose the backend is reachable only as "api" on the private network,
// and in local dev it is the rag-api launch config on :8400.
const API_URL = process.env.API_URL ?? "http://localhost:8400";

// Route handlers relay backend responses unchanged. The browser only ever talks to this
// origin, so the API needs no CORS and its address never reaches the client bundle.
export async function proxy(path: string, init?: RequestInit) {
  try {
    const r = await fetch(API_URL + path, { ...init, cache: "no-store" });
    return new NextResponse(r.body, {
      status: r.status,
      headers: { "Content-Type": r.headers.get("Content-Type") ?? "application/json" },
    });
  } catch {
    return NextResponse.json({ detail: "The analyst API is unreachable." }, { status: 503 });
  }
}

// For Server Components: null when the backend is down, so pages still render.
export async function getJson<T>(path: string): Promise<T | null> {
  try {
    const r = await fetch(API_URL + path, { cache: "no-store" });
    return r.ok ? ((await r.json()) as T) : null;
  } catch {
    return null;
  }
}
