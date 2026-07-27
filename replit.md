# Telegram Channel Forwarder

Forwards messages (text + media) from one Telegram channel to another.

## Stack

- **Language**: Python 3.12
- **Library**: Telethon (MTProto)
- **System tool**: ffmpeg (video thumbnails & streaming metadata)
- **Entry point**: `sv.py`

## How to run on Replit

1. Set the required secrets in the **Secrets** tab:
   - `API_ID` — from https://my.telegram.org
   - `API_HASH` — from https://my.telegram.org
   - `SESSION_STRING` — generate locally: `python sv.py --gen-session`
   - `SOURCE_CHANNEL` — numeric channel ID (e.g. `-100xxxxxxxxxx`)
   - `DESTINATION_CHANNEL` — numeric channel ID
2. Optionally set: `START_POST_ID`, `BATCH_SIZE`, `DELAY`, `PAUSE_HOURS`, `MAX_RETRIES`
3. Start the **"Telegram Forwarder"** workflow (Run button)

## Deployment targets

| Platform | Config file     | Type            |
|----------|-----------------|-----------------|
| Replit   | `.replit`       | Console workflow |
| Render   | `render.yaml`   | Background worker |
| Railway  | `railway.toml`  | Worker process  |
| Docker   | `Dockerfile`    | Container       |

## Environment variables

| Variable             | Required | Default | Description                          |
|----------------------|----------|---------|--------------------------------------|
| `API_ID`             | ✅       | —       | Telegram API ID                      |
| `API_HASH`           | ✅       | —       | Telegram API hash                    |
| `SESSION_STRING`     | ✅       | —       | Telethon StringSession               |
| `SOURCE_CHANNEL`     | ✅       | —       | Source channel numeric ID            |
| `DESTINATION_CHANNEL`| ✅       | —       | Destination channel numeric ID       |
| `START_POST_ID`      | ❌       | `2`     | First message ID to forward          |
| `BATCH_SIZE`         | ❌       | `1000`  | Messages fetched per batch           |
| `DELAY`              | ❌       | `5`     | Seconds between each forwarded msg   |
| `PAUSE_HOURS`        | ❌       | `3`     | Hours to pause between batches       |
| `MAX_RETRIES`        | ❌       | `3`     | Per-message retry attempts           |

## User preferences

- Do not change the core logic of `sv.py` — functionality must be preserved as-is.
