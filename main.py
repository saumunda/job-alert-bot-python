import os
import time
import random
import asyncio
import threading
import requests
from flask import Flask
from playwright.async_api import async_playwright

# ================= CONFIG =================
GRAPHQL_URL = "https://qy64m4juabaffl7tjakii4gdoa.appsync-api.eu-west-1.amazonaws.com/graphql"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_IDS = [chat.strip() for chat in os.getenv("TELEGRAM_CHAT_IDS", "").split(",") if chat.strip()]

CHECK_INTERVAL_MIN = 4
CHECK_INTERVAL_MAX = 7

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/132.0",
]

seen_jobs = set()
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

# ================= TOKEN =================
async def get_token(browser):
    try:
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS)
        )

        page = await context.new_page()

        # ⚡ Block heavy resources
        await page.route("**/*", lambda route: asyncio.create_task(
            route.abort() if route.request.resource_type in ["image", "stylesheet", "font"] else route.continue_()
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
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        print("🚀 BOT STARTED (WEB MODE)")

        cycle = 0

        while True:
            start = time.time()

            # refresh token every 5 cycles
            if cycle % 5 == 0:
                token = await get_token(browser)
            cycle += 1

            if token:
                fetch_jobs(token)
            else:
                print("⚠️ Token failed")

            elapsed = time.time() - start
            sleep_time = random.uniform(CHECK_INTERVAL_MIN, CHECK_INTERVAL_MAX)

            print(f"⏱ {round(elapsed,2)}s | sleep {round(sleep_time,2)}s")

            await asyncio.sleep(sleep_time)

# ================= THREAD START =================
def start_bot():
    asyncio.run(bot_loop())

# ================= FLASK ROUTES =================
@app.route("/")
def home():
    return "✅ Amazon Job Bot Running (Fast Mode)"

@app.route("/force")
def force():
    return "⚡ Bot is running in background"

# ================= MAIN =================
if __name__ == "__main__":
    threading.Thread(target=start_bot, daemon=True).start()

    # REQUIRED for Render Web Service
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
