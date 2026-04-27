import os
import time
import random
import asyncio
import threading
import datetime
import requests
from flask import Flask
from playwright.async_api import async_playwright

# ================= CONFIG =================
GRAPHQL_URL = "https://qy64m4juabaffl7tjakii4gdoa.appsync-api.eu-west-1.amazonaws.com/graphql"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_IDS = [c.strip() for c in os.getenv("TELEGRAM_CHAT_IDS", "").split(",") if c.strip()]

CHECK_INTERVAL_MIN = 4
CHECK_INTERVAL_MAX = 7

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/132.0",
]

# ================= GLOBAL STATE =================
seen_jobs = set()
last_run_time = time.time()
BOT_TIMEOUT = 30

bot_running = False
restart_timestamps = []
MAX_RESTARTS = 5
RESTART_WINDOW = 300  # seconds

lock = threading.Lock()
app = Flask(__name__)

# ================= TELEGRAM =================
def send_telegram(msg):
    for chat_id in CHAT_IDS:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                data={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"},
                timeout=10
            )
        except Exception as e:
            print("Telegram error:", e)

# ================= HEARTBEAT =================
def heartbeat():
    while True:
        try:
            status = "RUNNING" if bot_running else "STOPPED"
            msg = (
                f"✅ *Bot Status: {status}*\n"
                f"⏰ {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"🔁 Restarts: {len(restart_timestamps)}/{MAX_RESTARTS}"
            )
            send_telegram(msg)
            print("📡 Heartbeat sent")
        except Exception as e:
            print("Heartbeat error:", e)

        time.sleep(3600)

# ================= TOKEN =================
async def get_token(browser):
    try:
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS)
        )

        page = await context.new_page()

        await page.route("**/*", lambda route: asyncio.create_task(
            route.abort() if route.request.resource_type in ["image", "stylesheet", "font"]
            else route.continue_()
        ))

        await page.goto("https://www.jobsatamazon.co.uk/", timeout=30000)

        cookies = await context.cookies()
        await context.close()

        for c in cookies:
            if "session" in c["name"].lower():
                return f"Bearer {c['value']}"

    except Exception as e:
        print("Token error:", e)

    return None

# ================= FETCH =================
def fetch_jobs(token):
    headers = {
        "Authorization": token,
        "Content-Type": "application/json",
        "User-Agent": random.choice(USER_AGENTS),
        "Origin": "https://www.jobsatamazon.co.uk",
        "Referer": "https://www.jobsatamazon.co.uk/"
    }

    payload = {
        "operationName": "searchJobCardsByLocation",
        "variables": {
            "searchJobRequest": {
                "locale": "en-GB",
                "country": "United Kingdom",
                "keyWords": "Warehouse Operative",
                "pageSize": 20
            }
        },
        "query": "query searchJobCardsByLocation($searchJobRequest: SearchJobRequest!) { searchJobCardsByLocation(searchJobRequest: $searchJobRequest) { jobCards { jobId jobTitle city totalPayRateMax } } }"
    }

    try:
        res = requests.post(GRAPHQL_URL, headers=headers, json=payload, timeout=10)
        data = res.json()

        jobs = data.get("data", {}).get("searchJobCardsByLocation", {}).get("jobCards", [])
        print(f"📦 {len(jobs)} jobs")

        if not jobs:
            print("⚠️ Possible soft block")

        for job in jobs:
            job_id = job["jobId"]

            if job_id not in seen_jobs:
                seen_jobs.add(job_id)

                msg = (
                    f"🚨 *Amazon Job Alert*\n"
                    f"💼 {job['jobTitle']}\n"
                    f"📍 {job['city']}\n"
                    f"💰 £{job['totalPayRateMax']}/hr\n"
                    f"https://www.jobsatamazon.co.uk/app#/jobDetail?jobId={job_id}"
                )

                print("🔥 NEW JOB:", job['jobTitle'])
                send_telegram(msg)

    except Exception as e:
        print("Fetch error:", e)

# ================= BOT LOOP =================
async def bot_loop():
    global last_run_time, bot_running

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        print("🚀 BOT STARTED (BULLETPROOF MODE)")

        cycle = 0
        token = None

        while True:
            try:
                with lock:
                    last_run_time = time.time()
                    bot_running = True

                if cycle % 5 == 0:
                    token = await get_token(browser)

                cycle += 1

                if token:
                    fetch_jobs(token)
                else:
                    print("⚠️ Token failed")

                sleep_time = random.uniform(CHECK_INTERVAL_MIN, CHECK_INTERVAL_MAX)
                await asyncio.sleep(sleep_time)

            except Exception as e:
                print("🔥 Bot crash:", e)
                send_telegram(f"🚨 *Bot Crash*\n`{str(e)[:200]}`")
                await asyncio.sleep(5)

# ================= SAFE START =================
def start_bot():
    global bot_running

    with lock:
        if bot_running:
            return
        bot_running = True

    try:
        asyncio.run(bot_loop())
    finally:
        with lock:
            bot_running = False

# ================= WATCHDOG =================
def watchdog():
    global last_run_time, restart_timestamps

    while True:
        time.sleep(10)

        with lock:
            idle = time.time() - last_run_time

        if idle > BOT_TIMEOUT:
            now = time.time()
            restart_timestamps = [t for t in restart_timestamps if now - t < RESTART_WINDOW]

            if len(restart_timestamps) >= MAX_RESTARTS:
                send_telegram("🚨 *CRITICAL*\nToo many restarts. Check bot!")
                continue

            restart_timestamps.append(now)

            send_telegram("🚨 Bot stuck. Restarting...")
            print("🔄 Restarting bot...")

            threading.Thread(target=start_bot, daemon=True).start()

# ================= FLASK =================
@app.route("/")
def home():
    return "✅ Amazon Job Bot Running (Bulletproof Mode)"

@app.route("/force")
def force():
    return "⚡ Bot active in background"

# ================= MAIN =================
if __name__ == "__main__":
    threading.Thread(target=start_bot, daemon=True).start()
    threading.Thread(target=heartbeat, daemon=True).start()
    threading.Thread(target=watchdog, daemon=True).start()

    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
