import os

import requests


def send_sms(text):
    r = requests.post(
        "https://api.linqapp.com/api/partner/v3/chats",
        headers={"Authorization": f"Bearer {os.environ['LINQ_API_KEY']}"},
        json={
            "from": os.environ["LINQ_FROM"],
            "to": [os.environ["PARENT_PHONE"]],
            "message": {"parts": [{"type": "text", "value": text}]},
        },
        timeout=30,
    )
    r.raise_for_status()
