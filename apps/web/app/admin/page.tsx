import Link from "next/link";

import { AdminShell } from "@/components/admin";

export default function AdminHome() {
  const cards = [
    ["Candidate review", "Approve or reject discoveries before ingestion.", "/admin/candidates"],
    ["Evidence operations", "Process sources, monitor analysis jobs, and clean verified evidence.", "/admin/jobs"],
    ["Quality and cost", "Run evaluations and watch provider budgets.", "/admin/evaluations"],
  ] as const;

  return <AdminShell title="Collection operations" copy="Discovery, ingestion, interview analysis, and Ask evidence are tracked from one control room.">
    <div className="grid gap-4 md:grid-cols-3">
      {cards.map(([title, copy, href]) => <Link href={href} key={href} className="rounded-xl border border-[var(--line)] bg-white p-5 no-underline">
        <span className="serif text-3xl text-[var(--ochre)]">-&gt;</span>
        <h2 className="mt-10 text-2xl">{title}</h2>
        <p className="mt-2 text-sm leading-6 text-[var(--muted)]">{copy}</p>
      </Link>)}
    </div>
    <div className="mt-6 rounded-xl border border-amber-300 bg-amber-50 p-5 text-sm leading-6">
      <strong>Configuration truthfulness:</strong> provider mode, disabled live crawling, and missing keys are reported by the readiness endpoint.
    </div>
  </AdminShell>;
}
