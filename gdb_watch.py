#!/usr/bin/env python3
"""
בודק כל דקה אם GDB פתוחה בוולט, ומפרסם לערוץ טלגרם רק כשהמצב משתנה:
  "GDB פתוח! ..."  /  "GDB עכשיו סגור :( ..."
את הערוץ פשוט עושים Mute / Unmute.

ללא תלויות - Python 3.9+ בלבד.

משתני סביבה:
  TELEGRAM_TOKEN  - הטוקן של הבוט (מ-@BotFather)
  CHANNEL_ID      - שם הערוץ, למשל @gdb_open_alerts
  VENUE_SLUG      - ברירת מחדל gdb
  RUN_MINUTES     - כמה דקות לרוץ לפני יציאה (0 = לנצח). ב-GitHub Actions: 55
  POLL_SECONDS    - ברירת מחדל 60
  ANNOUNCE        - "1" = לפרסם את המצב הנוכחי מיד בהפעלה (לבדיקה)
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
CHANNEL = os.environ.get("CHANNEL_ID", "").strip()
SLUG = os.environ.get("VENUE_SLUG", "gdb").strip()
RUN_MINUTES = float(os.environ.get("RUN_MINUTES", "0") or 0)
POLL_SECONDS = max(20, int(os.environ.get("POLL_SECONDS", "60") or 60))
ANNOUNCE = os.environ.get("ANNOUNCE", "") == "1"
STATE_FILE = os.environ.get("STATE_FILE", "state.json")

WOLT_URL = f"https://consumer-api.wolt.com/order-xp/web/v1/venue/slug/{urllib.parse.quote(SLUG)}/dynamic/?selected_delivery_method=homedelivery"
VENUE_LINK = f"https://wolt.com/he/isr/tel-aviv/restaurant/{SLUG}"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def http_json(url, data=None):
    headers = {"User-Agent": UA, "Accept": "application/json"}
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def is_available():
    """True = אפשר להזמין עכשיו. זורק שגיאה אם וולט לא ענה."""
    v = http_json(WOLT_URL).get("venue") or {}
    status = v.get("delivery_open_status") or v.get("open_status") or {}
    return bool(v.get("online")) and bool(status.get("is_open"))


def post(available):
    name = "GDB" if SLUG == "gdb" else SLUG
    text = (f"🍔 {name} פתוח! לחצו כאן להזמנה: {VENUE_LINK}" if available
            else f"{name} עכשיו סגור :( {VENUE_LINK}")
    http_json(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
              {"chat_id": CHANNEL, "text": text,
               # הודעת "סגור" נשלחת בשקט, בלי צלצול
               "disable_notification": not available})
    log("posted:", text)


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f).get("available")
    except Exception:
        return None


def save_state(available):
    with open(STATE_FILE, "w") as f:
        json.dump({"available": available, "at": time.time()}, f)


def main():
    if not TOKEN or not CHANNEL:
        sys.exit("חסר TELEGRAM_TOKEN או CHANNEL_ID")
    last = load_state()
    log(f"start: slug={SLUG} last={last}")
    end = time.time() + RUN_MINUTES * 60 if RUN_MINUTES else None
    first = True
    while end is None or time.time() < end:
        try:
            now = is_available()
            if (first and ANNOUNCE) or (now != last and (last is not None or now)):
                post(now)
            if now != last:
                last = now
                save_state(now)
            log("available" if now else "closed")
        except Exception as e:
            log("error:", e)  # לא משנים מצב כשיש שגיאה
        first = False
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
