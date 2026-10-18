
import json
import os
import time
import urllib3
from datetime import datetime, timezone

import requests


API_URL = "https://www.hpgamestream.com/api/content/deals/categories?queryDeals=true"
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# TEMPORARY WORKAROUND:
# HP's API certificate is expired. Remove this after HP fixes it.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
            data = json.load(f)

        if isinstance(data, list):
            return set(str(item) for item in data)

        print("[OMEN] Warning: posted.json is not a list.")
        return set()

    except (json.JSONDecodeError, OSError) as exc:
        print(f"[OMEN] Could not load posted.json: {exc}")
        return set()


def save_posted(posted):
    try:
        with open(POSTED_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(posted), f, indent=2)
    except OSError as exc:
        print(f"[OMEN] Could not save posted.json: {exc}")
        raise


def fetch_giveaways():
    HEADERS["currentTimestamp"] = str(int(time.time()))

    try:
        response = requests.get(
            API_URL,
            headers=HEADERS,
            timeout=30,
            verify=False,  # TEMPORARY: expired HP certificate
        )
        response.raise_for_status()
        data = response.json()

    except requests.exceptions.SSLError as exc:
        print(f"[OMEN] SSL error while fetching giveaways: {exc}")
        raise

    except requests.exceptions.HTTPError as exc:
        print(f"[OMEN] HP API returned an HTTP error: {exc}")
        raise

    except requests.exceptions.RequestException as exc:
        print(f"[OMEN] Could not connect to HP API: {exc}")
        raise

    except ValueError as exc:
        print(f"[OMEN] HP API did not return valid JSON: {exc}")
        raise

    giveaways = []
    seen = set()

    def scan(obj, parent_category=None):
        if isinstance(obj, dict):
            current_category = obj.get("category", parent_category)

            if obj.get("category") in {
                "OMEN Giveaways",
                "Expired Giveaways",
            }:
                current_category = obj.get("category")

            # Preserve the original genuine OMEN giveaway filters.
            if (
                obj.get("buttonAction") == "GameCodeHPID"
                and obj.get("vendorPlatformName") == "OMEN"
                and obj.get("discountTag") == "Claim For Free"
                and current_category != "Expired Giveaways"
            ):
                promo_id = str(obj.get("id", ""))

                if promo_id and promo_id != "None" and promo_id not in seen:
                    seen.add(promo_id)
                    giveaways.append(obj)

            for value in obj.values():
                scan(value, current_category)

        elif isinstance(obj, list):
            for item in obj:
                scan(item, parent_category)

    scan(data)

    print("[OMEN] Detected active OMEN giveaways:")

    for promo in giveaways:
        print(
            f"- {promo.get('title')} | "
            f"{promo.get('id')} | "
            f"{promo.get('buttonAction')} | "
            f"{promo.get('codename')}"
        )

    return giveaways


def send_discord(promo):
    if not WEBHOOK_URL:
        raise RuntimeError(
            "WEBHOOK_URL is missing. Check your GitHub Actions secrets."
        )

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
                "inline": True,
            },
            {
                "name": "🎁 Type",
                "value": "Free In-Game Item / Code",
                "inline": True,
            },
        ],
        "footer": {
            "text": "HP OMEN Gaming Hub",
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if image:
        embed["image"] = {"url": image}

    payload = {"embeds": [embed]}

    try:
        response = requests.post(
            WEBHOOK_URL,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()

    except requests.exceptions.RequestException as exc:
        print(f"[DISCORD] Failed to post {title}: {exc}")
        raise

    print(f"[DISCORD] Posted: {title}")


def main():
    print("[OMEN] Checking giveaways...")

    posted = load_posted()

    # If fetching fails, stop without overwriting posted.json.
    giveaways = fetch_giveaways()

    print(
        f"[OMEN] Found {len(giveaways)} "
        f"active OMEN giveaway(s)"
    )

    new_count = 0

    for promo in giveaways:
        promo_id = str(promo.get("id", ""))

        if not promo_id or promo_id == "None" or promo_id in posted:
            continue

        print(f"[NEW] {promo.get('title')}")

        send_discord(promo)

        posted.add(promo_id)
        save_posted(posted)
        new_count += 1

    # Save even when there were no new giveaways.
    save_posted(posted)

    print(f"[OMEN] {new_count} new giveaway(s)")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[OMEN] Workflow failed: {type(exc).__name__}: {exc}")
        raise
