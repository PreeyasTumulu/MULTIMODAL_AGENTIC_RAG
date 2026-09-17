"use client";

// Runs during HTML parsing (server render); inert when React renders it in the browser,
// which silences React's "script tag inside a component" warning. Pattern from the Next.js
// guide "Preventing flash before hydration".
export function InlineScript({ html }: { html: string }) {
  return (
    <script
      type={typeof window === "undefined" ? "text/javascript" : "text/plain"}
      suppressHydrationWarning
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
