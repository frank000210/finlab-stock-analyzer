"""
Session Integration: Automatically query knowledge base for context.

This module provides utilities to integrate knowledge base queries
into your session interactions.
"""

from __future__ import annotations

from knowledge_base.db import get_db
from knowledge_base.query import build_system_prompt_injection


class SessionContextManager:
    """Manages knowledge base context for current session."""

    def __init__(self):
        """Initialize the context manager."""
        self.db = get_db()
        self._cache = {}

    def get_context_for_question(
        self,
        question: str,
        top_k: int = 5,
        use_cache: bool = True,
        scope: str = "session",
    ) -> str:
        """
        Get knowledge base context for a question.

        Args:
            question: The user's question
            top_k: Number of results to retrieve
            use_cache: Cache results for same questions

        Returns:
            System prompt injection string ready to use
        """
        cache_key = f"{scope}:{question}:{top_k}"
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]

        injection = build_system_prompt_injection(self.db, question, top_k=top_k, scope=scope)
        if use_cache:
            self._cache[cache_key] = injection

        return injection

    def clear_cache(self) -> None:
        """Clear the context cache."""
        self._cache.clear()

    def __enter__(self) -> SessionContextManager:
        """Context manager entry."""
        return self

    def __exit__(self, *args) -> None:
        """Context manager exit."""
        self.clear_cache()


# Global instance for easy access
_context_manager: SessionContextManager | None = None


def get_context_manager() -> SessionContextManager:
    """Get or create global context manager."""
    global _context_manager
    if _context_manager is None:
        _context_manager = SessionContextManager()
    return _context_manager


def get_knowledge_context(question: str, top_k: int = 5, scope: str = "session") -> str:
    """
    Quick function to get knowledge context for a question.

    Usage:
        from knowledge_base.session_integration import get_knowledge_context
        
        context = get_knowledge_context("how to deploy to production")
        # Use context in your system prompt

    Args:
        question: The user's question or task
        top_k: Number of knowledge items to retrieve

    Returns:
        Formatted context string for system prompt injection
    """
    manager = get_context_manager()
    return manager.get_context_for_question(question, top_k=top_k, scope=scope)


def inject_knowledge_into_prompt(
    system_prompt: str,
    question: str,
    top_k: int = 5,
    scope: str = "session",
) -> str:
    """
    Inject knowledge base context into an existing system prompt.

    Usage:
        from knowledge_base.session_integration import inject_knowledge_into_prompt
        
        enhanced_prompt = inject_knowledge_into_prompt(
            system_prompt="You are a helpful assistant.",
            question="How should I architect this system?"
        )

    Args:
        system_prompt: Original system prompt
        question: User's question or current task
        top_k: Number of knowledge items to retrieve

    Returns:
        Enhanced system prompt with knowledge context prepended
    """
    context = get_knowledge_context(question, top_k=top_k, scope=scope)
    if not context:
        return system_prompt

    return f"{context}\n\n---\n\n{system_prompt}"


def format_as_json_context(question: str, top_k: int = 5, scope: str = "session") -> dict:
    """
    Get knowledge context as structured JSON for programmatic use.

    Returns:
        Dict with keys: context (str), results (list), question (str)
    """
    from knowledge_base.query import search_knowledge

    db = get_db()
    results = search_knowledge(db, question, top_k=top_k, scope=scope)

    return {
        "question": question,
        "num_results": len(results),
        "results": [
            {
                "type": r["type"],
                "title": r["doc"].get("title", r["doc"].get("slug", "Unknown")),
                "relevance_score": r["relevance_score"],
                "summary": r["doc"].get("summary", r["doc"].get("insight", ""))[:300],
            }
            for r in results
        ],
    }
