import { denied, proxy } from "@/lib/api";

// The body goes through untouched: FastAPI owns validation (3-500 chars, api.py).
// A question about an uploaded document is private, so only a signed-in request gets the key.
export async function POST(req: Request) {
  const body = await req.text();
  let documentId: unknown;
  try {
    documentId = JSON.parse(body)?.document_id;
  } catch {}
  if (documentId) {
    const stop = await denied();
    if (stop) return stop;
  }
  const init = { method: "POST", headers: { "Content-Type": "application/json" }, body };
  return proxy("/api/v1/ask", init, Boolean(documentId));
}
