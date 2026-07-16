"""Initial evidence, research, RAG, access, and operations schema."""

from alembic import op
from apps.api.afs.models import Base

revision = "20260715_0001"
down_revision = None
branch_labels = None
depends_on = None

ANCILLARY_SQL = """
CREATE TABLE roles (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), name varchar(80) UNIQUE NOT NULL);
CREATE TABLE user_roles (user_id uuid REFERENCES users(id) ON DELETE CASCADE, role_id uuid REFERENCES roles(id) ON DELETE CASCADE, PRIMARY KEY(user_id, role_id));
CREATE TABLE founder_aliases (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), founder_id uuid NOT NULL REFERENCES founders(id) ON DELETE CASCADE, alias varchar(200) NOT NULL, UNIQUE(founder_id, alias));
CREATE TABLE founder_topics (founder_id uuid REFERENCES founders(id) ON DELETE CASCADE, topic_id uuid REFERENCES topics(id) ON DELETE CASCADE, PRIMARY KEY(founder_id, topic_id));
CREATE TABLE discovery_queries (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), query text NOT NULL, provider varchar(80) NOT NULL, active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE discovery_runs (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), status varchar(40) NOT NULL, raw_results integer NOT NULL DEFAULT 0, unique_results integer NOT NULL DEFAULT 0, created_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz);
CREATE TABLE candidate_reviews (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), candidate_id uuid NOT NULL REFERENCES source_candidates(id), reviewer_id uuid REFERENCES users(id), decision varchar(40) NOT NULL, note text, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE domain_policies (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), domain varchar(255) UNIQUE NOT NULL, policy varchar(30) NOT NULL, emergency_stop boolean NOT NULL DEFAULT false, note text, updated_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE raw_artifacts (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), source_id uuid REFERENCES sources(id), object_key text UNIQUE NOT NULL, sha256 varchar(64) NOT NULL, media_type varchar(200), byte_size bigint NOT NULL, immutable boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE source_versions (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), source_id uuid NOT NULL REFERENCES sources(id) ON DELETE CASCADE, version integer NOT NULL, raw_artifact_id uuid REFERENCES raw_artifacts(id), cleaned_text text, content_hash varchar(64), created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(source_id, version));
ALTER TABLE sources ADD CONSTRAINT fk_source_raw_artifact FOREIGN KEY(raw_artifact_id) REFERENCES raw_artifacts(id);
ALTER TABLE chunks ADD CONSTRAINT fk_chunk_source_version FOREIGN KEY(source_version_id) REFERENCES source_versions(id);
CREATE TABLE source_people (source_id uuid REFERENCES sources(id) ON DELETE CASCADE, person_name varchar(240) NOT NULL, role varchar(80) NOT NULL, PRIMARY KEY(source_id, person_name, role));
CREATE TABLE source_topics (source_id uuid REFERENCES sources(id) ON DELETE CASCADE, topic_id uuid REFERENCES topics(id) ON DELETE CASCADE, confidence float, PRIMARY KEY(source_id, topic_id));
CREATE TABLE source_relationships (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), source_id uuid REFERENCES sources(id) ON DELETE CASCADE, related_source_id uuid REFERENCES sources(id) ON DELETE CASCADE, relationship varchar(40) NOT NULL, UNIQUE(source_id, related_source_id, relationship));
CREATE TABLE crawl_attempts (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), source_id uuid REFERENCES sources(id), url text NOT NULL, robots_decision varchar(60) NOT NULL, strategy varchar(80), status varchar(40) NOT NULL, http_status integer, latency_ms integer, estimated_cost_usd numeric(12,6) NOT NULL DEFAULT 0, crawled_at timestamptz NOT NULL DEFAULT now(), error text);
CREATE TABLE extraction_attempts (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), source_id uuid REFERENCES sources(id), strategy varchar(80) NOT NULL, confidence float, meaningful boolean NOT NULL DEFAULT false, status varchar(40) NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), error text);
CREATE TABLE media_assets (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), source_id uuid REFERENCES sources(id), platform varchar(60), platform_id varchar(200), object_key text, duration_seconds float, metadata jsonb NOT NULL DEFAULT '{}'::jsonb);
CREATE TABLE transcripts (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), source_id uuid REFERENCES sources(id), media_asset_id uuid REFERENCES media_assets(id), pathway varchar(80) NOT NULL, language varchar(20), review_status varchar(40) NOT NULL DEFAULT 'pending', created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE speakers (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), founder_id uuid REFERENCES founders(id), name varchar(240) NOT NULL, role varchar(80) NOT NULL);
CREATE TABLE transcript_segments (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), transcript_id uuid REFERENCES transcripts(id) ON DELETE CASCADE, speaker_id uuid REFERENCES speakers(id), start_seconds float NOT NULL, end_seconds float NOT NULL, text text NOT NULL, speaker_confidence float, transcription_confidence float, review_status varchar(40) NOT NULL DEFAULT 'pending');
CREATE TABLE speaker_assignments (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), segment_id uuid REFERENCES transcript_segments(id) ON DELETE CASCADE, speaker_id uuid REFERENCES speakers(id), assigned_by uuid REFERENCES users(id), confidence float, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE chunk_topics (chunk_id uuid REFERENCES chunks(id) ON DELETE CASCADE, topic_id uuid REFERENCES topics(id) ON DELETE CASCADE, confidence float, PRIMARY KEY(chunk_id, topic_id));
CREATE TABLE embeddings (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), chunk_id uuid REFERENCES chunks(id) ON DELETE CASCADE, provider varchar(80) NOT NULL, model varchar(160) NOT NULL, version varchar(80) NOT NULL, vector vector(1536), token_count integer NOT NULL DEFAULT 0, created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(chunk_id, provider, model, version));
CREATE INDEX ix_embeddings_vector_hnsw ON embeddings USING hnsw (vector vector_cosine_ops);
CREATE TABLE search_documents (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), chunk_id uuid UNIQUE REFERENCES chunks(id) ON DELETE CASCADE, document tsvector NOT NULL);
CREATE INDEX ix_search_documents_document ON search_documents USING gin(document);
CREATE TABLE source_claims (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), source_id uuid REFERENCES sources(id), chunk_id uuid REFERENCES chunks(id), claim text NOT NULL, confidence float, review_status varchar(40) NOT NULL DEFAULT 'pending');
CREATE TABLE quotations (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), source_id uuid REFERENCES sources(id), chunk_id uuid REFERENCES chunks(id), text text NOT NULL, start_seconds float, end_seconds float, verified boolean NOT NULL DEFAULT false);
CREATE TABLE job_events (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), job_id uuid REFERENCES background_jobs(id) ON DELETE CASCADE, event varchar(80) NOT NULL, details jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE api_usage_records (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), provider varchar(80) NOT NULL, operation varchar(80) NOT NULL, tokens_in integer NOT NULL DEFAULT 0, tokens_out integer NOT NULL DEFAULT 0, latency_ms integer, correlation_id varchar(100), created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE provider_cost_records (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), provider varchar(80) NOT NULL, operation varchar(80) NOT NULL, units numeric(16,6) NOT NULL, estimated_cost_usd numeric(12,6) NOT NULL, job_id uuid REFERENCES background_jobs(id), created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE evaluation_sets (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), version varchar(40) UNIQUE NOT NULL, description text, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE evaluation_questions (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), set_id uuid REFERENCES evaluation_sets(id) ON DELETE CASCADE, category varchar(80) NOT NULL, question text NOT NULL, expected jsonb NOT NULL DEFAULT '{}'::jsonb);
CREATE TABLE evaluation_runs (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), set_id uuid REFERENCES evaluation_sets(id), status varchar(40) NOT NULL, metrics jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz);
CREATE TABLE evaluation_results (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), run_id uuid REFERENCES evaluation_runs(id) ON DELETE CASCADE, question_id uuid REFERENCES evaluation_questions(id), metrics jsonb NOT NULL DEFAULT '{}'::jsonb, answer jsonb);
CREATE TABLE user_queries (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid REFERENCES users(id), founder_id uuid REFERENCES founders(id), question text NOT NULL, confidence varchar(20), citation_count integer NOT NULL DEFAULT 0, refused boolean NOT NULL DEFAULT false, latency_ms integer, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE answer_feedback (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), query_id uuid REFERENCES user_queries(id), user_id uuid REFERENCES users(id), rating integer, comment text, created_at timestamptz NOT NULL DEFAULT now());
"""


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    Base.metadata.create_all(bind=op.get_bind())
    # asyncpg prepared statements accept one command at a time.
    for statement in ANCILLARY_SQL.split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
    op.execute("DROP EXTENSION IF EXISTS vector")
