export type Founder = {
  id: string; slug: string; name: string; collection_name: string; biography: string; status: string;
};
export type Topic = { id: string; slug: string; name: string; description: string; parent_id: string | null };
export type Source = {
  id: string; founder_id: string; canonical_url: string; title: string; publisher: string | null;
  author: string | null; publication_date: string | null; content_type: string; source_tier: string;
  approval_status: string; speaker_verified: boolean; quality_score: number; underlying_work_id: string;
};
export type Citation = {
  source_id: string; title: string; publisher: string; publication_date: string | null; url: string;
  start_seconds: number | null; end_seconds: number | null; supporting_excerpt: string;
};
export type Answer = {
  answer: string; confidence: "high" | "medium" | "low"; evidence_summary: string;
  citations: Citation[]; contradictions: string[]; limitations: string[]; follow_up_questions: string[];
  provider: { name: string; model: string; is_mock: boolean };
};
