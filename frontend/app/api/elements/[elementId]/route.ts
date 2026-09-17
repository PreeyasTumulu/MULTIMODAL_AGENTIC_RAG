import { proxy } from "@/lib/api";
import { signedIn } from "@/lib/session";

// Signed in, the key goes along, so an uploaded document's pages open too; otherwise the
// API answers 404 for them, exactly as if they did not exist.
export async function GET(_: Request, ctx: RouteContext<"/api/elements/[elementId]">) {
  const { elementId } = await ctx.params;
  return proxy(`/api/v1/elements/${encodeURIComponent(elementId)}`, {}, await signedIn());
}
