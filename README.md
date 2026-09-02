# 90 Gündem — ViralFutbol Otomasyonu

Anlık Türk futbol haberlerini tarar, en az iki bağımsız yayıncıyla doğrular, tekrarları engeller ve doğrulanmış haberi MoneyPrinterTurbo'ya 9:16 YouTube Shorts görevi olarak gönderir.

## Akış

1. Google News RSS sorguları taranır.
2. Son 90 dakikadaki benzer başlıklar gruplanır.
3. En az iki bağımsız kaynak şartı uygulanır.
4. Daha önce işlenen haberler SQLite ile elenir.
5. Türkçe, 30–45 saniyelik Shorts görevi MoneyPrinterTurbo API'sine gönderilir.
6. MoneyPrinterTurbo tamamlanan videoyu YouTube'a yükler.

## Hızlı başlangıç

```bash
cp .env.example .env
# .env içindeki MPT_API_URL ve MPT_API_KEY değerlerini doldurun.
docker compose up -d --build
```

İlk kontrolde `NEWS_DRY_RUN=true` kullanın. Gerçek üretim için `false` yapın.

## YouTube yayını

MoneyPrinterTurbo tarafında Upload-Post veya doğrudan YouTube yayın sağlayıcısı yapılandırılmalıdır. İlk gerçek testte private/unlisted önerilir; proje ayarı public yapılabilir. API anahtarları, OAuth dosyaları ve tokenlar GitHub'a yüklenmemelidir.

## Telif ve doğruluk

Sistem maç yayını kliplerini çekmez. Pexels/izinli medya, özgün grafik veya lisanslı içerik kullanılmalıdır. Kaynak eşleşmesi otomatik hata riskini azaltır ancak editoryal ve telif sorumluluğunu ortadan kaldırmaz.
