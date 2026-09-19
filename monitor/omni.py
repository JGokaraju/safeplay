import base64
import json
import os
import re

import requests

PROMPT = (
    "You are a playground safety monitor. Look at this image and decide what is happening. "
    "Answer with ONLY a JSON object: {\"status\": \"injured\" | \"dangerous\" | \"none\", \"reason\": \"<one short sentence>\"}. "
    "Use \"injured\" if someone appears injured or has fallen and is not getting up. "
    "Use \"dangerous\" if there is dangerous activity or horseplay (e.g. climbing where unsafe, pushing, "
    "jumping from heights, rough play). Use \"none\" if nothing concerning is happening."
)


def analyze(image_bytes):
    b64 = base64.b64encode(image_bytes).decode()
    r = requests.post(
        os.environ["OMNI_BASE_URL"].rstrip("/") + "/chat/completions",
        headers={"Authorization": f"Bearer {os.environ['OMNI_API_KEY']}"},
        json={
            "model": os.environ["OMNI_MODEL"],
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ]}],
            "temperature": 0,
        },
        timeout=90,
    )
    r.raise_for_status()
    text = r.json()["choices"][0]["message"]["content"]
    m = re.search(r"\{.*\}", text, re.S)
    try:
        out = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        out = {}
    status = str(out.get("status", "")).lower()
    if status not in ("injured", "dangerous", "none"):
        status = "none"
        out["reason"] = f"unparseable model reply: {text[:120]}"
    return status, out.get("reason", "")
