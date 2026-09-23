from bamloop.performance import collect


def test_bamloop_performance_is_disabled_without_credentials(tmp_path, monkeypatch):
    for key in ("MEME_YOUTUBE_CLIENT_ID","MEME_YOUTUBE_CLIENT_SECRET","MEME_YOUTUBE_REFRESH_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    assert collect(str(tmp_path/"bamloop.db")) == {"ready":False,"collected":0}
