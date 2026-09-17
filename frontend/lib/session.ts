import "server-only";
import { createHash, createHmac, timingSafeEqual } from "node:crypto";
import { cookies } from "next/headers";

// One secret, ADMIN_API_KEY, does two jobs: this server sends it to the API as X-API-Key,
// and it signs the session cookie. The browser only ever holds the cookie - an expiry and
// its HMAC - never the key. Changing the key signs every session out.
export const SESSION = "pramaan_session";
export const MAX_AGE = 60 * 60 * 24 * 7; // a week

const key = () => process.env.ADMIN_API_KEY ?? "";
export const enabled = () => key().length > 0;
export const adminHeaders = () => ({ "X-API-Key": key() });

const sign = (expires: string) =>
  createHmac("sha256", key()).update(`session:${expires}`).digest("base64url");

// Hashing first makes the comparison constant-time even when the lengths differ.
const digest = (s: string) => createHash("sha256").update(s).digest();
const same = (a: string, b: string) => timingSafeEqual(digest(a), digest(b));

export const keyMatches = (candidate: string) => enabled() && same(candidate, key());

export function newSession(): string {
  const expires = String(Math.floor(Date.now() / 1000) + MAX_AGE);
  return `${expires}.${sign(expires)}`;
}

export async function signedIn(): Promise<boolean> {
  const token = (await cookies()).get(SESSION)?.value;
  if (!enabled() || !token) return false;
  const [expires, signature = ""] = token.split(".");
  return Number(expires) > Date.now() / 1000 && same(signature, sign(expires));
}
