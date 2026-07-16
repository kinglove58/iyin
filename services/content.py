import hashlib
import re
from dataclasses import dataclass

PROMPT_INJECTION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"ignore (all |any )?(previous|prior|system) instructions",
        r"reveal (the )?(system prompt|secrets?|api keys?)",
        r"you are now",
        r"invoke (a )?tool",
        r"developer message",
    )
]


def content_hash(content: str) -> str:
    normalized = re.sub(r"\s+", " ", content).strip()
    return hashlib.sha256(normalized.encode()).hexdigest()


def prompt_injection_flags(content: str) -> list[str]:
    return ["possible_prompt_injection"] if any(p.search(content) for p in PROMPT_INJECTION_PATTERNS) else []


@dataclass(frozen=True)
class SemanticChunk:
    text: str
    section_title: str | None
    start_character: int
    end_character: int
    token_count: int
    quality_flags: list[str]


def semantic_chunks(content: str, *, target_words: int = 180, max_words: int = 320) -> list[SemanticChunk]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", content) if p.strip()]
    chunks: list[SemanticChunk] = []
    buffer: list[str] = []
    section: str | None = None

    def flush() -> None:
        if not buffer:
            return
        text = "\n\n".join(buffer)
        start = content.find(buffer[0])
        chunks.append(
            SemanticChunk(
                text=text,
                section_title=section,
                start_character=max(0, start),
                end_character=max(0, start) + len(text),
                token_count=max(1, round(len(text.split()) * 1.3)),
                quality_flags=prompt_injection_flags(text),
            )
        )
        buffer.clear()

    for paragraph in paragraphs:
        if len(paragraph.split()) <= 12 and (paragraph.endswith(":") or paragraph.startswith("#")):
            flush()
            section = paragraph.lstrip("# ").rstrip(":")
            continue
        prospective = sum(len(item.split()) for item in buffer) + len(paragraph.split())
        if buffer and prospective > max_words:
            if sum(len(item.split()) for item in buffer) <= 20:
                # Keep a short interview question or lead-in with its complete answer.
                buffer.append(paragraph)
                flush()
                continue
            flush()
        buffer.append(paragraph)
        if sum(len(item.split()) for item in buffer) >= target_words and paragraph[-1:] in ".?!\"”":
            flush()
    flush()
    return chunks
