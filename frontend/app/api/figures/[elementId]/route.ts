import { proxy } from "@/lib/api";
import { signedIn } from "@/lib/session";

// api.py already converts JPEG 2000 to PNG; this only relays the bytes for <img src>.
export async function GET(_: Request, ctx: RouteContext<"/api/figures/[elementId]">) {
  const { elementId } = await ctx.params;
  return proxy(`/api/v1/figures/${encodeURIComponent(elementId)}`, {}, await signedIn());
}
