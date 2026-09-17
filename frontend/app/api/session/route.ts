import { type NextRequest, NextResponse } from "next/server";
import { enabled, keyMatches, MAX_AGE, newSession, SESSION } from "@/lib/session";

// Sign in with the admin key; the response sets an httpOnly cookie that holds a signed
// expiry, not the key. SameSite=Lax keeps other sites from POSTing with it (CSRF).
export async function POST(req: NextRequest) {
  if (!enabled()) {
    return NextResponse.json(
      { detail: "Private uploads are not configured on this server (ADMIN_API_KEY)." },
      { status: 503 },
    );
  }
  const { key } = await req.json().catch(() => ({}));
  if (typeof key !== "string" || !keyMatches(key)) {
    await new Promise((r) => setTimeout(r, 800)); // makes guessing slow
    return NextResponse.json({ detail: "That key is not right." }, { status: 401 });
  }
  const res = NextResponse.json({ ok: true });
  res.cookies.set(SESSION, newSession(), {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    maxAge: MAX_AGE,
    // Behind a TLS-terminating proxy the request itself is http, so trust its header too.
    secure: req.nextUrl.protocol === "https:" || req.headers.get("x-forwarded-proto") === "https",
  });
  return res;
}

export async function DELETE() {
  const res = NextResponse.json({ ok: true });
  res.cookies.delete(SESSION);
  return res;
}
