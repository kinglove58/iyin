import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { AskForm } from "./ask-form";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

it("sends conversation history and renders timestamped cited evidence", async () => {
  const answer = {
    answer: "He emphasized practical learning [1].",
    confidence: "high",
    evidence_summary: "One approved segment directly supports the answer.",
    citations: [{
      source_id: "source-1",
      title: "Public interview",
      publisher: "Example channel",
      publication_date: null,
      url: "https://www.youtube.com/watch?v=example&t=42",
      start_seconds: 42,
      end_seconds: 60,
      supporting_excerpt: "Business is practical learning.",
    }],
    contradictions: [],
    limitations: [],
    follow_up_questions: [],
    provider: { name: "openai", model: "gpt-5.6-luna", is_mock: false },
  };
  const fetchMock = vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(new Response(JSON.stringify(answer), { status: 200 }))
    .mockResolvedValueOnce(new Response(JSON.stringify(answer), { status: 200 }));

  render(<AskForm />);
  const composer = screen.getByLabelText("Ask a research question");
  fireEvent.change(composer, { target: { value: "What did he say about business?" } });
  fireEvent.click(screen.getByRole("button", { name: "Send question" }));

  expect(await screen.findByText(/He emphasized practical learning/)).toBeVisible();
  expect(screen.getByText(/0:42/)).toBeVisible();

  fireEvent.change(composer, { target: { value: "Can you explain that further?" } });
  fireEvent.click(screen.getByRole("button", { name: "Send question" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  const secondBody = JSON.parse(String((fetchMock.mock.calls[1]?.[1] as RequestInit).body));
  expect(secondBody.history).toEqual([
    { role: "user", content: "What did he say about business?" },
    { role: "assistant", content: "He emphasized practical learning [1]." },
  ]);
});
