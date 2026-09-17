import type { Metadata } from "next";
import { Workspace } from "@/components/workspace";
import { getJson } from "@/lib/api";
import { signedIn } from "@/lib/session";
import type { Upload } from "@/lib/types";

export const metadata: Metadata = {
  title: "Analyst",
  description: "Ask about an Indian company's annual report and get the figure with its page.",
};

// ?q= makes every answer a shareable link: opening it asks the question again.
// ?doc= scopes it to one uploaded PDF - honoured only for a signed-in owner.
export default async function AnalystPage({ searchParams }: PageProps<"/analyst">) {
  const { q, doc } = await searchParams;
  const owner = await signedIn();
  const uploads = owner ? ((await getJson<Upload[]>("/api/v1/documents", true)) ?? []) : [];
  const documents = uploads
    .filter((d) => d.status === "ready")
    .map((d) => ({ id: d.document_id, title: d.title }));
  return (
    <Workspace
      initial={typeof q === "string" ? q.slice(0, 500) : undefined}
      documents={documents}
      initialScope={documents.find((d) => d.id === doc)?.id ?? null}
      owner={owner}
    />
  );
}
