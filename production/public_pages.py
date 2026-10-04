"""Public information pages for the two OAuth-backed publishing services.

These pages intentionally contain no runtime configuration or credentials.
"""

from __future__ import annotations

from html import escape


_BRANDS = {
    "viral_futbol": (
        "Viral Futbol / 90+ Gündem",
        "https://viralfutbol.onrender.com",
        "Güncel futbol haberlerinden kısa ve uzun videolar hazırlayan otomatik yayın aracı.",
    ),
    "bamloop": (
        "BAMLOOP",
        "https://bamloop.onrender.com",
        "Özgün kısa ve uzun eğlence videoları hazırlayan otomatik yayın aracı.",
    ),
}

_CONTACT = "zambakste@gmail.com"


def public_page(service: str, path: str) -> bytes | None:
    """Return an HTML page for a known brand and route, or None."""
    if service not in _BRANDS or path not in {"/about", "/privacy", "/terms"}:
        return None
    name, base, description = _BRANDS[service]
    safe_name, safe_description = escape(name), escape(description)
    navigation = (
        f'<nav><a href="{base}/about">Ana sayfa</a> · '
        f'<a href="{base}/privacy">Gizlilik politikası</a> · '
        f'<a href="{base}/terms">Kullanım şartları</a></nav>'
    )
    if path == "/about":
        title = "Ana sayfa"
        content = (
            f"<p>{safe_description}</p>"
            "<p>Hizmet, kaynaklardan içerik keşfeder, metin ve görsel sahneler oluşturur, "
            "seslendirir, videoyu üretip teknik denetimden geçirir ve yetkilendirilmiş "
            "YouTube kanalına yayınlar. Yalnız kanal sahibi tarafından kullanılır.</p>"
            "<p>Google hesabı erişimi yalnız kanal kimliğini doğrulamak ve YouTube'a "
            "video yüklemek için istenir. Veri işleme ayrıntıları "
            f'<a href="{base}/privacy">gizlilik politikasındadır</a>.</p>'
        )
    elif path == "/privacy":
        title = "Gizlilik politikası"
        content = (
            "<p>Bu araç kanal sahibinin verdiği OAuth izniyle YouTube kanalının kimliğini "
            "(kanal ID'si ve adı) okur ve üretilen videoları kanala yükler. "
            "Kanal dışındaki Google verilerine erişim amacı yoktur.</p>"
            "<p>OAuth yenileme anahtarı ve istemci bilgileri Render ortam değişkenlerinde tutulur; "
            "halka açık durum yanıtlarında gösterilmez. Yayınlanan videonun ID'si ve "
            "yayın metaverisi, tekrar yüklemeyi önlemek ve yayın sıklığını korumak için "
            "yerel kuyrukta ve GitHub yayın kayıtlarında saklanabilir. Geçici medya dosyaları "
            "Render çalışma alanında işlenir. Google verileri reklam hedeflemesi için satılmaz.</p>"
            "<p>İzin, Google hesabının üçüncü taraf bağlantıları bölümünden kaldırılabilir. "
            "Bu durumda yeni yükleme yapılamaz. Veri erişimi veya silme talebi için "
            f'<a href="mailto:{_CONTACT}">{_CONTACT}</a> adresine yazın.</p>'
        )
    else:
        title = "Kullanım şartları"
        content = (
            "<p>Bu araç yalnız yetkilendirilmiş kanal sahibi için içerik üretimi ve "
            "YouTube yayını yapar. Üçüncü kişilere açık üyelik veya kullanıcı hesabı sunmaz.</p>"
            "<p>Haber ve medya kaynaklarının doğruluğu, kullanım hakları ve YouTube yayın "
            "kurallarına uygunluk kanal sahibinin sorumluluğundadır. Üretim, ağ, platform "
            "veya yetkilendirme hataları nedeniyle yayın gecikebilir ya da gerçekleşmeyebilir.</p>"
            f'<p>İletişim: <a href="mailto:{_CONTACT}">{_CONTACT}</a>.</p>'
        )
    return (
        "<!doctype html><html lang=\"tr\"><head><meta charset=\"utf-8\">"
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{escape(title)} — {safe_name}</title>"
        "<style>body{font:17px/1.6 system-ui,sans-serif;max-width:720px;"
        "margin:2rem auto;padding:0 1rem;color:#17212f}a{color:#075aa8}"
        "nav{margin:1.5rem 0}h1{line-height:1.2}</style></head><body>"
        f"<header><strong>{safe_name}</strong></header>{navigation}"
        f"<main><h1>{escape(title)}</h1>{content}</main>"
        f"<footer>{navigation}</footer></body></html>"
    ).encode("utf-8")
