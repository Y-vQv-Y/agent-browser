"""Tests for the memory system."""

import json
import tempfile
from pathlib import Path

import pytest

from agent_browser.core.memory import WorkingMemory, MemoryEntry


class TestMemoryEntry:
    def test_creation(self):
        entry = MemoryEntry(key="test", value="hello", category="fact")
        assert entry.key == "test"
        assert entry.value == "hello"
        assert entry.category == "fact"
        assert entry.access_count == 0

    def test_timestamps(self):
        entry = MemoryEntry(key="test", value="hello", category="fact")
        assert entry.created_at > 0
        assert entry.updated_at > 0


class TestWorkingMemory:
    @pytest.fixture
    def memory(self, tmp_path):
        return WorkingMemory(data_dir=tmp_path / "memory")

    def test_working_memory(self, memory):
        memory.set_working("key1", "value1")
        assert memory.get_working("key1") == "value1"
        assert memory.get_working("nonexistent") is None

    def test_clear_working(self, memory):
        memory.set_working("key1", "value1")
        memory.clear_working()
        assert memory.get_working("key1") is None

    def test_facts_persist(self, tmp_path):
        # Create and save
        mem1 = WorkingMemory(data_dir=tmp_path / "memory")
        mem1.add_fact("test_fact", "test_value")
        mem1.save()

        # Load and verify
        mem2 = WorkingMemory(data_dir=tmp_path / "memory")
        assert mem2.get_fact("test_fact") == "test_value"

    def test_fact_update(self, memory):
        memory.add_fact("key", "old_value")
        memory.add_fact("key", "new_value")
        assert memory.get_fact("key") == "new_value"

    def test_sops(self, memory):
        memory.add_sop("login_flow", "1. Navigate to login\n2. Enter credentials\n3. Click login")
        sop = memory.get_sop("login_flow")
        assert "Navigate to login" in sop

    def test_sops_persist(self, tmp_path):
        mem1 = WorkingMemory(data_dir=tmp_path / "memory")
        mem1.add_sop("proc1", "step1;step2")
        mem1.save()

        mem2 = WorkingMemory(data_dir=tmp_path / "memory")
        assert mem2.get_sop("proc1") == "step1;step2"

    def test_conversation_history(self, memory):
        memory.add_message("user", "Hello")
        memory.add_message("assistant", "Hi there!")
        messages = memory.get_messages()
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["content"] == "Hi there!"

    def test_history_max_limit(self, memory):
        memory.max_history = 5
        for i in range(10):
            memory.add_message("user", f"msg {i}")
        assert len(memory.get_messages()) == 5

    def test_context_prompt(self, memory):
        memory.set_working("current_task", "Test task")
        memory.add_fact("browser", "Chromium")

        context = memory.get_context_prompt()
        assert "current_task" in context
        assert "Test task" in context
        assert "browser" in context

    def test_clear_all(self, memory):
        memory.set_working("key", "val")
        memory.add_message("user", "test")
        memory.clear_all()
        assert memory.get_working("key") is None
        assert len(memory.get_messages()) == 0

    def test_access_count_increment(self, memory):
        memory.add_fact("key", "value")
        memory.get_fact("key")
        memory.get_fact("key")
        assert memory.facts["key"].access_count == 2
