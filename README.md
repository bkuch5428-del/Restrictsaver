# Telegram Channel Forwarder
© @thealphabotz | All Rights Reserved

Forwards messages (text + media) from one Telegram channel to another.  
Deployable to **Railway** in a few minutes.

---

## Step 1 — Generate a Session String (local, one-time)

You need Python installed locally for this step only.

```bash
pip install telethon
python sv.py --gen-session
```

Follow the prompts — enter your API ID, API Hash, phone number, and OTP.  
Copy the printed `SESSION_STRING` value.

---

## Step 2 — Deploy to Railway

### Option A — GitHub (recommended)

1. Push this folder to a GitHub repo.
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**.
3. Select your repo.
4. Go to your service → **Variables** tab and add:

| Variable | Value |
|---|---|
| `API_ID` | from my.telegram.org |
| `API_HASH` | from my.telegram.org |
| `SESSION_STRING` | generated in Step 1 |
| `SOURCE_CHANNEL` | e.g. `-100xxxxxxxxxx` |
| `DESTINATION_CHANNEL` | e.g. `-100xxxxxxxxxx` |
| `START_POST_ID` | `2` (or wherever you want to start) |

5. Railway auto-deploys. Check **Logs** to confirm it's running.

### Option B — Railway CLI

```bash
npm install -g @railway/cli
railway login
railway init
railway up
railway variables set API_ID=... API_HASH=... SESSION_STRING=... ...
```

---

## Optional Variables (have defaults)

| Variable | Default | Description |
|---|---|---|
| `START_POST_ID` | `2` | First message ID to forward |
| `BATCH_SIZE` | `1000` | Messages per batch |
| `DELAY` | `5` | Seconds between each forward |
| `PAUSE_HOURS` | `3` | Hours to pause between batches |
| `MAX_RETRIES` | `3` | Retries per message on error |

---

## Local Testing

```bash
cp .env.example .env
# fill in .env values
pip install -r requirements.txt
python sv.py
```
