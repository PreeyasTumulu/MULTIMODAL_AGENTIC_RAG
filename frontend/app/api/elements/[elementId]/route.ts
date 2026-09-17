import { proxy } from "@/lib/api";

export async function GET(_: Request, ctx: RouteContext<"/api/elements/[elementId]">) {
  const { elementId } = await ctx.params;
  return proxy(`/api/v1/elements/${encodeURIComponent(elementId)}`);
}
