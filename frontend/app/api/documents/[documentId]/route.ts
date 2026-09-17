import { denied, proxy } from "@/lib/api";

type Ctx = RouteContext<"/api/documents/[documentId]">;
const path = async (ctx: Ctx) =>
  `/api/v1/documents/${encodeURIComponent((await ctx.params).documentId)}`;

export async function GET(_: Request, ctx: Ctx) {
  return (await denied()) ?? proxy(await path(ctx), {}, true);
}

export async function DELETE(_: Request, ctx: Ctx) {
  return (await denied()) ?? proxy(await path(ctx), { method: "DELETE" }, true);
}
