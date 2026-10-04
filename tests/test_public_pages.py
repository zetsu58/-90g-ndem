from production.public_pages import public_page


def test_public_pages_have_brand_and_navigation():
    for service, host, name in (
        ("viral_futbol", "viralfutbol.onrender.com", "Viral Futbol"),
        ("bamloop", "bamloop.onrender.com", "BAMLOOP"),
    ):
        for route in ("/about", "/privacy", "/terms"):
            page = public_page(service, route).decode("utf-8")
            assert name in page
            assert f"https://{host}/privacy" in page
            assert f"https://{host}/terms" in page
            assert "zambakste@gmail.com" in page or route == "/about"
            assert "refresh_token" not in page


def test_unknown_page_is_not_served():
    assert public_page("viral_futbol", "/status") is None
    assert public_page("unknown", "/privacy") is None
