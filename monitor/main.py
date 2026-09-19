"""SafePlay laptop monitor: polls GitHub for new images, analyzes them, notifies, and talks back via the Pi."""
import json
import os
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import scrolledtext

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "common"))
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from github_io import GitHubIO  # noqa: E402
import linq  # noqa: E402
import omni  # noqa: E402

INJURY_SPEECH = "Injury detected. Parent notified."
DANGER_SPEECH = "Please follow the park safety guidelines, this is dangerous activity."


class App:
    def __init__(self):
        self.gh = GitHubIO()
        self.poll = float(os.getenv("POLL_SECONDS", "3"))
        self.cooldown = float(os.getenv("SMS_COOLDOWN_SECONDS", "300"))
        self.last_sms = 0.0
        self.root = tk.Tk()
        self.root.title("SafePlay Monitor")
        tk.Button(self.root, text="Take Photo Now", font=("Segoe UI", 14),
                  command=self.request_capture).pack(padx=10, pady=10)
        self.log_box = scrolledtext.ScrolledText(self.root, width=80, height=20, state="disabled")
        self.log_box.pack(padx=10, pady=(0, 10))
        threading.Thread(target=self.loop, daemon=True).start()

    def log(self, msg):
        line = f"[{datetime.now():%H:%M:%S}] {msg}\n"
        print(line, end="", flush=True)
        self.root.after(0, self._append, line)

    def _append(self, line):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", line)
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def request_capture(self):
        def work():
            try:
                self.gh.write_file("capture_request.json", json.dumps({"status": "capture"}), "request photo")
                self.log("Photo requested from Pi")
            except Exception as e:
                self.log(f"Capture request failed: {e}")
        threading.Thread(target=work, daemon=True).start()

    def loop(self):
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
        try:
            status, reason = omni.analyze(image)
            self.log(f"Verdict: {status} - {reason}")
            self.act(status, reason)
        finally:
            self.gh.write_file("capture_image.json", "None", "image processed")

    def act(self, status, reason):
        if status == "injured":
            if time.time() - self.last_sms >= self.cooldown:
                try:
                    linq.send_sms(f"SafePlay alert: possible injury detected at the playground. "
                                  f"{reason} ({datetime.now():%H:%M})")
                    self.last_sms = time.time()
                    self.log("Parent notified by SMS")
                except Exception as e:
                    self.log(f"SMS failed: {e}")
            else:
                self.log("SMS suppressed (cooldown)")
            self.gh.write_file("verbal_commands.txt", INJURY_SPEECH, "speak")
        elif status == "dangerous":
            self.gh.write_file("verbal_commands.txt", DANGER_SPEECH, "speak")


if __name__ == "__main__":
    App().root.mainloop()
