import { ImageResponse } from "next/og";
import { site } from "@/lib/site";

// The card shown when a link to the site is shared (LinkedIn, Slack, X).
export const alt = `${site.name} — ${site.tagline}`;
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: 80,
          background: "#0b0c0b",
          color: "#ecede7",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 20, fontSize: 40 }}>
          <svg width="64" height="64" viewBox="0 0 32 32">
            <rect width="32" height="32" rx="8" fill="#3fcca8" />
            <path d="M10.5 8.5h7l4 4v11h-11z" fill="none" stroke="#04120d" strokeWidth="1.8" strokeLinejoin="round" />
            <path d="M13.2 17.6l2.1 2.1 4-4.4" fill="none" stroke="#04120d" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          {site.name}
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <div style={{ fontSize: 76, lineHeight: 1.05, letterSpacing: -2 }}>
            Every figure, with its page.
          </div>
          <div style={{ fontSize: 30, color: "#8f928a", maxWidth: 900 }}>
            An AI research analyst for Indian listed companies. Each figure it shows is checked
            against the annual-report page it cites.
          </div>
        </div>
      </div>
    ),
    size,
  );
}
