# BAMLOOP — Original Micro-Meme Shorts

BAMLOOP produces original 6-second, sound-on, seamless-loop Shorts inspired by the retention mechanics of successful micro-meme channels without downloading or reposting their videos.

## Format

- 720x1280 H.264/AAC
- 6-second forward/reverse seamless loop
- immediate visual action; no intro
- large two-line punch caption
- copyright-safe generated audio bed
- portrait source clips from the Pexels API
- separate YouTube OAuth credentials so Viral Futbol is never mixed with this channel

## Run one safe preview

1. Copy `.env.bamloop.example` values into the service environment.
2. Keep `MEME_YOUTUBE_ENABLED=false` for previews.
3. Run:

```bash
python -m scripts.run_meme_worker
```

The MP4 is stored in `storage/bamloop`.

## Connect the BAMLOOP channel

Authorize the Google account that owns the new BAMLOOP YouTube channel with the `youtube.upload` scope, then set the three `MEME_YOUTUBE_*` OAuth values. Start with `MEME_YOUTUBE_PRIVACY_STATUS=private`; after visual review, change it to `public`.

## Safety rules

- Do not download or re-upload YouTube, TikTok, Instagram, broadcast, movie, or sports footage.
- Only use licensed API media, owned recordings, explicit creator submissions, or generated media.
- Keep attribution in internal metadata even when the license does not require visible credit.
- Do not publish more than 4–8 Shorts per day; repeated near-identical uploads can suppress distribution.


Production Render service: `Dockerfile.bamloop`, start `python -m bamloop.service`,
`/data` persistent disk and `MEME_DB_PATH=/data/bamloop/bamloop.sqlite3`.
The separate Viral Futbol service uses `Dockerfile`, start `python -m viral_futbol.web`,
`NEWS_DB_PATH=/data/viral_futbol.sqlite3`, `LITE_VIDEO_DIR=/data/viral-videos`
and its own `/data` persistent disk. Set the corresponding `*_YOUTUBE_ENABLED=true`
only after configuring each service's own OAuth client ID, secret and refresh token.
Set `*_YOUTUBE_PRIVACY_STATUS=public` deliberately when the appropriate channel
has been checked. Each service uses its own quota and never shares its database.
Use `python -m scripts.production_smoke` for offline video validation.
