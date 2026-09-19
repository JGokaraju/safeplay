"""SafePlay Raspberry Pi agent.

Threads:
  1. KY-037 sound sensor fires -> photo -> upload
  2. capture_request.json == capture -> photo -> upload
  3. verbal_commands.txt has text -> speak via ElevenLabs -> reset to None

LEDs: green = normal/idle, red = speaking.
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

from dotenv import load_dotenv
from gpiozero import LED, DigitalInputDevice

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "common"))
load_dotenv(HERE / ".env")

from github_io import GitHubIO  # noqa: E402
import camera  # noqa: E402
import speaker  # noqa: E402

gh = GitHubIO()
POLL = float(os.getenv("POLL_SECONDS", "2"))
COOLDOWN = float(os.getenv("TRIGGER_COOLDOWN_SECONDS", "10"))
SOUND_PIN = int(os.getenv("SOUND_PIN", "22"))
# Most KY-037 boards pull D0 LOW when sound exceeds the pot threshold (onboard LED lights up). Set to 1 if yours is inverted.
SOUND_ACTIVE_HIGH = os.getenv("SOUND_ACTIVE_HIGH", "0") == "1"
green = LED(int(os.getenv("GREEN_LED_PIN", "17")))
red = LED(int(os.getenv("RED_LED_PIN", "27")))
capture_lock = threading.Lock()


def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def set_led(talking):
    if talking:
        green.off()
        red.on()
    else:
        red.off()
        green.on()


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

    def on_sound():
        if time.time() - last[0] > COOLDOWN:
            last[0] = time.time()
            triggers.put(1)

    # pull_up=None: the module drives the line itself. bounce_time debounces the comparator output.
    sensor = DigitalInputDevice(SOUND_PIN, pull_up=None, active_state=SOUND_ACTIVE_HIGH, bounce_time=0.05)
    sensor.when_activated = on_sound
    log(f"Listening for sound on GPIO{SOUND_PIN}")
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
                set_led(True)
                try:
                    speaker.speak(text)
                finally:
                    set_led(False)
        except Exception as e:
            log(f"Speech error: {e}")
        time.sleep(POLL)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test-leds":
        for name, led in (("green", green), ("red", red)):
            log(f"{name} LED on for 2s")
            led.on()
            time.sleep(2)
            led.off()
        sys.exit(0)
    set_led(False)
    for fn in (request_loop, speech_loop):
        threading.Thread(target=fn, daemon=True).start()
    try:
        sound_loop()
    finally:
        green.off()
        red.off()
