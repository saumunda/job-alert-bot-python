import os
import time
import datetime
import random
import threading
import asyncio
import requests
from playwright.async_api import async_playwright

# === CONFIG ===
GRAPHQL_URL = "https://qy64m4juabaffl7tjakii4gdoa.appsync-api.eu-west-1.amazonaws.com/graphql"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_IDS = [chat.strip() for chat in os.getenv("TELEGRAM_CHAT_IDS", "").split(",") if chat.strip()]

CHECK_INTERVAL = 5  # ⚡ FAST (5 sec)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
]

seen_jobs = set()

# === TELEGRAM ===
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

# === GET TOKEN (FAST VERSION) ===
async def get_token(browser):
    try:
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS)
        )

        page = await context.new_page()

        # 🚀 Block heavy resources
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

# === FETCH JOBS ===
def fetch_jobs(token):
    headers = {
        "Authorization": token,
        "Content-Type": "application/json",
        "User-Agent": random.choice(USER_AGENTS)
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
        "query": "query searchJobCardsByLocation($searchJobRequest: SearchJobRequest!) { searchJobCardsByLocation(searchJobRequest: $searchJobRequest) { jobCards { jobId jobTitle city state totalPayRateMax } } }"
    }

    try:
        res = requests.post(GRAPHQL_URL, headers=headers, json=payload, timeout=10)
        data = res.json()

        jobs = data.get("data", {}).get("searchJobCardsByLocation", {}).get("jobCards", [])

        print(f"📦 {len(jobs)} jobs")

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

# === MAIN LOOP ===
async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        print("🚀 FAST BOT STARTED")

        while True:
            start = time.time()

            token = await get_token(browser)

            if token:
                fetch_jobs(token)
            else:
                print("⚠️ Token failed")

            elapsed = time.time() - start
            sleep_time = max(1, CHECK_INTERVAL - elapsed)

            print(f"⏱ {round(elapsed,2)}s cycle | sleep {round(sleep_time,2)}s")

            await asyncio.sleep(sleep_time)

# === RUN ===
if __name__ == "__main__":
    asyncio.run(main())
