# 90 Gündem — ViralFutbol Otomasyonu

Anlık Türkçe ve global futbol haberlerini tarar, en az iki bağımsız yayıncıyla doğrular, tekrarları engeller ve doğrulanmış haberleri MoneyPrinterTurbo'ya 9:16 YouTube Shorts görevleri olarak gönderir.

## Akış

1. Türkiye akışı Google News TR üzerinden Süper Lig ve Türkiye futbolunu tarar.
2. Global akış Google News US/English üzerinden dünya futbolu, transferler, Premier League, Champions League, Real Madrid ve Barcelona gündemini tarar.
3. Son 90 dakikadaki benzer başlıklar gruplanır.
4. En az iki bağımsız yayıncı şartı uygulanır.
5. Türkçe ve İngilizce sürümler dil bazında ayrı ayrı tekrar kontrolünden geçirilir.
6. Her pazar için birebir çeviri olmayan, özgün kanca ve editoryal açıklama içeren 30–40 saniyelik bir senaryo üretilir.
7. MoneyPrinterTurbo; dile özel ses, altyazı ve İngilizce materyal arama terimleriyle HD Shorts videosunu üretir.
8. Bir haber yalnızca görev kimliği alındığında değil, MoneyPrinterTurbo geçerli bir
   `final-*.mp4` döndürdüğünde tamamlanmış sayılır. Başarısız işler gecikmeli ve
   sınırlı sayıda yeniden denenir.

## Dayanıklı görev yaşam döngüsü

Görevler SQLite içinde `submitting → submitted → processing → complete/failed`
durumlarıyla izlenir. `/run` önce mevcut işleri MoneyPrinterTurbo'dan uzlaştırır,
sonra boş kapasite kadar yeni iş gönderir. Geçici Colab/ngrok kesintisi bir işi
başarısız saymaz; sonraki taramada tekrar sorgulanır. `/status` son tarama sonucunu
ve durum sayılarını döndürür.

MoneyPrinterTurbo anahtarı `x-api-key` başlığında gönderilir. Render üzerinde
`NEWS_DB_PATH=/data/viral_futbol.sqlite3` kullanılıyorsa `/data` kalıcı diske
bağlanmalıdır; aksi halde Render yeniden başlatıldığında haber geçmişi kaybolur.

Ücretsiz Render planında kalıcı disk yoksa güvenlik ağı yine çalışır: ViralFutbol
her haber için sabit bir `Idempotency-Key` gönderir ve MoneyPrinterTurbo bu anahtarı
Google Drive'daki dayanıklı görev kaydıyla eşler. Render yanıtı kaçırsa veya yerel
SQLite sıfırlansa bile aynı haber mevcut göreve bağlanır; ikinci video başlatılmaz.

## Dil profilleri

- `tr`: Türkiye kaynakları, `tr-TR-AhmetNeural-Male` ses ve Türkçe altyazı.
- `en`: İngilizce global kaynaklar, `en-US-GuyNeural-Male` ses ve İngilizce altyazı.
- Varsayılan `NEWS_LANGUAGES=tr,en` değeridir. Tek dil için `tr` veya `en` kullanılabilir.

İngilizce akış yalnızca Türkçe metni çevirmemelidir. Global izleyici için ayrı başlık, doğal İngilizce anlatım, farklı arama kelimeleri ve habere özgü değer üretmelidir. Bu, kanalın seri üretilmiş veya birbirinin kopyası içerik gibi görünme riskini azaltır.

## Hızlı ve kaliteli video profili

- Çıktı: otomasyon için hızlı ve net `720×1280`; istenirse `1080×1920`.
- Hedef süre: 30–40 saniye.
- Klip süresi: varsayılan 5 saniye; yaklaşık 6–9 klip.
- Kaynak eşleştirme: senaryo sırasına göre.
- Geçiş: klipler arasında dinamik `Shuffle` profili.
- Ses hızı: doğal kalacak şekilde `1.03x`.
- Müzik seviyesi: etkinleştirildiğinde `0.10`.

## Hızlı başlangıç

```bash
cp .env.example .env
# .env içindeki MPT_API_URL ve MPT_API_KEY değerlerini doldurun.
docker compose up -d --build
```

İlk kontrolde `NEWS_DRY_RUN=true` kullanın. Gerçek üretim için yalnızca uçtan uca kontrol tamamlandıktan sonra `false` yapın.

Dayanıklılık ve kapasite değişkenleri: `NEWS_MAX_INFLIGHT_TASKS`,
`NEWS_MAX_TASK_ATTEMPTS`, `NEWS_RETRY_DELAY_SECONDS`,
`NEWS_SUBMISSION_STALE_SECONDS`, `MPT_REQUEST_TIMEOUT`.

## Telifsiz müzik güvenlik kuralı

Arka plan müziği varsayılan olarak kapalıdır. MoneyPrinterTurbo'nun isimsiz hazır parçaları otomatik yayında kullanılmaz. YouTube Studio Ses Kitaplığı'ndan indirilen, **Atıf gerekmiyor** olarak işaretli dosyalar `storage/bgm` dizinine eklendikten ve kaynak/lisans kaydı saklandıktan sonra `NEWS_BGM_TYPE=random` yapılmalıdır.

## YouTube yayını

Türkçe ve İngilizce sürümler için ayrı kanal profili önerilir; böylece başlık, altyazı, ses ve görsel kurgu izleyiciye tamamen yerelleştirilebilir. YouTube çok dilli ses özelliği etkin olan kanallarda aynı Short'a ikinci ses parçası da eklenebilir, ancak bu özellik kanal erişimine bağlıdır.

MoneyPrinterTurbo tarafında Upload-Post veya doğrudan YouTube OAuth yayın sağlayıcısı yapılandırılmalıdır. İlk gerçek testte private/unlisted önerilir. API anahtarları, OAuth dosyaları ve tokenlar GitHub'a yüklenmemelidir.

## Para kazanma, telif ve doğruluk

Sistem maç yayını kliplerini çekmez. Pexels/izinli medya, özgün grafik veya lisanslı içerik kullanılmalıdır. Sistem yalnızca haber metnini okumamalı; doğrulanmış kaynaklardan özgün açıklama ve anlamlı kurgu üretmelidir. Otomatik kaynak eşleşmesi editoryal ve telif sorumluluğunu ortadan kaldırmaz.
