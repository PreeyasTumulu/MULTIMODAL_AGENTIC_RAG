import Link from "next/link";
import { NavLinks, StatusPill, ThemeToggle } from "@/components/header-controls";
import { GithubMark, Logo } from "@/components/logo";
import { site } from "@/lib/site";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-line bg-bg/85 backdrop-blur">
      <div className="container-page flex flex-wrap items-center gap-x-4 py-2.5">
        <Link href="/" className="flex items-center gap-2.5 font-semibold tracking-tight">
          <Logo />
          {site.name}
        </Link>
        {/* On phones the nav drops to its own row instead of being hidden behind a menu. */}
        <div className="order-last -mx-3 w-full pt-1 sm:order-none sm:mx-0 sm:w-auto sm:pt-0">
          <NavLinks />
        </div>
        <div className="ml-auto flex items-center gap-1.5">
          <StatusPill />
          <ThemeToggle />
          <a
            href={site.repo}
            aria-label="Source code on GitHub"
            className="grid size-9 place-items-center rounded-md text-muted transition-colors hover:bg-sunken hover:text-ink"
          >
            <GithubMark />
          </a>
        </div>
      </div>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="border-t border-line">
      <div className="container-page flex flex-col gap-3 py-8 text-sm text-muted sm:flex-row sm:items-center sm:justify-between">
        <p>
          {site.name} · built by {site.author}. Not investment advice — it reads public filings
          and declines requests for recommendations.
        </p>
        <nav aria-label="Footer" className="flex gap-4">
          <Link href="/methodology" className="hover:text-ink">
            Methodology
          </Link>
          <a href={site.repo} className="hover:text-ink">
            GitHub
          </a>
        </nav>
      </div>
    </footer>
  );
}
