"""Read-only, session-scoped evidence assistant. No inference or training imports."""

from .service import EvidenceAssistant

__all__ = ["EvidenceAssistant"]
