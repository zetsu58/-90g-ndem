from bamloop.learning import remember_story_scenes, learned_story_advice
from bamloop.story import LocalStoryProvider


def test_bamloop_story_uses_shared_scene_store(tmp_path):
    db=str(tmp_path/"bamloop.db")
    story=LocalStoryProvider().create("42")
    scenes=remember_story_scenes(db,"content-1",story)
    assert len(scenes) == 4
    assert scenes[0]["kind"] == "bamloop_story"
    assert scenes[0]["motion"] == story.scenes[0].movement
    assert learned_story_advice(db) is None
