"""
Shared schemas for document, chunk, and answer objects.
This is the single source of truth - DO NOT modify without updating all consumers.

Owner: All team (Trang, Chi, Thanh)
Contract version: 1.0.0
"""
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class DocumentType(str, Enum):
    LAW = "law"
    REGULATION = "regulation"
    POLICY = "policy"
    GUIDELINE = "guideline"
    FRAMEWORK = "framework"
    RECOMMENDATION = "recommendation"
    STRATEGY = "strategy"
    STANDARD = "standard"


class ParseStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    EMPTY = "empty"
    SCAN_DETECTED = "scan_detected"


class AnswerStatus(str, Enum):
    ANSWERED = "answered"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    ERROR = "error"


@dataclass
class RawDocument:
    """Represents a document as downloaded from source, before any parsing."""
    document_id: str
    version_id: str
    source_url: str
    file_url: Optional[str]
    raw_path: str
    file_format: str          # pdf, html, docx
    jurisdiction: str         # VN, EU, International, ASEAN
    language: str             # vi, en
    document_type: DocumentType
    collected_at: str         # ISO 8601
    content_hash: str         # SHA-256 of raw file
    parse_status: ParseStatus = ParseStatus.SUCCESS
    title: Optional[str] = None
    issued_date: Optional[str] = None
    effective_date: Optional[str] = None


@dataclass
class ProcessedDocument:
    """Represents a document after text extraction and ETL cleaning."""
    document_id: str
    version_id: str
    title: str
    text: str
    document_type: DocumentType
    source_url: str
    raw_path: str
    jurisdiction: str
    language: str
    pipeline_version: str
    content_hash: str
    parse_status: ParseStatus
    article: Optional[str] = None
    section: Optional[str] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    issued_date: Optional[str] = None
    effective_date: Optional[str] = None
    legal_status: str = "unknown"


@dataclass
class Chunk:
    """A text chunk ready for embedding and indexing into Qdrant."""
    chunk_id: str             # stable ID = sha256(document_id + version_id + chunk_index + text[:100])
    document_id: str
    version_id: str
    title: str
    text: str
    source_url: str
    jurisdiction: str
    language: str
    document_type: DocumentType
    article: Optional[str] = None
    section: Optional[str] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    chunk_index: int = 0
    embedding_model: Optional[str] = None
    indexed_at: Optional[str] = None  # ISO 8601


@dataclass
class Citation:
    """A source citation attached to an answer."""
    source_id: str            # e.g., "S1", "S2" as referenced in the answer text
    chunk_id: str
    document_id: str
    title: str
    excerpt: str              # Relevant text snippet
    location: Optional[str] = None      # article/section/page reference
    source_url: Optional[str] = None


@dataclass
class AnswerResult:
    """The final output of the RAG answering pipeline."""
    status: AnswerStatus
    answer: Optional[str] = None
    citations: List[Citation] = field(default_factory=list)
    timings: dict = field(default_factory=dict)   # {"retrieval_ms": X, "generation_ms": Y}
    error_message: Optional[str] = None
