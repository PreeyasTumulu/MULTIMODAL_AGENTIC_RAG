import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { LoginForm } from "@/components/login-form";
import { enabled, signedIn } from "@/lib/session";

export const metadata: Metadata = { title: "Sign in", robots: { index: false } };

export default async function LoginPage({ searchParams }: PageProps<"/login">) {
  const { next } = await searchParams;
  // Only same-site paths: "//evil.example" would be an open redirect.
  const to = typeof next === "string" && /^\/(?!\/)/.test(next) ? next : "/documents";
  if (await signedIn()) redirect(to);
  return <LoginForm next={to} enabled={enabled()} />;
}
