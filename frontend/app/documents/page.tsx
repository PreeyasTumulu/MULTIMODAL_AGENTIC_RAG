import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { DocumentsManager } from "@/components/documents-manager";
import { getJson } from "@/lib/api";
import { signedIn } from "@/lib/session";
import type { Upload } from "@/lib/types";

export const metadata: Metadata = { title: "Documents", robots: { index: false } };

// Checked here, on the server, before anything private is fetched or rendered.
export default async function DocumentsPage() {
  if (!(await signedIn())) redirect("/login?next=/documents");
  const docs = await getJson<Upload[]>("/api/v1/documents", true);
  return <DocumentsManager initial={docs ?? []} offline={docs === null} />;
}
