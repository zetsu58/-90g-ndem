from production.growth_engine import decide, hook_score, packaging_warnings, similarity, topic_score

def test_growth_is_deterministic_and_profile_isolated():
    a=decide("Galatasaray transfer görüşmelerinde yeni gelişme",profile="viral_futbol",source_count=2)
    b=decide("Galatasaray transfer görüşmelerinde yeni gelişme",profile="viral_futbol",source_count=2)
    c=decide("Galatasaray transfer görüşmelerinde yeni gelişme",profile="bamloop",source_count=2)
    assert a==b
    assert a.fingerprint!=c.fingerprint
    assert 0<=a.hook_score<=1 and 0<=a.topic_score<=1

def test_missing_outlier_is_neutral_not_fabricated():
    neutral=topic_score(outlier_multiple=None)
    low=topic_score(outlier_multiple=0)
    assert neutral>low

def test_duplicate_similarity_reduces_topic_score():
    fresh=decide("Fenerbahçe yeni transfer açıkladı",profile="viral_futbol",recent_titles=[])
    duplicate=decide("Fenerbahçe yeni transfer açıkladı",profile="viral_futbol",
                     recent_titles=["Fenerbahçe yeni transfer açıkladı"])
    assert duplicate.topic_score<fresh.topic_score

def test_hook_and_packaging_lint():
    assert hook_score("Son dakika: Galatasaray 2 oyuncuyla görüşüyor")>0
    assert similarity("Galatasaray transfer haberi","Galatasaray transfer haberi")==1
    assert "title_too_vague" in packaging_warnings("Şok!")
    assert "title_opening_duplicate" in packaging_warnings("Galatasaray transfer haberi","Galatasaray transfer haberi")
