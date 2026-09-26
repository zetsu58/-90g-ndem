# Production hardening checkpoint

CURRENT PHASE: PR review and post-deploy verification.

COMPLETED:
- Inspected GitHub main at tree `3c54098a2e0d110926d4f82e5cf7f9dd3c24b45d` and mirrored text source into an isolated local validation workspace.
- Confirmed live worker reaches and completes render. At 2026-09-26 11:18 UTC its latest finished cycle reported one rendered/queued story but `youtube.quality_blocked=1`.
- Found default 1080x1920 publish gate incompatible with intentional 720x1280 production FFmpeg output.
- Changed quality-gate defaults and Render blueprint/example to 720x1280.
- Final renders now use a `.pending.mp4` and ffprobe quality validation before atomic publication; corrupt cached MP4s are discarded.
- Edge TTS await is capped at 45 seconds.
- Fixed fresh SQLite analytics readers that queried tables before initialization.
- BAMLOOP Render blueprint now keeps Remotion disabled, avoiding an unnecessary 360-second render attempt.
- Both YouTube upload transports use bounded HTTP sockets and a 300-second overall upload deadline.
- BAMLOOP source downloads have a 100 MiB cap; meme/story renders validate before atomic final-file replacement.

COMMITS:
- Local baseline snapshot `4cce135` is an isolated mirror, **not** a GitHub production commit.
- Local logical commits `c4abff4` (render/publish gate) and `c4412df` (schema/Remotion). These are not yet GitHub commits.
- GitHub branch `codex/production-render-hardening-20260926` has commits `ee39801` (render/publish gate), `151df65` (schema/Remotion/tests), `d7f406f` (BAMLOOP media safety).

TESTS:
- `python -m compileall -q viral_futbol bamloop production scripts`: passed before changes.
- Targeted pytest: 7 passed after the quality-gate/render changes.
- Credential-free production smoke passed: Viral Futbol 720x1280 / 27.39s, BAMLOOP meme 1080x1920 / 12s, BAMLOOP AI story 1080x1920 / 36s; all H.264/AAC.
- Full pytest initially: 91 passed, 2 failed (missing analytics tables); both failures fixed and focused tests passed (3/3). Full rerun in progress.
- Render timeout cleanup and disabled Remotion tests passed.
- Final full pytest: **95 passed**. Final smoke rerun: all three outputs passed ffprobe at the dimensions/codecs above.
- Dockerfiles inspected; local Docker build unavailable because the Docker CLI is not installed here.

OPEN ISSUE:
- Open PR and merge only after review; Render deployment has not yet been performed.
- BAMLOOP live status was reachable but reported an in-progress production cycle; no real YouTube ID was observed in this run.
- Render Free SQLite remains ephemeral; GitHub ledger is the durable duplicate guard.

NEXT EXACT ACTION:
Open a PR from `codex/production-render-hardening-20260926` to `main`; after merge/deploy, check `youtube.quality_blocked=0`, successful `last_finished_at`, and a real YouTube video ID before claiming live publishing.
