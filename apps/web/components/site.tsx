import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";

export const NOTICE =
  "Every answer is designed to lead you back to the original conversation.";

export function Header() {
  return (
    <header className="sticky top-0 z-50 border-b border-[var(--line)] bg-[var(--paper)]/95 backdrop-blur-xl">
      <div className="mx-auto flex max-w-[1500px] items-center justify-between gap-8 px-5 py-4 lg:px-8 xl:px-12">
        <Link
          href="/"
          className="flex items-center no-underline"
          aria-label="African Founder Studies home"
        >
          <Image
            src="/images/afs_logo.svg"
            alt="African Founder Studies"
            width={573}
            height={337}
            priority
            className="h-14 w-auto sm:h-16"
          />
        </Link>
        <nav
          aria-label="Primary"
          className="hidden items-center gap-6 text-sm font-semibold md:flex"
        >
          <Link href="/ask">Ask</Link>
          <Link href="/topics">Ideas</Link>
          <Link href="/about">About Elijah</Link>
        </nav>
        <Link
          href="/ask"
          className="rounded-full bg-[var(--forest)] px-4 py-2.5 text-sm font-semibold text-white no-underline sm:px-5"
        >
          <span className="sm:hidden">Ask</span>
          <span className="hidden sm:inline">Ask a question</span>
        </Link>
      </div>
    </header>
  );
}

export function Footer() {
  return (
    <footer className="mt-20 bg-[#102d22] text-white">
      <div className="mx-auto grid max-w-7xl gap-12 px-5 py-16 text-sm lg:grid-cols-[1.6fr_1fr_1fr] lg:px-8">
        <div>
          <Link
            href="/"
            aria-label="African Founder Studies home"
            className="inline-flex rounded-2xl bg-[var(--paper)] px-4 py-2 no-underline"
          >
            <Image
              src="/images/afs_logo.svg"
              alt="African Founder Studies"
              width={573}
              height={337}
              className="h-20 w-auto"
            />
          </Link>
          <p className="mt-5 max-w-xl leading-7 text-[#b9cdc1]">{NOTICE}</p>
        </div>
        <div>
          <p className="mb-4 text-xs font-bold uppercase tracking-[.18em] text-[#f6c663]">
            Explore
          </p>
          <div className="grid gap-3">
            <Link href="/ask">Ask a question</Link>
            <Link href="/topics">Explore ideas</Link>
            <Link href="/about">Meet Elijah</Link>
          </div>
        </div>
        <div>
          <p className="mb-4 text-xs font-bold uppercase tracking-[.18em] text-[#f6c663]">
            Participate
          </p>
          <div className="grid gap-3">
            <Link href="/corrections">Suggest a correction</Link>
            <Link href="/disclaimer">How answers work</Link>
            <a href="mailto:obafemielijahsunday@gmail.com">Contact Elijah</a>
          </div>
        </div>
      </div>
    </footer>
  );
}

export function Notice({ compact = false }: { compact?: boolean }) {
  return (
    <aside
      className={`border-l-4 border-[var(--ochre)] bg-[#f2e5d7] text-[#59432d] ${compact ? "px-4 py-3 text-xs leading-5" : "px-5 py-4 text-sm leading-6"}`}
      aria-label="Independence notice"
    >
      {NOTICE}
    </aside>
  );
}

export function PageShell({ children }: { children: ReactNode }) {
  return (
    <>
      <Header />
      <main>{children}</main>
      <Footer />
    </>
  );
}

export function PageIntro({
  eyebrow,
  title,
  copy,
}: {
  eyebrow: string;
  title: string;
  copy: string;
}) {
  return (
    <div className="border-b border-[var(--line)] bg-[#efece3]">
      <div className="mx-auto max-w-7xl px-5 py-14 lg:px-8">
        <p className="eyebrow">{eyebrow}</p>
        <h1 className="mt-3 max-w-4xl text-4xl leading-tight md:text-6xl">
          {title}
        </h1>
        <p className="mt-5 max-w-2xl text-lg leading-8 text-[var(--muted)]">
          {copy}
        </p>
      </div>
    </div>
  );
}

export function EmptyState({ title, copy }: { title: string; copy: string }) {
  return (
    <div className="rounded-xl border border-dashed border-[#aaa69b] bg-[var(--card)] px-6 py-12 text-center">
      <h2 className="text-2xl">{title}</h2>
      <p className="mx-auto mt-3 max-w-xl text-[var(--muted)]">{copy}</p>
    </div>
  );
}
