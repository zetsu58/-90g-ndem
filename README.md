# 90+ Gündem — ViralFutbol + BAMLOOP

Otomatik kısa video üretim ve yayın altyapısı. Repository iki bağımsız production hattı içerir:

- **ViralFutbol:** güncel futbol haberlerini keşfeder, puanlar, kısa senaryo/sahne planı oluşturur, FFmpeg ile 9:16 video üretir ve YouTube yayın kuyruğuna alır.
- **BAMLOOP:** ViralFutbol'dan bağımsız çalışan kısa/meme/story video worker'ıdır; kendi queue, render ve YouTube yayın akışına sahiptir.

> **Production ilkesi:** gerçek kanallara fixture/test video yüklenmez. YouTube'a yalnız normal production pipeline tarafından seçilen ve kalite kontrolünden geçen içerik gönderilir.

## Güncel durum — 26 Eylül 2026

### ViralFutbol

- Render Web Service: `https://viralfutbol.onrender.com`
- Status: `/status`
- Production renderer: **FFmpeg lite**
- Remotion production'da kapalıdır.
- YouTube yayını etkin ve hedef gizlilik durumu `public`.
- Direct publish ve GitHub publish ledger etkindir.
- Worker servis açıldığında otomatik başlar.
- Son doğrulanan production akışında 720×1280 H.264/AAC video başarıyla render edilip queue'ya alınmıştır.
- Yayıncı `ledger_capacity` durumunda videoyu silmez; uygun yayın slotuna erteler.
- Free Render dosya sistemi kalıcı değildir; status çıktısındaki `db_persistent_path=false` buna dikkat edilmesi gerektiğini gösterir.

### BAMLOOP

- Render Web Service: `https://bamloop.onrender.com`
- Health: `/health`
- Runtime: Docker / `Dockerfile.bamloop`
- Start command: `python -m bamloop.service`
- YouTube production config: etkin
- YouTube privacy: `public`
- Direct publish + GitHub ledger: etkin
- Minimum yayın aralığı: **3 saat**
- Günlük üst sınır: **5 Short**
- Render health endpoint'i production'da `{"status":"ok"}` döndürmektedir.
- **Bilinen sorun:** 26 Eylül 2026 itibarıyla canlı BAMLOOP `/status` endpoint'i bazı deploylarda `{"error":"not_found"}` döndürmektedir. Repository'deki `bamloop/service.py` içinde `/status` ve `/api/status` route'ları bulunmaktadır; canlı container/import çözümlemesi ayrıca doğrulanmalıdır.

Son BAMLOOP status teşhis commit'i:
`eeebfa955cc69bce29ca8f71fb6d4b1f39cc2e4f`

## Production mimarisi

```text
                 ┌──────────────────────────┐
                 │      Content Sources     │
                 └────────────┬─────────────┘
                              │
                  discovery / trend scoring
                              │
               ┌──────────────▼──────────────┐
               │        ViralFutbol          │
               │ news → script → scenes      │
               └──────────────┬──────────────┘
                              │
                         FFmpeg render
                              │
                     ffprobe validation
                              │
                         Publish Queue
                              │
                     GitHub Publish Ledger
                              │
                       YouTube PUBLIC

               ┌─────────────────────────────┐
               │          BAMLOOP            │
               │ idea/story → media → render │
               └──────────────┬──────────────┘
                              │
                         Publish Queue
                              │
                     GitHub Publish Ledger
                              │
                       YouTube PUBLIC
```

ViralFutbol ve BAMLOOP aynı repository'de bulunur ancak worker ve yayın akışları birbirinden bağımsızdır. Bir hattın render/API hatası diğer hattın worker'ını durdurmamalıdır.

## ViralFutbol akışı

1. Güncel futbol içerikleri taranır.
2. Yaş, kaynak, tekrar ve trend/viral sinyalleri değerlendirilir.
3. Üretime alınacak haber seçilir.
4. Shorts senaryosu ve sahne manifesti oluşturulur.
5. Görsel/medya materyalleri hazırlanır.
6. TTS seslendirme oluşturulur.
7. FFmpeg ile dikey video render edilir.
8. Çıktı ffprobe ile teknik olarak doğrulanır.
9. Video publish queue'ya yazılır.
10. GitHub ledger duplicate ve yayın kapasitesini kontrol eder.
11. Slot uygunsa YouTube upload yapılır.
12. Başarılı upload sonrası gerçek YouTube video ID'si ledger/queue durumuna işlenir.

## BAMLOOP akışı

BAMLOOP servisi `bamloop.service` ile başlar. Worker startup delay sonrasında production cycle'ı çalıştırır. Yeni içerik üretimleri arasındaki süre `MEME_INTERVAL_SECONDS` ile yönetilir. Render aralarında publish queue ayrıca kontrol edilerek tamamlanmış videoların yayın slotu geldiğinde gönderilebilmesi hedeflenir.

Temel endpointler:

```text
GET /health
GET /healthz
GET /ready
GET /status
GET /api/status
```

`/health` yalnız prosesin HTTP yanıtı verebildiğini gösterir. YouTube production readiness için credentials, durable publishing koşulları ve ledger ayrıca kontrol edilmelidir.

## Yayın politikası

İki production hattında yayın güvenliği temel olarak queue + GitHub ledger ile sağlanır.

BAMLOOP varsayılanları:

```env
PUBLISH_DIRECT_ENABLED=true
PUBLISH_LEDGER_REQUIRED=true
PUBLISH_QUEUE_ENABLED=true
SMART_PUBLISH_SCHEDULING=true

MEME_YOUTUBE_ENABLED=true
MEME_YOUTUBE_PRIVACY_STATUS=public

MAX_SHORTS_PER_DAY=5
MIN_HOURS_BETWEEN_SHORTS=3
CHANNEL_TIMEZONE=Europe/Istanbul
```

`LedgerCapacity` bir upload hatası değildir. Günlük kapasite veya minimum yayın aralığı doluysa queue item uygun `next_publish_slot` zamanına ertelenmelidir.

Unresolved ledger reservation kayıtları körlemesine silinmemelidir. Bir önceki YouTube isteği başarılı olmuş fakat ledger güncellemesi yarıda kalmış olabilir; bu nedenle reconciliation yapılmadan reservation temizlemek duplicate public upload riski oluşturur.

## Video profili

Production'da öncelik düşük bellek tüketimi ve güvenilir FFmpeg render'ıdır.

ViralFutbol için doğrulanan profil:

- Dikey 9:16
- 720×1280
- H.264 video
- AAC audio
- FFmpeg lite renderer
- ffprobe kalite doğrulaması

Render tamamlanmadan final dosyayı hazır kabul etmeyin. Geçici/yarım çıktıların publish queue'ya girmemesi gerekir.

## Render deployment

### ViralFutbol

ViralFutbol kendi Render Web Service'i üzerinden çalışır. Production durumunu:

```text
GET https://viralfutbol.onrender.com/status
```

ile kontrol edin.

Önemli status alanları:

```text
running
cycle_stage
render_count
upload_count
failure_count
queue_size
next_publish_slot
last_upload_state
last_upload_error_type
last_uploaded_video_id
youtube_enabled
youtube_credentials_ready
youtube_privacy_status
github_ledger_ready
deploy_commit
```

### BAMLOOP

Render yapılandırması `render.bamloop.yaml` içindedir.

```text
Repository: zetsu58/-90g-ndem
Branch: main
Root Directory: (empty)
Dockerfile: ./Dockerfile.bamloop
Build Context: .
Start: python -m bamloop.service
Health Check: /health
```

BAMLOOP servisinin canlı olması yalnız `/health` ile doğrulanmamalıdır. Production yayın için status/readiness ve gerçek queue/ledger durumu da kontrol edilmelidir.

## Render Free instance davranışı

Free Web Service inactivity nedeniyle spin down olabilir. Proses uyurken kendi worker'ı çalışamaz. Servis tekrar HTTP trafiğiyle ayağa kalktığında startup worker yeniden başlamalı ve mevcut queue/ledger durumunu güvenli biçimde değerlendirmelidir.

Bu nedenle pipeline restart-safe ve idempotent tasarlanmalıdır.

## Persistence ve idempotency

Yerel SQLite queue kullanılırken Render'ın ephemeral filesystem davranışı dikkate alınmalıdır. GitHub publish ledger servis restartları arasında duplicate korumasının durable katmanıdır.

Production ilkeleri:

- upload öncesi reservation,
- başarılı upload sonrası `published`,
- gerçek `youtube_video_id` kaydı,
- duplicate reservation engeli,
- minimum yayın aralığı,
- günlük yayın limiti.

Yerel queue kaybı ihtimali nedeniyle durable ledger kayıtları manuel olarak değiştirilmemelidir.

## YouTube OAuth

Credential değerleri repository'ye commit edilmez.

ViralFutbol ve BAMLOOP için gerekli OAuth/environment değerleri Render secret env olarak tutulmalıdır. BAMLOOP tarafında:

```text
MEME_YOUTUBE_CLIENT_ID
MEME_YOUTUBE_CLIENT_SECRET
MEME_YOUTUBE_REFRESH_TOKEN
```

Status/log çıktılarında credential değerleri gösterilmemeli; yalnız configured/ready bilgisi raporlanmalıdır.

YouTube API hataları secret veya response body sızdırmadan sınıflandırılmalıdır.

## BAMLOOP environment özeti

`render.bamloop.yaml` içindeki temel production ayarları:

```env
REMOTION_ENABLED=false
REMOTION_SMOKE_ON_START=false
MEME_OUTPUT_DIR=storage/bamloop
MEME_INTERVAL_SECONDS=14400
MEME_STARTUP_DELAY_SECONDS=20
MEME_DB_PATH=storage/bamloop/bamloop.sqlite3

PUBLISH_DIRECT_ENABLED=true
PUBLISH_LEDGER_REQUIRED=true
PUBLISH_QUEUE_ENABLED=true
SMART_PUBLISH_SCHEDULING=true

MAX_SHORTS_PER_DAY=5
MIN_HOURS_BETWEEN_SHORTS=3
CHANNEL_TIMEZONE=Europe/Istanbul

MEME_YOUTUBE_ENABLED=true
MEME_YOUTUBE_PRIVACY_STATUS=public
```

## Lokal geliştirme

Python gereksinimi:

```text
Python >= 3.11
```

Kurulum:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

Test:

```bash
pytest -q
```

BAMLOOP servisini lokal çalıştırmak için:

```bash
python -m bamloop.service
```

Gerçek YouTube credential'ları bulunan ortamda test suite çalıştırırken fixture/test içeriklerin production kanalına gönderilmediğinden emin olun.

## Repository yapısı

```text
viral_futbol/       ViralFutbol discovery, render ve publisher
bamloop/            BAMLOOP worker, pipeline ve YouTube entegrasyonu
production/         ortak publish queue / GitHub ledger altyapısı
scripts/            operasyon ve yardımcı scriptler
assets/             uygulama varlıkları
remotion/           alternatif render altyapısı; production'da kapalı
Dockerfile.bamloop  BAMLOOP production image
render.bamloop.yaml BAMLOOP Render blueprint
pyproject.toml      Python package/dependency tanımı
```

## Production tamamlanma kriteri

Bir servis yalnız Render'da **Live** göründüğü için tamamlanmış sayılmaz.

Gerçek production doğrulaması için:

1. Worker başarılı cycle çalıştırmalı.
2. Gerçek içerik seçilmeli.
3. Video başarıyla render edilmeli.
4. Teknik kalite kontrolü geçmeli.
5. Queue item oluşmalı.
6. Ledger reservation başarılı olmalı veya doğru slota defer edilmeli.
7. YouTube upload gerçekten tamamlanmalı.
8. Gerçek YouTube video ID'si alınmalı.
9. Ledger ve queue `published` durumuna geçmeli.
10. Video privacy durumu `public` olmalı.

Bu kriterler sağlanmadan yalnız health/deploy başarısı production yayın başarısı olarak değerlendirilmez.

## Güvenlik

- OAuth token/client secret/API key commit etmeyin.
- Token veya YouTube API response body'lerini loglamayın.
- Fixture/test videolarını production kanalına göndermeyin.
- Ledger kayıtlarını reconciliation yapmadan silmeyin.
- Telif hakkı belirsiz maç yayını kliplerini otomatik olarak kullanmayın.
