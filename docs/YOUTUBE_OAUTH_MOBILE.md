# YouTube OAuth on Android (ViralFutbol and BAMLOOP)

Use a separate OAuth client and refresh token for each channel unless both services deliberately publish to the same channel. A token must be used with **the same client ID and client secret** that issued it. Do not paste credentials into a chat, GitHub issue, or commit.

1. In Google Cloud, enable YouTube Data API v3 for the correct project. Set the OAuth consent screen to Production when eligible; an External app left in Testing may issue short-lived refresh tokens. Add your Google account as a test user if the app is still in Testing. Register `https://developers.google.com/oauthplayground` as an authorized redirect URI on a **Web application** OAuth client.
2. On Android Chrome open [OAuth 2.0 Playground](https://developers.google.com/oauthplayground/). Open its settings, select **Use your own OAuth credentials**, and enter the exact client ID and secret for the service you are configuring. Use a server-side/offline flow with **Offline** access and **Consent Screen** prompt. Select `https://www.googleapis.com/auth/youtube.upload` and `https://www.googleapis.com/auth/youtube.readonly`. Sign in to the intended account and select its correct YouTube channel.
3. Exchange the authorization code in the Playground. The resulting refresh token is a secret. In the corresponding **Render service → Environment** set:

   | Service | Client ID | Client secret | Refresh token | Verified channel ID |
   | --- | --- | --- | --- | --- |
   | ViralFutbol | `YOUTUBE_CLIENT_ID` | `YOUTUBE_CLIENT_SECRET` | `YOUTUBE_REFRESH_TOKEN` | `YOUTUBE_EXPECTED_CHANNEL_ID` |
   | BAMLOOP | `MEME_YOUTUBE_CLIENT_ID` | `MEME_YOUTUBE_CLIENT_SECRET` | `MEME_YOUTUBE_REFRESH_TOKEN` | `MEME_YOUTUBE_EXPECTED_CHANNEL_ID` |

4. To independently verify an authorization code with local Python (including Termux), use `python -m scripts.youtube_oauth_bootstrap --profile viral` or `--profile bamloop`. The tool prints a mobile consent URL and `--exchange` asks for the client secret and code privately, tests refresh and `channels.list(mine=true)`, then writes a private `youtube_oauth_<profile>.json` file. Configure the four Render fields from this file yourself, and delete the file afterward. Never add it to git. Authorization codes expire quickly and may be used only once.
5. Check `/status` after Render redeploy. `youtube_auth_ready=true`, `oauth_refresh_error=null`, and `youtube_channel_id` matching the configured ID prove the current worker successfully refreshed and queried the channel. YouTube upload occurs only at a valid ledger slot; no test video is uploaded by this procedure.

The service refuses to publish when the expected channel ID is unset or mismatched. Do not reset uncertain ledger reservations; first reconcile them against the channel's actual upload history.
