import type { Metadata } from "next";
import { Workspace } from "@/components/workspace";

export const metadata: Metadata = {
  title: "Analyst",
  description: "Ask about an Indian company's annual report and get the figure with its page.",
};

// ?q= makes every answer a shareable link: opening it asks the question again.
export default async function AnalystPage({ searchParams }: PageProps<"/analyst">) {
  const { q } = await searchParams;
  return <Workspace initial={typeof q === "string" ? q.slice(0, 500) : undefined} />;
}
