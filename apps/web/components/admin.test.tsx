import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import {
  CandidateQueue,
  LoginForm,
  ProcessingJobs,
  SpeakerReviewQueue,
} from "./admin";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

it("shows and hides the administrator password accessibly", () => {
  render(<LoginForm />);
  const password = screen.getByLabelText("Password");
  expect(password).toHaveAttribute("type", "password");

  fireEvent.click(screen.getByRole("button", { name: "Show password" }));
  expect(password).toHaveAttribute("type", "text");
  expect(screen.getByRole("button", { name: "Hide password" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
});

it("bulk approves every pending candidate currently shown after confirmation", async () => {
  const candidates = [
    {
      id: "candidate-1",
      title: "First candidate",
      normalized_url: "https://example.com/first",
      publisher: "Example",
      score: 80,
      robots_status: "allowed",
      score_breakdown: {},
    },
    {
      id: "candidate-2",
      title: "Second candidate",
      normalized_url: "https://example.com/second",
      publisher: "Example",
      score: 75,
      robots_status: "allowed",
      score_breakdown: {},
    },
  ];
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(new Response(JSON.stringify(candidates), { status: 200 }))
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ approved_count: 2, skipped_count: 0 }), {
        status: 200,
      }),
    )
    .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }));
  vi.spyOn(window, "confirm").mockReturnValue(true);

  render(<CandidateQueue />);
  fireEvent.click(await screen.findByRole("button", { name: "Approve all 2" }));

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
  const request = fetchMock.mock.calls[1]!;
  expect(request[0]).toContain("/candidates/bulk-approve");
  expect(JSON.parse(String((request[1] as RequestInit).body))).toMatchObject({
    candidate_ids: ["candidate-1", "candidate-2"],
    source_tier: "B",
  });
  expect(await screen.findByText("Approved 2 candidates.")).toBeVisible();
});

it("queues Zyte approved-source processing with paid transcription disabled", async () => {
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
    .mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          queued_count: 4,
          message: "Public-caption processing was queued.",
          estimated_zyte_cost_usd_max: 0.00266,
        }),
        { status: 202 },
      ),
    )
    .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }));
  vi.spyOn(window, "confirm").mockReturnValue(true);

  render(<ProcessingJobs />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Process remaining with Zyte" }),
  );

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
  const request = fetchMock.mock.calls[1]!;
  expect(request[0]).toContain("/sources/process-approved");
  expect(JSON.parse(String((request[1] as RequestInit).body))).toEqual({
    limit: 200,
    captions_only: true,
    use_zyte_proxy: true,
  });
  expect(
    await screen.findByText(
      "Queued 4 approved sources through Zyte. Maximum estimated batch cost: $0.0027.",
    ),
  ).toBeVisible();
});

it("requires explicit selection and confirmation before verifying a speaker", async () => {
  const review = {
    source_id: "source-1",
    title: "Iyinoluwa Aboyeji keynote",
    publisher: "Conference",
    canonical_url: "https://www.youtube.com/watch?v=abcdefghijk",
    speaker_verified: false,
    founder_name: "Iyinoluwa Aboyeji",
    review_status: "pending",
    chunk_count: 12,
    duration_seconds: 1200,
    title_mentions_founder: true,
    excerpt: "Thank you for inviting me to speak about building companies.",
  };
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(new Response(JSON.stringify([review]), { status: 200 }))
    .mockResolvedValueOnce(
      new Response(
        JSON.stringify({ reviewed_count: 1, updated_chunk_count: 12 }),
        { status: 200 },
      ),
    )
    .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }));
  vi.spyOn(window, "confirm").mockReturnValue(true);
  vi.spyOn(window, "prompt").mockReturnValue("Checked the complete keynote video.");

  render(<SpeakerReviewQueue />);
  fireEvent.click(
    await screen.findByRole("checkbox", {
      name: "Select Iyinoluwa Aboyeji keynote",
    }),
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Verify single speaker" }),
  );

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
  const request = fetchMock.mock.calls[1]!;
  expect(request[0]).toContain("/speaker-reviews/bulk");
  expect(JSON.parse(String((request[1] as RequestInit).body))).toEqual({
    source_ids: ["source-1"],
    decision: "verified_single_speaker",
    note: "Checked the complete keynote video.",
  });
  expect(
    await screen.findByText("Reviewed 1 sources and updated 12 chunks."),
  ).toBeVisible();
});
