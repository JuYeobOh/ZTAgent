import pytest
import math
from collections import Counter
from employee_agent.sites.groupoffice import GroupOfficeHandler
from employee_agent.sites.dms import DMSHandler


def compute_entropy(items):
    from collections import Counter
    counts = Counter(items)
    total = len(items)
    return -sum((c/total) * math.log2(c/total) for c in counts.values())


class TestGroupOfficeActionMapper:
    def setup_method(self):
        self.handler = GroupOfficeHandler()

    def test_calendar_switch_view_diversity(self):
        goals = [self.handler.build_goal("calendar", "switch_view") for _ in range(30)]
        entropy = compute_entropy(goals)
        counts = Counter(goals)
        max_freq = max(counts.values()) / 30
        assert entropy >= math.log2(3), f"entropy={entropy:.3f} < log2(3)={math.log2(3):.3f}"
        assert max_freq < 0.70, f"max_freq={max_freq:.2%} >= 70%"

    def test_calendar_create_event_diversity(self):
        goals = [self.handler.build_goal("calendar", "create_event") for _ in range(30)]
        entropy = compute_entropy(goals)
        counts = Counter(goals)
        max_freq = max(counts.values()) / 30
        assert entropy >= math.log2(3)
        assert max_freq < 0.70

    def test_address_book_search_diversity(self):
        goals = [self.handler.build_goal("address_book", "search_contact") for _ in range(30)]
        entropy = compute_entropy(goals)
        assert entropy >= math.log2(3)

    def test_unknown_action_returns_fallback(self):
        goal = self.handler.build_goal("unknown_module", "unknown_action")
        assert "unknown_module" in goal or "unknown_action" in goal

    def test_use_vision_true_for_goui(self):
        assert self.handler.use_vision("switch_view") is True
        assert self.handler.use_vision("create_event") is True

    def test_system_prompt_not_empty(self):
        prompt = self.handler.system_prompt()
        assert len(prompt) > 50
        assert "Group-Office" in prompt or "GOUI" in prompt or "group.kmuinfosec" in prompt


class TestDMSActionMapper:
    def setup_method(self):
        self.handler = DMSHandler()

    def test_view_files_returns_goal(self):
        goal = self.handler.build_goal("files", "view_files")
        assert len(goal) > 10

    def test_upload_file_diversity(self):
        goals = [self.handler.build_goal("files", "upload_file") for _ in range(30)]
        entropy = compute_entropy(goals)
        assert entropy >= math.log2(3)

    def test_use_vision_false_for_dms(self):
        assert self.handler.use_vision("view_files") is False

    def test_system_prompt_not_empty(self):
        prompt = self.handler.system_prompt()
        assert len(prompt) > 50
