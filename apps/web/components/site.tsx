import Link from "next/link";
import type { ReactNode } from "react";

export const NOTICE = "African Founder Studies is an independent educational research project based on publicly available material. It is not affiliated with, endorsed by or operated by Iyinoluwa Aboyeji. The system does not speak on his behalf. Answers are AI-generated summaries of cited public sources and may contain errors.";

export function Header() {
  return <header className="border-b border-[var(--line)] bg-[var(--paper)]/95">
    <div className="mx-auto flex max-w-7xl items-center justify-between gap-8 px-5 py-4 lg:px-8">
      <Link href="/" className="flex items-center gap-3 no-underline" aria-label="African Founder Studies home">
        <span className="grid h-10 w-10 place-items-center rounded-full bg-[var(--forest)] text-sm font-bold text-white">AF</span>
        <span><strong className="serif block text-lg leading-none">African Founder Studies</strong><small className="text-[var(--muted)]">Public ideas, cited carefully</small></span>
      </Link>
      <nav aria-label="Primary" className="hidden items-center gap-6 text-sm font-semibold md:flex">
        <Link href="/ask">Ask</Link><Link href="/topics">Topics</Link><Link href="/sources">Sources</Link><Link href="/timeline">Timeline</Link><Link href="/about">Methodology</Link>
      </nav>
      <Link href="/admin/login" className="rounded-full border border-[var(--forest)] px-4 py-2 text-sm font-semibold text-[var(--forest)] no-underline">Research admin</Link>
    </div>
  </header>;
}

export function Footer() {
  return <footer className="mt-20 border-t border-[var(--line)] bg-[#eeeadf]">
    <div className="mx-auto grid max-w-7xl gap-8 px-5 py-12 text-sm lg:grid-cols-[2fr_1fr_1fr] lg:px-8">
      <div><strong className="serif text-xl">African Founder Studies</strong><p className="mt-3 max-w-xl leading-6 text-[var(--muted)]">{NOTICE}</p></div>
      <div><p className="eyebrow mb-3">Research</p><div className="grid gap-2"><Link href="/sources">Source library</Link><Link href="/timeline">Idea timeline</Link><Link href="/about">Methodology</Link></div></div>
      <div><p className="eyebrow mb-3">Accountability</p><div className="grid gap-2"><Link href="/disclaimer">Disclaimer</Link><Link href="/corrections">Submit a correction</Link></div></div>
    </div>
  </footer>;
}

export function Notice({ compact = false }: { compact?: boolean }) {
  return <aside className={`border-l-4 border-[var(--ochre)] bg-[#f2e5d7] text-[#59432d] ${compact ? "px-4 py-3 text-xs leading-5" : "px-5 py-4 text-sm leading-6"}`} aria-label="Independence notice">{NOTICE}</aside>;
}

export function PageShell({ children }: { children: ReactNode }) { return <><Header /><main>{children}</main><Footer /></>; }

export function PageIntro({ eyebrow, title, copy }: { eyebrow: string; title: string; copy: string }) {
  return <div className="border-b border-[var(--line)] bg-[#efece3]"><div className="mx-auto max-w-7xl px-5 py-14 lg:px-8"><p className="eyebrow">{eyebrow}</p><h1 className="mt-3 max-w-4xl text-4xl leading-tight md:text-6xl">{title}</h1><p className="mt-5 max-w-2xl text-lg leading-8 text-[var(--muted)]">{copy}</p></div></div>;
}

export function EmptyState({ title, copy }: { title: string; copy: string }) {
  return <div className="rounded-xl border border-dashed border-[#aaa69b] bg-[var(--card)] px-6 py-12 text-center"><h2 className="text-2xl">{title}</h2><p className="mx-auto mt-3 max-w-xl text-[var(--muted)]">{copy}</p></div>;
}
