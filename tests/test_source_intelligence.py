from dataclasses import dataclass

from viral_futbol.source_intelligence import assess_sources


@dataclass
class Story:
    publisher: str
    link: str


def family(name: str) -> str:
    return {"A Spor": "turkuvaz", "Fotomaç": "turkuvaz"}.get(name, name.casefold())


def test_syndicated_publishers_count_once():
    result = assess_sources([
        Story("A Spor", "https://aspor.com.tr/a"),
        Story("Fotomaç", "https://fotomac.com.tr/b"),
        Story("BBC", "https://bbc.com/c"),
    ], family)
    assert result.independent_sources == 2


def test_official_source_gets_quality_signal():
    result = assess_sources([
        Story("UEFA", "https://uefa.com/news/a"),
        Story("BBC", "https://bbc.com/b"),
    ], family)
    assert result.official_sources == 1
    assert result.score >= 65


def test_social_reposts_are_penalized():
    result = assess_sources([
        Story("Account A", "https://x.com/a/status/1"),
        Story("Account B", "https://instagram.com/p/2"),
    ], family)
    assert result.low_signal_sources == 2
    assert result.score == 20
