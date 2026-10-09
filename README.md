# 90+ Gündem — ViralFutbol + BAMLOOP

## Tek kanal / yalnız Shorts — 5 Ekim 2026

Production profili `UNIFIED_YOUTUBE_CHANNEL=true` ve `SHORTS_ONLY_MODE=true` kullanır.
ViralFutbol servisi futbol ve BAMLOOP üreticilerini aynı cycle lock altında sırayla
çalıştırır. İkisi de `YOUTUBE_*` yetkisini ve `YOUTUBE_EXPECTED_CHANNEL_ID` kanalını
kullanır; BAMLOOP'un eski `MEME_YOUTUBE_*` yetkisine geri dönüş yapılmaz.
Yerel kuyruk aynı `NEWS_DB_PATH` veritabanını, ledger günlük slotları aynı
`viral_futbol` kanalını paylaşır. Kaynakların item kayıtları tekrar koruması için
korunur. `PUBLISH_LIMITS_PER_SOURCE=true` ile ViralFutbol günde 5, BAMLOOP
günde 5 Shorts paylaşabilir: toplam üst sınır 10'dur. En az 3 saat aralık her
kaynak için ayrı uygulanır; aynı turda iki kaynağın birer Short'u yayınlanabilir.
BAMLOOP üretim aralığı `MEME_INTERVAL_SECONDS=10800` kullanır. Kota üst sınırdır;
haber bulunması, kalite kontrolü ve OAuth başarısı gerçek yayın sayısını belirler.

BAMLOOP production içerik modu `reaction_meme` kullanır: Türkçe durum yazısı,
görüntüde gerçekten gerçekleşen komik olay, tepki yakın planı, özgün ses efekti
ve kısa tekrar. Rastgele Pexels aramasının ilk sonucu ve ileri–geri döngü bu
modda kullanılmaz; AI hikâyeye otomatik geçiş yapılmaz. İncelenmiş olay zamanları,
kaynak SHA-256 ve lisans/atıf `bamloop/meme_clips.json` içinde kayıtlıdır.
Yeni klip eklenmeden önce olayın tamamı görsel olarak incelenmelidir; eski
stok/story kuyruk işleri dosyaları silinmeden `quality_blocked` durumuna alınır.
Kaynak içeriği değişirse yeniden inceleme yapılmadan render edilmez.
Free Render çıktısı 720×1280, 30 fps; decoder/encoder tek thread çalışır ve
reverse kare tamponu kullanılmaz. Lisans ve uyarlama bilgisi YouTube açıklamasındadır.
İncelenmiş gerçek meme klipleri yayınlanır. Çizim tabanlı araç simülasyonu
prototipi kanalın görsel beklentisini karşılamadığı için production'da
`BAMLOOP_SIMULATION_ENABLED=false` olarak kapalıdır. Herhangi bir yeni üretim
formatı, örnek video kalite incelemesinden sonra ayrıca etkinleştirilmelidir.
Katalog biterse `reviewed_meme_catalog_exhausted` ile beklenir.

Uzun video üretimi, force-pair komutu ve upload kapısı Shorts politikası tarafından
engellenir. Kuyruktaki eski uzun videolar dosyaları silinmeden `format_disabled`
durumuna alınır. Ayrı BAMLOOP servisi `BAMLOOP_STANDALONE_ENABLED=false` ile
standby çalışır. Eski BAMLOOP kuyruğu otomatik olarak yeni kanala taşınmaz.

Mevcut Render servislerinde ortam değişkenleri Docker varsayılanlarını geçersiz
kılabilir. Canlı ayarlarda birleşik mod/Shorts bayrakları, `YOUTUBE_ENABLED=true`,
`YOUTUBE_PRIVACY_STATUS=public`, iki longform bayrağı `false` ve ayrı BAMLOOP
worker bayrağı `false` uygulanmalı, iki servis de aynı commit'e deploy edilmelidir.
Gerçek PUBLIC yayın ancak OAuth/kanal ön kontrolü ve normal production upload
sonrası doğrulanabilir; aşağıdaki tarihli eski durum kayıtları canlı başarı kanıtı değildir.

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


## Multi-format long-form motoru

ViralFutbol ve BAMLOOP ortak `production/` çekirdeği üzerinden iki format çalıştırabilir:

- `short`: 9:16, 12–70 saniye.
- `video`: 16:9, 150–300 saniye; varsayılan hedef 210 saniye.

Long-form üretim zinciri:

```text
cadence + publish-slot gate
  -> konu rotasyonu / cooldown
  -> Wikidata + Google News evidence
  -> fact manifest (minimum kanıt + kaynak doğrulaması)
  -> grounded narration (opsiyonel OpenAI-compatible LLM, güvenli fallback)
  -> 8–15 zamanlanmış sahne
  -> Wikimedia Commons görseli / doğrulanmış editoryal fallback kartı
  -> Edge TTS / espeak-ng fallback
  -> Remotion timed-scene render / low-memory FFmpeg fallback
  -> 16:9 H.264/AAC quality gate
  -> format-aware publish queue
  -> OAuth + expected-channel preflight
  -> resumable YouTube upload
  -> public verification + analytics
```

Long-form render yalnız video yayın slotu hazır olduğunda başlatılır. Shorts ve normal videoların günlük limitleri ve minimum yayın aralıkları birbirinden bağımsızdır; bir formatın dolu kotası diğer formatı bloke etmez.

Temel environment ayarları:

```env
VIRAL_LONGFORM_ENABLED=false
BAMLOOP_LONGFORM_ENABLED=false
VIRAL_LONGFORM_INTERVAL_HOURS=24
BAMLOOP_LONGFORM_INTERVAL_HOURS=24
MAX_VIDEOS_PER_DAY=1
MIN_HOURS_BETWEEN_VIDEOS=12
LONGFORM_MIN_EVIDENCE=10
LONGFORM_RENDER_ONLY_WHEN_SLOT_READY=true
LONGFORM_MUSIC_ENABLED=true
LONGFORM_TTS_RATE=+5%
REMOTION_LONGFORM_TIMEOUT_SECONDS=900
```

Opsiyonel OpenAI-compatible script endpoint:

```env
LONGFORM_LLM_BASE_URL=
LONGFORM_LLM_MODEL=
LONGFORM_LLM_API_KEY=
```

Bu değerler yoksa long-form sistemi doğrulanmış olgulardan deterministic grounded fallback narration üretir; LLM bağlantısının olmaması worker'ı durdurmaz. Feature flag varsayılan olarak kapalıdır; ilk production smoke/QC sonrası kanal bazında açılmalıdır.

