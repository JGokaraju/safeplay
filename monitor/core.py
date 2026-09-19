"""SafePlay monitor logic: polls GitHub for new images, analyzes them, notifies, and talks back via the Pi."""
import json
import os
import sys
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "common"))
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from github_io import GitHubIO  # noqa: E402
import linq  # noqa: E402
import omni  # noqa: E402

INJURY_SPEECH = "Injury detected. Parent notified."
DANGER_SPEECH = "Please follow the park safety guidelines, this is dangerous activity."


class Monitor:
    def __init__(self):
        self.gh = GitHubIO()
        self.poll = float(os.getenv("POLL_SECONDS", "3"))
        self.cooldown = float(os.getenv("SMS_COOLDOWN_SECONDS", "300"))
        self.last_sms = 0.0
        self.events = deque(maxlen=200)  # newest last
        self.last_verdict = None  # (time, status, reason)
        self.last_image = None  # bytes of the last analyzed image

    def log(self, msg):
        line = f"[{datetime.now():%H:%M:%S}] {msg}"
        print(line, flush=True)
        self.events.append(line)

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        self.log("Polling for images...")
        while True:
            try:
                self.check_once()
            except Exception as e:
                self.log(f"Error: {e}")
            time.sleep(self.poll)

    def check_once(self):
        flag = self.gh.read_text("capture_image.json", use_etag=True)
        if not flag or flag == "None":
            return
        try:
            meta = json.loads(flag)
        except json.JSONDecodeError:
            meta = {}
        if meta.get("status") != "new":
            return
        self.log(f"New image ({meta.get('trigger', '?')}) - analyzing")
        image = self.gh.read_bytes("latest_image.jpg")
        self.last_image = image
        try:
            status, reason = omni.analyze(image)
            self.last_verdict = (datetime.now(), status, reason)
            self.log(f"Verdict: {status} - {reason}")
            if status == "injured":
                self.handle_injury(reason)
            elif status == "dangerous":
                self.handle_horseplay()
        finally:
            self.gh.write_file("capture_image.json", "None", "image processed")

    def handle_injury(self, reason="", bypass_cooldown=False):
        if bypass_cooldown or time.time() - self.last_sms >= self.cooldown:
            try:
                linq.send_sms(f"SafePlay alert: possible injury detected at the playground. "
                              f"{reason} ({datetime.now():%H:%M})".replace("  ", " "))
                self.last_sms = time.time()
                self.log("Parent notified by SMS")
            except Exception as e:
                self.log(f"SMS failed: {e}")
        else:
            self.log("SMS suppressed (cooldown)")
        self.gh.write_file("verbal_commands.txt", INJURY_SPEECH, "speak")

    def handle_horseplay(self):
        self.gh.write_file("verbal_commands.txt", DANGER_SPEECH, "speak")
        self.log("Safety warning queued for speaker")

    def request_capture(self):
        self.gh.write_file("capture_request.json", json.dumps({"status": "capture"}), "request photo")
        self.log("Photo requested from Pi")
