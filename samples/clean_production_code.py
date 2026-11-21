"""Clean Reference Implementation for CodeLens Baseline Quality Auditing.

Exemplifies best software engineering practices:
- Type annotations across all public APIs (PEP 484)
- Google-style docstrings with Args and Returns
- Strict context managers for deterministic resource management
- Parameterized safe interfaces
- Clean exception hierarchies
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from pathlib import Path


@dataclass(frozen=True)
class ServiceConfig:
    """Immutable configuration container for external services."""
    service_name: str
    timeout_seconds: int = 30
    retry_limit: int = 3


class SafeDataProcessor:
    """Demonstrates modular, thread-safe, and well-typed data processing."""

    def __init__(self, config: ServiceConfig) -> None:
        self.config = config

    def deduplicate_items(self, items: List[str]) -> List[str]:
        """Deduplicates items in O(N) time preserving order.

        Args:
            items: A list of string values to deduplicate.

        Returns:
            A new list containing unique elements in their first-seen order.
        """
        seen = set()
        unique = []
        for item in items:
            normalized = item.strip().casefold()
            if normalized not in seen:
                seen.add(normalized)
                unique.append(item.strip())
        return unique

    def safe_read_file(self, base_dir: Path, filename: str) -> Optional[str]:
        """Safely reads file contents preventing directory traversal.

        Args:
            base_dir: The allowed parent directory.
            filename: The relative file name to load.

        Returns:
            The UTF-8 content of the file, or None if not found or unauthorized.
        """
        try:
            target = (base_dir / filename).resolve()
            if not target.is_relative_to(base_dir.resolve()):
                return None
            if not target.is_file():
                return None
            return target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None
