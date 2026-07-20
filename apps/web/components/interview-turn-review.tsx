"use client";

import { useCallback, useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

type MixedSource = {
  source_id: string;
  title: string;
  review_status: string;
  pending_turn_count: number;
  duration_seconds: number;
};

type InterviewTurn = {
  id: string;
  source_id: string;
  title: string;
  canonical_url: string;
  start_seconds: number;
  end_seconds: number;
  suggested_role: "iyin" | "interviewer" | "other" | "uncertain";
  cleaned_text: string;
  confidence: number;
  rationale: string;
};

function formatTime(seconds: number) {
  const rounded = Math.max(0, Math.round(seconds));
  return `${Math.floor(rounded / 60)}:${String(rounded % 60).padStart(2, "0")}`;
}

export function InterviewTurnReview() {
  const [sources, setSources] = useState<MixedSource[]>([]);
  const [sourceId, setSourceId] = useState("");
  const [turns, setTurns] = useState<InterviewTurn[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [message, setMessage] = useState("Loading mixed-speaker interviews…");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const sourceResponse = await fetch(
        `${API}/speaker-reviews?status=all&limit=200`,
        { credentials: "include" },
      );
      if (!sourceResponse.ok) throw new Error("Sources unavailable");
      const reviewedSources = await sourceResponse.json() as MixedSource[];
      const pendingSources = reviewedSources.filter(source => source.pending_turn_count > 0);
      setSources(pendingSources);
      const activeSource = sourceId && pendingSources.some(source => source.source_id === sourceId)
        ? sourceId
        : pendingSources[0]?.source_id || "";
      if (activeSource && activeSource !== sourceId) setSourceId(activeSource);
      if (!activeSource) {
        setMessage("No pending interview-turn suggestions are available.");
        return;
      }
      const turnResponse = await fetch(
        `${API}/interview-turns?source_id=${encodeURIComponent(activeSource)}&status=pending&limit=5000`,
        { credentials: "include" },
      );
      if (!turnResponse.ok) throw new Error("Turns unavailable");
      const suggestions = await turnResponse.json() as InterviewTurn[];
      setTurns(suggestions);
      setSelected(current => new Set(
        [...current].filter(id => suggestions.some(item => item.id === id)),
      ));
      setMessage(
        suggestions.length
          ? ""
          : "No pending suggestions. Select Analyze interview to reconstruct its flow.",
      );
    } catch {
      setMessage("The interview-turn review service is unavailable.");
    }
  }, [sourceId]);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 4000);
    return () => window.clearInterval(timer);
  }, [load]);

  async function analyze() {
    if (!sourceId) return;
    setBusy(true);
    setMessage("Queueing GPT interview-flow analysis…");
    try {
      const response = await fetch(`${API}/interview-turns/analyze`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": sessionStorage.getItem("afs_csrf") ?? "",
        },
        body: JSON.stringify({ source_id: sourceId }),
      });
      const result = await response.json() as {
        message?: string;
        error?: { message?: string };
      };
      setMessage(
        response.ok
          ? result.message ?? "Analysis queued."
          : result.error?.message ?? "Analysis could not be queued.",
      );
    } catch {
      setMessage("The interview analysis service is unavailable.");
    } finally {
      setBusy(false);
    }
  }

  function toggle(id: string) {
    setSelected(current => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function review(decision: "approve_as_iyin" | "reject") {
    if (!selected.size) return;
    const verb = decision === "approve_as_iyin"
      ? "approve the selected passages as Iyin"
      : "reject the selected suggestions";
    if (!window.confirm(`Confirm that you want to ${verb}?`)) return;
    const note = window.prompt("Enter a short note describing what you checked:");
    if (!note || note.trim().length < 3) return;
    setBusy(true);
    try {
      const response = await fetch(`${API}/interview-turns/review`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": sessionStorage.getItem("afs_csrf") ?? "",
        },
        body: JSON.stringify({
          suggestion_ids: [...selected],
          decision,
          note: note.trim(),
        }),
      });
      const result = await response.json() as {
        reviewed_count?: number;
        approved_chunk_count?: number;
        error?: { message?: string };
      };
      if (!response.ok) {
        setMessage(result.error?.message ?? "Review failed.");
        return;
      }
      setSelected(new Set());
      await load();
      setMessage(
        `Reviewed ${result.reviewed_count ?? 0} turns; `
        + `${result.approved_chunk_count ?? 0} RAG chunks were approved.`,
      );
    } catch {
      setMessage("The interview review service is unavailable.");
    } finally {
      setBusy(false);
    }
  }

  const suggestedIyin = turns.filter(item => item.suggested_role === "iyin");
  return <div className="grid gap-5">
    <section className="rounded-xl border border-[var(--forest)] bg-[#eef5ef] p-5">
      <p className="eyebrow">AI-assisted interview review</p>
      <h2 className="mt-2 text-2xl">Reconstruct questions and answers from captions</h2>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--muted)]">
        GPT-5.4 nano suggests Iyin, interviewer, other, or uncertain turns. Nothing
        enters public RAG until you verify it against the timestamped video.
      </p>
      <div className="mt-4 flex flex-wrap gap-3">
        <select
          value={sourceId}
          onChange={event => {
            setSourceId(event.target.value);
            setSelected(new Set());
          }}
          className="min-w-0 flex-1 rounded-lg border border-[var(--line)] bg-white px-3 py-2 text-sm"
        >
          {sources.map(source => <option key={source.source_id} value={source.source_id}>
            {source.title} ({source.pending_turn_count} pending, {formatTime(source.duration_seconds)})
          </option>)}
        </select>
        <button
          type="button"
          onClick={() => void analyze()}
          disabled={!sourceId || busy}
          className="rounded-full bg-[var(--forest)] px-5 py-2.5 text-sm font-bold text-white disabled:opacity-50"
        >
          {busy ? "Working…" : "Analyze interview"}
        </button>
      </div>
    </section>
    {message && <p role="status" className="rounded-xl border border-[var(--line)] bg-white p-4 text-sm text-[var(--muted)]">{message}</p>}
    {turns.length > 0 && <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[var(--line)] bg-white p-4">
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => setSelected(new Set(suggestedIyin.map(item => item.id)))}
          className="rounded-full border border-[var(--forest)] px-4 py-2 text-sm font-bold"
        >
          Select suggested Iyin ({suggestedIyin.length})
        </button>
        <button
          type="button"
          onClick={() => setSelected(new Set(turns.map(item => item.id)))}
          className="rounded-full border border-[var(--line)] px-4 py-2 text-sm font-bold"
        >
          Select all ({turns.length})
        </button>
        {selected.size > 0 && <button
          type="button"
          onClick={() => setSelected(new Set())}
          className="rounded-full border border-[var(--line)] px-4 py-2 text-sm font-bold text-[var(--muted)]"
        >
          Clear
        </button>}
        <span className="text-sm text-[var(--muted)]">{selected.size} selected</span>
      </div>
      <div className="flex gap-2">
        <button type="button" disabled={!selected.size || busy} onClick={() => void review("reject")} className="rounded-full border border-red-700 px-4 py-2 text-sm font-bold text-red-800 disabled:opacity-40">Reject</button>
        <button type="button" disabled={!selected.size || busy} onClick={() => void review("approve_as_iyin")} className="rounded-full bg-[var(--forest)] px-4 py-2 text-sm font-bold text-white disabled:opacity-40">Approve as Iyin</button>
      </div>
    </div>}
    <div className="grid gap-3">
      {turns.map(turn => <article key={turn.id} className={`rounded-xl border bg-white p-5 ${selected.has(turn.id) ? "border-[var(--forest)] ring-2 ring-[var(--forest)]/20" : "border-[var(--line)]"}`}>
        <div className="grid gap-4 md:grid-cols-[28px_1fr_auto]">
          <input
            type="checkbox"
            checked={selected.has(turn.id)}
            onChange={() => toggle(turn.id)}
            aria-label={`Select ${turn.suggested_role} turn at ${formatTime(turn.start_seconds)}`}
            className="mt-1 h-5 w-5"
          />
          <div>
            <div className="flex flex-wrap gap-2">
              <span className={`rounded-full px-2.5 py-1 text-xs font-bold uppercase ${turn.suggested_role === "iyin" ? "bg-emerald-100 text-emerald-900" : turn.suggested_role === "uncertain" ? "bg-amber-100 text-amber-900" : "bg-stone-100 text-stone-800"}`}>{turn.suggested_role}</span>
              <span className="text-xs text-[var(--muted)]">{formatTime(turn.start_seconds)}–{formatTime(turn.end_seconds)} · {Math.round(turn.confidence * 100)}% confidence</span>
            </div>
            <p className="mt-3 text-sm leading-6">{turn.cleaned_text}</p>
            <p className="mt-2 text-xs leading-5 text-[var(--muted)]">{turn.rationale}</p>
          </div>
          <a href={turn.canonical_url} target="_blank" rel="noreferrer" className="self-start rounded-full border border-[var(--forest)] px-4 py-2 text-sm font-bold no-underline">Verify video ↗</a>
        </div>
      </article>)}
    </div>
  </div>;
}
