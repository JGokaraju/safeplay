"""SafePlay Raspberry Pi agent.

Threads:
  1. loud sound  -> photo -> upload
  2. capture_request.json == capture -> photo -> upload
  3. verbal_commands.txt has text -> speak via ElevenLabs -> reset to None
"""
import json
import os
import queue
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import sounddevice as sd
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "common"))
load_dotenv(HERE / ".env")

from github_io import GitHubIO  # noqa: E402
import camera  # noqa: E402
import speaker  # noqa: E402

gh = GitHubIO()
POLL = float(os.getenv("POLL_SECONDS", "2"))
THRESHOLD = float(os.getenv("SOUND_THRESHOLD_RMS", "0.15"))
COOLDOWN = float(os.getenv("TRIGGER_COOLDOWN_SECONDS", "10"))
capture_lock = threading.Lock()


def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def take_and_upload(trigger):
    with capture_lock:
        jpeg = camera.capture_jpeg()
        gh.write_file("latest_image.jpg", jpeg, f"image ({trigger})")  # image first, flag second
        meta = {"status": "new", "id": str(uuid.uuid4()),
                "ts": datetime.now(timezone.utc).isoformat(), "trigger": trigger}
        gh.write_file("capture_image.json", json.dumps(meta), "new image")
        log(f"Uploaded image ({trigger})")


def sound_loop():
    triggers = queue.Queue()
    last = [0.0]

    def callback(indata, frames, t, status):
        if np.sqrt(np.mean(indata ** 2)) > THRESHOLD and time.time() - last[0] > COOLDOWN:
            last[0] = time.time()
            triggers.put(1)

    with sd.InputStream(channels=1, samplerate=16000, blocksize=4000, callback=callback):
        log(f"Listening for loud sounds (RMS > {THRESHOLD})")
        while True:
            triggers.get()
            try:
                take_and_upload("sound")
            except Exception as e:
                log(f"Sound capture failed: {e}")


def request_loop():
    while True:
        try:
            v = gh.read_text("capture_request.json", use_etag=True)
            if v and v != "None" and json.loads(v).get("status") == "capture":
                gh.write_file("capture_request.json", "None", "request handled")
                take_and_upload("manual")
        except Exception as e:
            log(f"Request poll error: {e}")
        time.sleep(POLL)


def speech_loop():
    while True:
        try:
            text = gh.read_text("verbal_commands.txt", use_etag=True)
            if text and text != "None":
                gh.write_file("verbal_commands.txt", "None", "spoken")  # clear first: avoid repeats on failure
                log(f"Speaking: {text}")
                speaker.speak(text)
        except Exception as e:
            log(f"Speech error: {e}")
        time.sleep(POLL)


if __name__ == "__main__":
    for fn in (request_loop, speech_loop):
        threading.Thread(target=fn, daemon=True).start()
    sound_loop()
