"""Add auditable AI interview-turn suggestions."""

from alembic import op

revision = "20260716_0002"
down_revision = "20260715_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE interview_turn_suggestions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            source_id uuid NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
            transcript_id uuid NOT NULL REFERENCES transcripts(id) ON DELETE CASCADE,
            job_id uuid REFERENCES background_jobs(id),
            chunk_id uuid REFERENCES chunks(id),
            start_seconds float NOT NULL,
            end_seconds float NOT NULL,
            suggested_role varchar(40) NOT NULL,
            cleaned_text text NOT NULL,
            confidence float NOT NULL,
            rationale text NOT NULL DEFAULT '',
            segment_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
            status varchar(40) NOT NULL DEFAULT 'pending',
            model varchar(160) NOT NULL,
            reviewed_by uuid REFERENCES users(id),
            reviewed_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.create_index(
        "ix_interview_turn_suggestions_source_status",
        "interview_turn_suggestions",
        ["source_id", "status"],
    )


def downgrade() -> None:
    op.drop_table("interview_turn_suggestions")
