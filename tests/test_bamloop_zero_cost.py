from __future__ import annotations

import pytest

from bamloop.story import LocalImageProvider, LocalStoryProvider, select_providers


def test_zero_cost_provider_is_default(monkeypatch):
    monkeypatch.setenv("BAMLOOP_DAILY_AI_BUDGET_USD", "0")
    monkeypatch.setenv("BAMLOOP_STORY_PROVIDER", "local")
    monkeypatch.setenv("BAMLOOP_IMAGE_PROVIDER", "local")
    monkeypatch.setenv("BAMLOOP_VIDEO_PROVIDER", "local")
    story, image, provider, cost, budget = select_providers(None)
    assert isinstance(story, LocalStoryProvider)
    assert isinstance(image, LocalImageProvider)
    assert provider == "zero-cost-local"
    assert cost == 0.0
    assert budget == 0.0


def test_paid_provider_cannot_run_with_zero_budget(monkeypatch):
    monkeypatch.setenv("BAMLOOP_DAILY_AI_BUDGET_USD", "0")
    monkeypatch.setenv("BAMLOOP_STORY_PROVIDER", "runway")
    monkeypatch.setenv("BAMLOOP_IMAGE_PROVIDER", "local")
    monkeypatch.setenv("BAMLOOP_VIDEO_PROVIDER", "local")
    # With no budget, selection must fall back locally and never initiate a paid call.
    story, image, provider, cost, budget = select_providers(None)
    assert provider == "zero-cost-local"
    assert cost == 0.0
    assert budget == 0.0


def test_story_continuity_is_stable():
    story = LocalStoryProvider().create("continuity-seed")
    assert len(story.scenes) == 4
    assert len({scene.subject for scene in story.scenes}) == 1
    assert len({scene.continuity_context for scene in story.scenes}) == 1
    assert all("logo yok" in scene.negative_constraints for scene in story.scenes)
