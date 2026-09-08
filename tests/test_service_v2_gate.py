from viral_futbol.trend_score import TrendSignals, score_trend


def test_produce_threshold_is_75():
    result = score_trend(
        TrendSignals(
            source_count=2,
            official_source=True,
            transfer=True,
            breaking=True,
            major_team_or_player=True,
        )
    )
    assert result.score >= 75
    assert result.decision == "produce"


def test_hold_band():
    result = score_trend(
        TrendSignals(source_count=2, transfer=True, breaking=True, major_team_or_player=True)
    )
    assert 55 <= result.score < 75
    assert result.decision == "hold"


def test_ignore_band():
    result = score_trend(TrendSignals(source_count=2))
    assert result.score < 55
    assert result.decision == "ignore"
