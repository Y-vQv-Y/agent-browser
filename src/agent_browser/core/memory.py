"""
Working Memory - Internalized from GenericAgent's memory system.
Provides layered memory for the agent: working memory, facts, SOPs.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    """A single memory entry."""
    key: str
    value: str
    category: str  # "fact", "sop", "insight", "context"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    access_count: int = 0


class WorkingMemory:
    """
    Layered memory system for the agent.
    L0: System prompt (hardcoded)
    L1: Working memory (current task context, key info)
    L2: Facts (learned environment facts, credentials references)
    L3: SOPs (standard operating procedures for recurring tasks)
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path("~/.agent-browser/memory").expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.working: dict[str, str] = {}  # L1: transient per-task
        self.facts: dict[str, MemoryEntry] = {}  # L2: persistent
        self.sops: dict[str, MemoryEntry] = {}  # L3: persistent
        self.conversation_history: list[dict[str, Any]] = []
        self.max_history = 50

        self._load()

    def _load(self):
        """Load persistent memory from disk."""
        facts_file = self.data_dir / "facts.json"
        sops_file = self.data_dir / "sops.json"

        if facts_file.exists():
            try:
                data = json.loads(facts_file.read_text())
                for k, v in data.items():
                    self.facts[k] = MemoryEntry(**v)
            except Exception as e:
                logger.warning("Failed to load facts: %s", e)

        if sops_file.exists():
            try:
                data = json.loads(sops_file.read_text())
                for k, v in data.items():
                    self.sops[k] = MemoryEntry(**v)
            except Exception as e:
                logger.warning("Failed to load SOPs: %s", e)

    def save(self):
        """Persist memory to disk."""
        self.data_dir.mkdir(parents=True, exist_ok=True)

        facts_data = {}
        for k, entry in self.facts.items():
            facts_data[k] = {
                "key": entry.key,
                "value": entry.value,
                "category": entry.category,
                "created_at": entry.created_at,
                "updated_at": entry.updated_at,
                "access_count": entry.access_count,
            }
        (self.data_dir / "facts.json").write_text(json.dumps(facts_data, indent=2))

        sops_data = {}
        for k, entry in self.sops.items():
            sops_data[k] = {
                "key": entry.key,
                "value": entry.value,
                "category": entry.category,
                "created_at": entry.created_at,
                "updated_at": entry.updated_at,
                "access_count": entry.access_count,
            }
        (self.data_dir / "sops.json").write_text(json.dumps(sops_data, indent=2))

    # --- L1: Working Memory ---

    def set_working(self, key: str, value: str):
        """Set a working memory entry (transient, current task)."""
        self.working[key] = value

    def get_working(self, key: str) -> Optional[str]:
        return self.working.get(key)

    def clear_working(self):
        self.working.clear()

    # --- L2: Facts ---

    def add_fact(self, key: str, value: str):
        """Add or update a persistent fact."""
        if key in self.facts:
            self.facts[key].value = value
            self.facts[key].updated_at = time.time()
        else:
            self.facts[key] = MemoryEntry(key=key, value=value, category="fact")
        self.save()

    def get_fact(self, key: str) -> Optional[str]:
        entry = self.facts.get(key)
        if entry:
            entry.access_count += 1
            return entry.value
        return None

    # --- L3: SOPs ---

    def add_sop(self, key: str, procedure: str):
        """Add or update a standard operating procedure."""
        if key in self.sops:
            self.sops[key].value = procedure
            self.sops[key].updated_at = time.time()
        else:
            self.sops[key] = MemoryEntry(key=key, value=procedure, category="sop")
        self.save()

    def get_sop(self, key: str) -> Optional[str]:
        entry = self.sops.get(key)
        if entry:
            entry.access_count += 1
            return entry.value
        return None

    # --- Conversation History ---

    def add_message(self, role: str, content: str, **extra):
        """Add a message to conversation history."""
        entry = {"role": role, "content": content, **extra}
        self.conversation_history.append(entry)
        if len(self.conversation_history) > self.max_history:
            self.conversation_history = self.conversation_history[-self.max_history:]

    def get_messages(self) -> list[dict]:
        """Get conversation history for LLM context."""
        return list(self.conversation_history)

    def get_context_prompt(self) -> str:
        """Build a context prompt from all memory layers."""
        parts = []

        if self.working:
            parts.append("=== WORKING MEMORY ===")
            for k, v in self.working.items():
                parts.append(f"  {k}: {v}")

        if self.facts:
            parts.append("=== KNOWN FACTS ===")
            for k, entry in list(self.facts.items())[:20]:
                parts.append(f"  {k}: {entry.value}")

        return "\n".join(parts) if parts else ""

    def clear_all(self):
        """Clear all memory."""
        self.working.clear()
        self.conversation_history.clear()
