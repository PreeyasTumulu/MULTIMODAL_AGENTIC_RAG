import "server-only";
import { NextResponse } from "next/server";
import { adminHeaders, signedIn } from "@/lib/session";

// Server-only: in compose the backend is reachable only as "api" on the private network,
// and in local dev it is the rag-api launch config on :8400.
const API_URL = process.env.API_URL ?? "http://localhost:8400";

// Route handlers relay backend responses unchanged. The browser only ever talks to this
// origin, so the API needs no CORS and its address never reaches the client bundle.
// `admin` adds the key - callers decide that only after checking the session.
export async function proxy(path: string, init: RequestInit = {}, admin = false) {
  try {
    const headers = new Headers(init.headers);
    if (admin) headers.set("X-API-Key", adminHeaders()["X-API-Key"]);
    const r = await fetch(API_URL + path, { ...init, headers, cache: "no-store" });
    return new NextResponse(r.body, {
      status: r.status,
      headers: { "Content-Type": r.headers.get("Content-Type") ?? "application/json" },
    });
  } catch {
    return NextResponse.json({ detail: "The analyst API is unreachable." }, { status: 503 });
  }
}

// For Server Components: null when the backend is down, so pages still render.
export async function getJson<T>(path: string, admin = false): Promise<T | null> {
  try {
    const r = await fetch(API_URL + path, {
      cache: "no-store",
      headers: admin ? adminHeaders() : {},
    });
    return r.ok ? ((await r.json()) as T) : null;
  } catch {
    return null;
  }
}

// The gate on private route handlers: a response to return, or null to carry on.
export async function denied(): Promise<NextResponse | null> {
  return (await signedIn())
    ? null
    : NextResponse.json({ detail: "Sign in to use private documents." }, { status: 401 });
}
