"""ElevenLabs text-to-speech playback with on-disk caching of repeated phrases."""
import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import requests

CACHE = Path(__file__).resolve().parent / ".cache"


def _synthesize(text):
    CACHE.mkdir(exist_ok=True)
    path = CACHE / (hashlib.sha1(text.encode()).hexdigest() + ".mp3")
    if path.exists():
        return path
    voice = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
        headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Accept": "audio/mpeg"},
        json={"text": text, "model_id": "eleven_multilingual_v2"},
        timeout=60,
    )
    r.raise_for_status()
    path.write_bytes(r.content)
    return path


def speak(text):
    path = _synthesize(text)
    if shutil.which("mpg123"):
        cmd = ["mpg123", "-q", str(path)]
    else:
        cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(path)]
    subprocess.run(cmd, check=True)
