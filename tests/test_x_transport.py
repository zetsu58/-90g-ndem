from pathlib import Path

from viral_futbol.news_card import build_news_card_svg
from viral_futbol.publishers.x_transport import XApiTransport


def test_x_transport_requires_runtime_token(monkeypatch):
    monkeypatch.delenv("X_ACCESS_TOKEN", raising=False)
    transport = XApiTransport()
    result = transport._request if False else None
    assert transport.token == ""


def test_news_card_svg_is_generated(tmp_path):
    output = tmp_path / "card.svg"
    result = build_news_card_svg("Galatasaray transfer görüşmelerine başladı", str(output))
    assert result == str(output)
    text = Path(output).read_text(encoding="utf-8")
    assert "VIRAL FUTBOL" in text
    assert "SON DAKİKA" in text
    assert "Galatasaray" in text
