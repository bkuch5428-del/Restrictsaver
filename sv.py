# © @thealphabotz | All Rights Reserved

import asyncio
import logging
import os
import random
import subprocess
import sys
import glob
from pathlib import Path
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError
from telethon.tl.types import (
    MessageMediaDocument,
    MessageMediaPhoto,
    DocumentAttributeVideo,
    DocumentAttributeAudio,
    DocumentAttributeFilename,
)

# ─────────────────────────────────────────────
#  Logging
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  Config — Railway → Variables tab
# ─────────────────────────────────────────────
def get_env(key, required=True, cast=str, default=None):
    val = os.environ.get(key, default)
    if required and not val:
        logger.error(f"Missing required env var: {key}")
        sys.exit(1)
    return cast(val) if val is not None else default

API_ID              = get_env("API_ID",              cast=int)
API_HASH            = get_env("API_HASH")
SESSION_STRING      = get_env("SESSION_STRING")
SOURCE_CHANNEL      = get_env("SOURCE_CHANNEL",      cast=int)
DESTINATION_CHANNEL = get_env("DESTINATION_CHANNEL", cast=int)
START_POST_ID       = get_env("START_POST_ID",       cast=int,   required=False, default="2")
BATCH_SIZE          = get_env("BATCH_SIZE",          cast=int,   required=False, default="1000")
DELAY               = get_env("DELAY",               cast=float, required=False, default="5")
PAUSE_HOURS         = get_env("PAUSE_HOURS",         cast=float, required=False, default="3")
MAX_RETRIES         = get_env("MAX_RETRIES",         cast=int,   required=False, default="3")

DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".flv", ".webm", ".m4v", ".3gp"}
AUDIO_EXTS = {".mp3", ".m4a", ".aac", ".ogg", ".flac", ".wav", ".opus"}

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)


# ─────────────────────────────────────────────
#  ffprobe helpers
# ─────────────────────────────────────────────
def ffprobe_available() -> bool:
    try:
        subprocess.run(
            ["ffprobe", "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False

FFPROBE_OK = ffprobe_available()

def get_video_info(file_path: str) -> dict:
    """
    Returns dict with keys: duration (int seconds), width, height.
    Falls back to zeros if ffprobe unavailable or fails.
    """
    if not FFPROBE_OK:
        return {"duration": 0, "width": 0, "height": 0}
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height,duration",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1",
                file_path,
            ],
            capture_output=True, text=True, timeout=60,
        )
        info = {}
        for line in result.stdout.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                info[k.strip()] = v.strip()

        duration = int(float(info.get("duration", 0) or 0))
        width    = int(info.get("width",    0) or 0)
        height   = int(info.get("height",   0) or 0)
        return {"duration": duration, "width": width, "height": height}
    except Exception as e:
        logger.warning(f"ffprobe info failed: {e}")
        return {"duration": 0, "width": 0, "height": 0}


def get_audio_duration(file_path: str) -> int:
    """Returns audio duration in seconds via ffprobe."""
    if not FFPROBE_OK:
        return 0
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path,
            ],
            capture_output=True, text=True, timeout=30,
        )
        return int(float(result.stdout.strip() or 0))
    except Exception:
        return 0


def extract_thumbnail(file_path: str, duration: int) -> str | None:
    """
    Extracts a JPEG thumbnail from a random timestamp in the video.
    Returns the thumb path, or None on failure.
    """
    if not FFPROBE_OK or duration == 0:
        return None
    try:
        # Pick a random second — avoid first/last 5% to dodge black frames
        margin   = max(1, int(duration * 0.05))
        seek_sec = random.randint(margin, max(margin, duration - margin))

        thumb_path = file_path + "_thumb.jpg"
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-ss", str(seek_sec),
                "-i", file_path,
                "-frames:v", "1",
                "-vf", "scale=320:-1",
                "-q:v", "3",
                thumb_path,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
            check=True,
        )
        return thumb_path if os.path.exists(thumb_path) else None
    except Exception as e:
        logger.warning(f"Thumbnail extraction failed: {e}")
        return None


# ─────────────────────────────────────────────
#  Cleanup helpers
# ─────────────────────────────────────────────
def safe_delete(*paths):
    """Delete files silently, ignoring errors."""
    for p in paths:
        if p and os.path.exists(p):
            try:
                os.remove(p)
            except OSError as e:
                logger.warning(f"Could not delete {p}: {e}")


def cleanup_downloads():
    """Nuke everything left in the downloads dir (orphaned files)."""
    for f in DOWNLOAD_DIR.glob("*"):
        try:
            f.unlink()
        except OSError:
            pass


# ─────────────────────────────────────────────
#  Media type detection
# ─────────────────────────────────────────────
def get_media_kind(message) -> str:
    """
    Returns: 'video' | 'audio' | 'photo' | 'document' | 'none'
    """
    if not message.media:
        return "none"

    if isinstance(message.media, MessageMediaPhoto):
        return "photo"

    if isinstance(message.media, MessageMediaDocument):
        doc = message.media.document
        attrs = {type(a): a for a in doc.attributes}

        if DocumentAttributeVideo in attrs:
            return "video"
        if DocumentAttributeAudio in attrs:
            return "audio"

        # Fallback: check filename extension
        if DocumentAttributeFilename in attrs:
            fname = attrs[DocumentAttributeFilename].file_name.lower()
            ext   = os.path.splitext(fname)[1]
            if ext in VIDEO_EXTS:
                return "video"
            if ext in AUDIO_EXTS:
                return "audio"

        return "document"

    return "none"


# ─────────────────────────────────────────────
#  Core send functions
# ─────────────────────────────────────────────
async def send_video(file_path: str, caption: str):
    info      = get_video_info(file_path)
    duration  = info["duration"]
    width     = info["width"]
    height    = info["height"]
    thumb     = extract_thumbnail(file_path, duration)

    logger.info(
        f"  📹 Video — {duration}s  {width}x{height}  "
        f"thumb={'✅' if thumb else '❌'}"
    )

    try:
        await client.send_file(
            DESTINATION_CHANNEL,
            file_path,
            caption=caption,
            thumb=thumb,
            # These attributes make Telegram treat it as a streamable video
            attributes=[
                DocumentAttributeVideo(
                    duration=duration,
                    w=width,
                    h=height,
                    supports_streaming=True,
                )
            ],
            force_document=False,
        )
    finally:
        safe_delete(file_path, thumb)


async def send_audio(file_path: str, caption: str):
    duration = get_audio_duration(file_path)
    logger.info(f"  🎵 Audio — {duration}s")
    try:
        await client.send_file(
            DESTINATION_CHANNEL,
            file_path,
            caption=caption,
            attributes=[
                DocumentAttributeAudio(
                    duration=duration,
                    voice=False,
                )
            ],
            force_document=False,
        )
    finally:
        safe_delete(file_path)


async def send_photo(file_path: str, caption: str):
    logger.info("  🖼️  Photo")
    try:
        await client.send_file(
            DESTINATION_CHANNEL,
            file_path,
            caption=caption,
            force_document=False,
        )
    finally:
        safe_delete(file_path)


async def send_document(file_path: str, caption: str):
    logger.info("  📄 Document")
    try:
        await client.send_file(
            DESTINATION_CHANNEL,
            file_path,
            caption=caption,
            force_document=True,
        )
    finally:
        safe_delete(file_path)


# ─────────────────────────────────────────────
#  Channel resolver
# ─────────────────────────────────────────────
async def get_channel_entity(channel_id: int):
    try:
        entity = await client.get_entity(channel_id)
        logger.info(f"Resolved channel: {entity.title}  (ID: {entity.id})")
        return entity
    except ValueError as e:
        logger.error(f"Cannot resolve channel {channel_id}: {e}")
        logger.info("Make sure the account is a member of that channel.")
        raise
    except Exception as e:
        logger.error(f"Unexpected error resolving entity: {e}")
        raise


# ─────────────────────────────────────────────
#  Per-message forwarder
# ─────────────────────────────────────────────
async def forward_single_message(source_entity, msg_id: int):
    """
    Returns:
      True  — forwarded or gracefully skipped
      False — all retries exhausted
      None  — no message (end of channel)
    """
    for attempt in range(1, MAX_RETRIES + 1):
        file_path = None
        thumb     = None
        try:
            message = await client.get_messages(source_entity, ids=msg_id)

            if not message:
                logger.info(f"[{msg_id}] No message — end of channel.")
                return None

            kind    = get_media_kind(message)
            caption = message.text or ""

            if kind == "none":
                if message.text:
                    await client.send_message(DESTINATION_CHANNEL, message.text)
                    logger.info(f"[{msg_id}] ✅ Text forwarded")
                else:
                    logger.info(f"[{msg_id}] — Empty message, skipped.")
                return True

            # Download to our controlled directory
            file_path = await client.download_media(
                message.media,
                file=str(DOWNLOAD_DIR) + "/",
            )

            if not file_path:
                logger.warning(f"[{msg_id}] ⚠️  Download returned nothing — skipping.")
                return True

            logger.info(f"[{msg_id}] Downloaded → {file_path}  (kind={kind})")

            if kind == "video":
                await send_video(file_path, caption)
            elif kind == "audio":
                await send_audio(file_path, caption)
            elif kind == "photo":
                await send_photo(file_path, caption)
            else:
                await send_document(file_path, caption)

            logger.info(f"[{msg_id}] ✅ Forwarded ({kind})")
            return True

        except FloodWaitError as e:
            logger.warning(f"[{msg_id}] 🚦 FloodWait — sleeping {e.seconds}s …")
            safe_delete(file_path, thumb)
            await asyncio.sleep(e.seconds + 5)
            # Don't count flood waits as a retry attempt
            continue

        except Exception as e:
            safe_delete(file_path, thumb)
            logger.error(f"[{msg_id}] Attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(DELAY * attempt)
            else:
                logger.error(f"[{msg_id}] ❌ Giving up.")

    return False


# ─────────────────────────────────────────────
#  Batch loop
# ─────────────────────────────────────────────
async def forward_batch(start_id: int):
    # Wipe any leftover files from a previous crashed run
    cleanup_downloads()

    async with client:
        logger.info("🔗 Connected to Telegram")
        if not FFPROBE_OK:
            logger.warning(
                "⚠️  ffprobe not found — video duration/thumbnail/streaming "
                "metadata will be absent. Install ffmpeg on your system."
            )

        source_entity = await get_channel_entity(SOURCE_CHANNEL)
        logger.info(
            f"▶️  Forwarder started | "
            f"Source: {SOURCE_CHANNEL} → Dest: {DESTINATION_CHANNEL} | "
            f"From ID: {start_id}"
        )

        message_id  = start_id
        batch_count = 0
        total_fwd   = 0

        while True:
            end_id = message_id + BATCH_SIZE
            logger.info(f"── Batch {batch_count + 1}: IDs {message_id} → {end_id - 1} ──")

            for msg_id in range(message_id, end_id):
                result = await forward_single_message(source_entity, msg_id)

                if result is None:
                    logger.info(f"🏁 Done. Total forwarded: {total_fwd}")
                    cleanup_downloads()
                    return

                if result:
                    total_fwd += 1

                processed = msg_id - message_id + 1
                if processed % 50 == 0:
                    logger.info(
                        f"  📊 {processed}/{BATCH_SIZE} in batch | "
                        f"Total: {total_fwd}"
                    )

                await asyncio.sleep(DELAY)

            batch_count += 1
            message_id = end_id
            logger.info(
                f"✔️  Batch {batch_count} done — "
                f"pausing {PAUSE_HOURS}h …"
            )
            await asyncio.sleep(PAUSE_HOURS * 3600)


if __name__ == "__main__":
    asyncio.run(forward_batch(START_POST_ID))
