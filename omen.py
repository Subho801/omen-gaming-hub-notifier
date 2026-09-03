import json
import os
import time
from datetime import datetime

import requests


API_URL = "https://www.hpgamestream.com/api/content/deals/categories?queryDeals=true"
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

HEADERS = {
    "User-Agent": "OGH-UL-1101.2607.3.0",
    "AppVersion_OGH": "1101.2607.3.0",
    "Client-id": "279d5b10-2464-44e7-846b-76fa09f34b45",
    "platform": "OTHER",
    "country": "IN",
    "appLaunchCount": "1",
    "deviceType": "Other",
    "language": "en",
    "currentTimestamp": str(int(time.time())),
    "connectedDevices": "",
    "template": "2",
    "appVersion": "1101.2607.3.0",
    "featureByte": "",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "version": "7",
}

POSTED_FILE = "posted.json"


def load_posted():
    if not os.path.exists(POSTED_FILE):
        return set()

    try:
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except (json.JSONDecodeError, OSError):
        return set()


def save_posted(posted):
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(posted), f, indent=2)


def fetch_giveaways():
    HEADERS["currentTimestamp"] = str(int(time.time()))

    response = requests.get(
        API_URL,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    for category in data.get("data", []):
        for child in category.get("children", []):
            if child.get("category") != "OMEN Giveaways":
                continue

            promotions = child.get("promotions", [])

            return [
                promo
                for promo in promotions
                if promo.get("buttonAction") == "GameCodeHPID"
            ]

    return []


def send_discord(promo):
    title = promo.get("title", "OMEN Giveaway")
    body = promo.get("body", "")
    image = promo.get("imageUrl")

    embed = {
        "title": f"🎁 {title}",
        "description": body,
        "color": 0x00AEEF,
        "fields": [
            {
                "name": "🎮 Platform",
                "value": "OMEN Gaming Hub",
                "inline": True
            },
            {
                "name": "🎁 Type",
                "value": "Free In-Game Item / Code",
                "inline": True
            }
        ],
        "footer": {
            "text": "HP OMEN Gaming Hub"
        },
        "timestamp": datetime.utcnow().isoformat()
    }

    if image:
        embed["image"] = {
            "url": image
        }

    payload = {
        "embeds": [embed]
    }

    response = requests.post(
        WEBHOOK_URL,
        json=payload,
        timeout=30
    )

    response.raise_for_status()

    print(f"[DISCORD] Posted: {title}")


def main():
    print("[OMEN] Checking giveaways...")

    posted = load_posted()
    giveaways = fetch_giveaways()

    print(
        f"[OMEN] Found {len(giveaways)} "
        f"GameCodeHPID giveaway(s)"
    )

    new_count = 0

    for promo in giveaways:
        promo_id = str(promo.get("id"))

        if not promo_id or promo_id in posted:
            continue

        print(f"[NEW] {promo.get('title')}")

        send_discord(promo)

        posted.add(promo_id)
        new_count += 1

    save_posted(posted)

    print(f"[OMEN] {new_count} new giveaway(s)")


if __name__ == "__main__":
    main()
