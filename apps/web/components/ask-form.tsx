"use client";

import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import type { Answer, Citation } from "@/lib/types";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
const STARTERS = [
  "What has Iyin said about building companies in Africa?",
  "How has he described talent and leadership?",
  "What are his views on fundraising and product-market fit?",
  "How has his thinking about infrastructure changed over time?",
];

type ChatMessage =
  | { id: string; role: "user"; content: string }
  | { id: string; role: "assistant"; content: string; answer: Answer };

function SourceIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true" className="h-4 w-4 fill-none stroke-current stroke-2"><path d="M14 3h7v7m0-7L10 14"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/></svg>;
}

function SendIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true" className="h-5 w-5 fill-none stroke-current stroke-2"><path d="m5 12 7-7 7 7M12 5v14"/></svg>;
}

function formatSeconds(value: number | null) {
  if (value === null) return "";
  const seconds = Math.max(0, Math.round(value));
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

function citedText(text: string, citations: Citation[]): ReactNode[] {
  return text.split(/(\[\d+\])/g).map((part, index) => {
    const match = part.match(/^\[(\d+)]$/);
    if (!match) return part;
    const citationIndex = Number(match[1]) - 1;
    const citation = citations[citationIndex];
    if (!citation) return part;
    return <a key={`${part}-${index}`} href={`#citation-${citation.source_id}-${citationIndex}`} className="mx-0.5 inline-grid h-5 min-w-5 place-items-center rounded-full bg-[var(--forest-light)] px-1.5 text-xs font-bold text-[var(--forest)] no-underline" aria-label={`See source ${citationIndex + 1}`}>{citationIndex + 1}</a>;
  });
}

function AssistantAnswer({ answer }: { answer: Answer }) {
  return <div className="min-w-0">
    <div className="flex flex-wrap items-center gap-2">
      <span className={`rounded-full px-2.5 py-1 text-[11px] font-bold uppercase tracking-wide ${answer.confidence === "high" ? "bg-emerald-100 text-emerald-900" : answer.confidence === "medium" ? "bg-amber-100 text-amber-900" : "bg-stone-200 text-stone-800"}`}>{answer.confidence} confidence</span>
      <span className="text-xs text-[var(--muted)]">{answer.provider.is_mock ? "Demo answer" : "Answer grounded in the public collection"}</span>
    </div>
    <div className="mt-4 grid gap-4 text-[15px] leading-7 text-[#25312a]">
      {answer.answer.split(/\n{2,}/).map((paragraph, index) => <p key={index}>{citedText(paragraph, answer.citations)}</p>)}
    </div>
    {answer.evidence_summary && <p className="mt-5 border-l-2 border-[var(--ochre)] pl-4 text-sm leading-6 text-[var(--muted)]">{answer.evidence_summary}</p>}
    {answer.citations.length > 0 && <section className="mt-7">
      <h3 className="text-sm font-bold">Sources</h3>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        {answer.citations.map((citation, index) => <a id={`citation-${citation.source_id}-${index}`} href={citation.url} target="_blank" rel="noreferrer" key={`${citation.source_id}-${citation.start_seconds}-${index}`} className="group rounded-xl border border-[var(--line)] bg-[#fffdf8] p-4 no-underline transition hover:border-[var(--forest)] hover:shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <span className="grid h-7 w-7 place-items-center rounded-full bg-[var(--forest)] text-xs font-bold text-white">{index + 1}</span>
            <span className="flex items-center gap-1 text-xs font-bold text-[var(--forest)]">Open source <SourceIcon /></span>
          </div>
          <h4 className="serif mt-3 line-clamp-2 font-bold leading-5">{citation.title}</h4>
          <p className="mt-2 text-xs text-[var(--muted)]">{citation.publisher}{citation.publication_date ? ` · ${citation.publication_date}` : ""}{citation.start_seconds !== null ? ` · ${formatSeconds(citation.start_seconds)}` : ""}</p>
          <p className="mt-3 line-clamp-3 text-xs leading-5 text-[var(--muted)]">“{citation.supporting_excerpt}”</p>
        </a>)}
      </div>
    </section>}
    {answer.limitations.length > 0 && <details className="mt-5 rounded-xl bg-[#f3eee4] px-4 py-3 text-sm">
      <summary className="cursor-pointer font-bold">Evidence limitations</summary>
      <ul className="mt-3 list-disc space-y-2 pl-5 text-[var(--muted)]">{answer.limitations.map(item => <li key={item}>{item}</li>)}</ul>
    </details>}
  </div>;
}

export function AskForm({ initialQuestion = "" }: { initialQuestion?: string }) {
  const [question, setQuestion] = useState(initialQuestion);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ behavior: "smooth", block: "end" });
  }, [messages, loading]);

  async function ask(nextQuestion: string) {
    const trimmed = nextQuestion.trim();
    if (trimmed.length < 5 || loading) return;
    const history = messages.slice(-10).map(message => ({
      role: message.role,
      content: message.content,
    }));
    const userMessage: ChatMessage = { id: crypto.randomUUID(), role: "user", content: trimmed };
    setMessages(current => [...current, userMessage]);
    setQuestion("");
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${API}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: trimmed, history }),
      });
      const payload = await response.json() as Answer & { error?: { message?: string } };
      if (!response.ok) throw new Error(payload.error?.message ?? "The research API could not process this question.");
      setMessages(current => [...current, { id: crypto.randomUUID(), role: "assistant", content: payload.answer, answer: payload }]);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unexpected request failure.");
    } finally {
      setLoading(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void ask(question);
  }

  return <div className="grid min-h-[calc(100vh-73px)] lg:grid-cols-[260px_minmax(0,1fr)]">
    <aside className="hidden border-r border-[var(--line)] bg-[#eee9df] p-4 lg:block">
      <button type="button" onClick={() => { setMessages([]); setQuestion(""); setError(""); }} className="flex w-full items-center gap-3 rounded-xl border border-[var(--line)] bg-[var(--card)] px-4 py-3 text-left text-sm font-bold shadow-sm">
        <span className="text-xl text-[var(--forest)]">+</span> New research chat
      </button>
      <div className="mt-7 px-2">
        <p className="eyebrow">This collection</p>
        <p className="mt-3 text-sm font-bold">Iyinoluwa Aboyeji</p>
        <p className="mt-2 text-xs leading-5 text-[var(--muted)]">Explore lessons drawn from Iyin&apos;s public talks and interviews. Every useful answer leads back to the original source.</p>
      </div>
      <div className="mt-8 border-t border-[var(--line)] px-2 pt-5 text-xs leading-5 text-[var(--muted)]">Built as a learning project for Africa&apos;s next generation of builders.</div>
    </aside>

    <section className="relative flex min-w-0 flex-col bg-[var(--paper)]">
      <div className="border-b border-[var(--line)] bg-[var(--paper)]/95 px-5 py-4 backdrop-blur lg:px-8">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-4">
          <div><p className="serif text-lg font-bold">Ask Iyin&apos;s public ideas</p><p className="text-xs text-[var(--muted)]">Clear answers with links to the original moment</p></div>
          {messages.length > 0 && <button type="button" onClick={() => setMessages([])} className="rounded-full border border-[var(--line)] px-3 py-1.5 text-xs font-bold lg:hidden">New chat</button>}
        </div>
      </div>

      <div className="flex-1 px-5 pb-44 pt-8 lg:px-8">
        <div className="mx-auto max-w-3xl">
          {messages.length === 0 && <div className="grid min-h-[52vh] content-center">
            <div className="grid h-14 w-14 place-items-center rounded-2xl bg-[var(--forest)] text-lg font-bold text-white shadow-lg">AF</div>
            <h1 className="serif mt-6 text-4xl leading-tight md:text-5xl">What would you like to understand?</h1>
            <p className="mt-4 max-w-2xl text-base leading-7 text-[var(--muted)]">Ask about Iyinoluwa Aboyeji&apos;s experience, convictions and advice. The assistant brings together what he has shared publicly and shows where each idea came from.</p>
            <div className="mt-8 grid gap-3 sm:grid-cols-2">{STARTERS.map(starter => <button type="button" key={starter} onClick={() => void ask(starter)} className="rounded-xl border border-[var(--line)] bg-[var(--card)] p-4 text-left text-sm leading-6 transition hover:border-[var(--forest)] hover:shadow-sm">{starter}</button>)}</div>
          </div>}
          {messages.length > 0 && <div className="grid gap-8">
            {messages.map(message => message.role === "user"
              ? <div key={message.id} className="flex justify-end"><div className="max-w-[85%] rounded-3xl rounded-br-lg bg-[var(--forest)] px-5 py-3 text-[15px] leading-6 text-white">{message.content}</div></div>
              : <article key={message.id} className="grid grid-cols-[34px_minmax(0,1fr)] gap-4">
                  <div className="grid h-8 w-8 place-items-center rounded-lg bg-[var(--ochre)] text-xs font-bold text-white">AF</div>
                  <AssistantAnswer answer={message.answer} />
                </article>)}
            {loading && <div className="grid grid-cols-[34px_minmax(0,1fr)] gap-4">
              <div className="grid h-8 w-8 place-items-center rounded-lg bg-[var(--ochre)] text-xs font-bold text-white">AF</div>
              <div className="pt-1 text-sm text-[var(--muted)]"><span className="inline-flex gap-1"><i className="h-2 w-2 animate-pulse rounded-full bg-[var(--forest)]"/><i className="h-2 w-2 animate-pulse rounded-full bg-[var(--forest)] [animation-delay:150ms]"/><i className="h-2 w-2 animate-pulse rounded-full bg-[var(--forest)] [animation-delay:300ms]"/></span><span className="ml-3">Finding the most relevant moments and checking the source…</span></div>
            </div>}
          </div>}
          {error && <div role="alert" className="mt-6 rounded-xl border border-red-300 bg-red-50 p-4 text-sm text-red-800">{error}</div>}
          <div ref={endRef} />
        </div>
      </div>

      <div className="fixed inset-x-0 bottom-0 z-20 border-t border-[var(--line)] bg-[var(--paper)]/95 p-4 backdrop-blur lg:left-[260px]">
        <form onSubmit={submit} className="mx-auto max-w-3xl">
          <div className="flex items-end gap-2 rounded-2xl border border-[var(--line)] bg-white p-2 pl-4 shadow-[0_12px_35px_rgba(23,33,28,.12)] focus-within:border-[var(--forest)]">
            <textarea aria-label="Ask a research question" required minLength={5} maxLength={1000} rows={1} value={question} onChange={event => setQuestion(event.target.value)} onKeyDown={event => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void ask(question); } }} className="max-h-40 min-h-11 flex-1 resize-none border-0 bg-transparent py-2 text-[15px] outline-none" placeholder="Ask about building, belief, leadership or Africa’s future…" />
            <button aria-label="Send question" disabled={loading || question.trim().length < 5} className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-[var(--forest)] text-white disabled:bg-stone-300"><SendIcon /></button>
          </div>
          <p className="mt-2 text-center text-[11px] text-[var(--muted)]">AI can make mistakes. Open and verify the cited source before relying on an answer.</p>
        </form>
      </div>
    </section>
  </div>;
}
