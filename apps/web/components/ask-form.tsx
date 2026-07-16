"use client";

import { useState, type FormEvent } from "react";
import type { Answer } from "@/lib/types";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export function AskForm() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setLoading(true); setError(""); setAnswer(null);
    try {
      const response = await fetch(`${API}/ask`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question }) });
      if (!response.ok) throw new Error("The research API could not process this question.");
      setAnswer(await response.json() as Answer);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unexpected request failure."); }
    finally { setLoading(false); }
  }
  return <div className="grid gap-8 lg:grid-cols-[.8fr_1.2fr]">
    <form onSubmit={submit} className="rounded-2xl border border-[var(--line)] bg-[var(--card)] p-6 shadow-sm"><label htmlFor="question" className="serif text-2xl">What do you want to investigate?</label><p className="mt-2 text-sm leading-6 text-[var(--muted)]">Ask about a topic, argument, date, or development over time. Questions about private views will be refused.</p><textarea id="question" required minLength={5} maxLength={1000} value={question} onChange={e=>setQuestion(e.target.value)} className="mt-5 min-h-40 w-full resize-y rounded-lg border border-[var(--line)] bg-white p-4" placeholder="What has the available public record said about fundraising before product-market fit?"/><button disabled={loading} className="mt-4 w-full rounded-full bg-[var(--forest)] px-5 py-3 font-bold text-white disabled:opacity-60">{loading ? "Searching approved evidence…" : "Search and answer"}</button><p className="mt-4 text-xs leading-5 text-[var(--muted)]">Answers never represent the founder and may contain errors. Verify every citation.</p></form>
    <div aria-live="polite">{error && <div role="alert" className="rounded-xl border border-red-300 bg-red-50 p-5 text-red-800">{error}</div>}{!answer && !error && <div className="grid min-h-80 place-items-center rounded-2xl border border-dashed border-[#aaa69b] px-8 text-center text-[var(--muted)]"><div><span className="serif text-5xl text-[var(--forest)]">“</span><p className="mt-2 max-w-md">A response will appear here with its confidence, evidence limitations, and source cards.</p></div></div>}{answer && <article className="rounded-2xl border border-[var(--line)] bg-white p-6"><div className="flex flex-wrap items-center gap-3"><span className={`rounded-full px-3 py-1 text-xs font-bold uppercase ${answer.confidence === "low" ? "bg-amber-100 text-amber-900" : "bg-emerald-100 text-emerald-900"}`}>{answer.confidence} confidence</span>{answer.provider.is_mock && <span className="rounded-full bg-violet-100 px-3 py-1 text-xs font-bold text-violet-900">Fixture / mock provider</span>}</div><h2 className="mt-5 text-3xl">Research answer</h2><p className="prose-copy mt-4">{answer.answer}</p><p className="mt-5 border-l-2 border-[var(--ochre)] pl-4 text-sm text-[var(--muted)]">{answer.evidence_summary}</p>{answer.limitations.length > 0 && <div className="mt-6 rounded-lg bg-[#f5eee3] p-4"><strong>Limitations</strong><ul className="mt-2 list-disc space-y-1 pl-5 text-sm">{answer.limitations.map(item=><li key={item}>{item}</li>)}</ul></div>}<h3 className="mt-8 text-2xl">Cited evidence</h3>{answer.citations.length ? <div className="mt-4 grid gap-4">{answer.citations.map(citation=><a href={citation.url} target="_blank" rel="noreferrer" key={`${citation.source_id}-${citation.start_seconds}`} className="rounded-xl border border-[var(--line)] p-4 no-underline"><span className="eyebrow">{citation.publication_date ?? "Undated"} · {citation.publisher}</span><h4 className="serif mt-2 text-lg font-bold">{citation.title}</h4><p className="mt-2 text-sm leading-6 text-[var(--muted)]">“{citation.supporting_excerpt}”</p></a>)}</div> : <p className="mt-3 text-sm text-[var(--muted)]">No citation met the answer policy.</p>}</article>}</div>
  </div>;
}
