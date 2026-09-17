import Link from "next/link";

export default function NotFound() {
  return (
    <div className="container-page py-28 text-center">
      <p className="eyebrow">404</p>
      <h1 className="mt-3 font-display text-5xl">This page isn&apos;t in the report.</h1>
      <p className="mt-4 text-ink-2">Pramaan declines to guess where it went.</p>
      <div className="mt-8 flex justify-center gap-3">
        <Link href="/" className="btn btn-primary">Home</Link>
        <Link href="/analyst" className="btn btn-ghost">Open the analyst</Link>
      </div>
    </div>
  );
}
