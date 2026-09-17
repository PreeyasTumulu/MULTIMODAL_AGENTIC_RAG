import { NextResponse } from "next/server";
import { denied, proxy } from "@/lib/api";

const LIMIT = 50 * 1024 * 1024; // the API's own limit; checked here too, before buffering

export async function GET() {
  return (await denied()) ?? proxy("/api/v1/documents", {}, true);
}

// The multipart body is relayed as-is, boundary and all (FastAPI parses it).
export async function POST(req: Request) {
  const stop = await denied();
  if (stop) return stop;
  if (Number(req.headers.get("content-length")) > LIMIT + 64 * 1024) {
    return NextResponse.json({ detail: "The file is over 50 MB." }, { status: 413 });
  }
  const init = {
    method: "POST",
    headers: { "Content-Type": req.headers.get("content-type") ?? "" },
    body: await req.arrayBuffer(),
  };
  return proxy("/api/v1/documents", init, true);
}
