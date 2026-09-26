# Production hardening checkpoint

CURRENT PHASE: Live publication diagnosis after PR #122 and #123 merged.

LIVE DEPLOY COMMIT: Not verified. GitHub main includes merge commits 510ee7c and 92b2d4d; the live /status endpoint did not yet expose a deploy SHA.

REAL YOUTUBE VIDEO ID: None observed for a new production upload.

LIVE STATUS (2026-09-26 11:50 UTC): /status HTTP 200; last_finished_at 2026-09-26T11:50:27Z; cycle_stage done; last_error null; shorts video validated 720x1280 H.264/AAC; YouTube published=0, failed=0, quality_blocked=0, skipped=1; upload_count=0; queue_size=5. GitHub publish-ledger has two reserved viral_futbol item records on 2026-09-26 with no video ID. Latest publicly visible channel Short was about five days old. Do not release these reservations without reconciling YouTube: an interrupted upload may have succeeded.

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
- The next publisher attempt is constrained by the channel's 3-hour spacing from its latest GitHub reservation at 2026-09-26 11:36:08 UTC. That reservation lacks a video ID; its upload outcome cannot safely be inferred from status alone.
- Render dashboard/log access requires an authenticated session, unavailable in this runtime. Diagnose prior upload failure from Render logs or the new safe status failure reason when a future attempt occurs. Do not bypass the ledger or publish fixture content.
- Render Free SQLite remains ephemeral; GitHub ledger is the durable duplicate guard. The public status has no immutable deployed SHA until the merged diagnostics code rolls out and Render supplies RENDER_GIT_COMMIT.

NEXT EXACT ACTION:
Finish merging the safe YouTube HTTP failure classification commit; verify the live /status exposes deploy_commit, configuration.shorts_min_width=720 and youtube.skip_reasons. Inspect the next permitted normal-worker upload attempt and its sanitized failure reason. If it returns a real video ID, verify the ledger item is published before claiming success.
