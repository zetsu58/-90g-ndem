from __future__ import annotations

import json
from bamloop.trends import TrendCandidate, content_brief, deduplicate


def main() -> None:
    samples = [
        TrendCandidate("Galatasaray transfer için resmi görüşmelere başladı", engagement=2400),
        TrendCandidate("Galatasaray transferde resmi görüşmelere başladı", engagement=1800),
        TrendCandidate("Şampiyonlar Ligi gecesinde son dakika golü", engagement=3200),
        TrendCandidate("Antrenmandan yeni görüntüler paylaşıldı", engagement=100),
    ]
    ranked = deduplicate(samples)
    payload = {
        "count": len(ranked),
        "queue": [content_brief(item) for item in ranked],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
