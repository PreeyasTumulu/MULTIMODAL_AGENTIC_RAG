import { proxy } from "@/lib/api";

// The body goes through untouched: FastAPI owns validation (3-500 chars, api.py).
export async function POST(req: Request) {
  return proxy("/api/v1/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: await req.text(),
  });
}
