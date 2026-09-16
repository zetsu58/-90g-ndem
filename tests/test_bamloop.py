from bamloop.engine import IDEAS, MemeIdea, choose_idea


def test_ideas_fit_micro_meme_format():
    assert len(IDEAS) >= 6
    assert all(isinstance(idea, MemeIdea) for idea in IDEAS)
    assert all(len(idea.title) <= 90 for idea in IDEAS)
    assert all("\n" in idea.caption or len(idea.caption) <= 24 for idea in IDEAS)


def test_seeded_choice_is_deterministic():
    assert choose_idea("same") == choose_idea("same")
