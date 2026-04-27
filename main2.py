import os
import time
import threading
import requests
from playwright.sync_api import sync_playwright

# ================= CONFIG =================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_IDS = os.getenv("TELEGRAM_CHAT_IDS", "")
CHAT_IDS = [chat.strip() for chat in CHAT_IDS.split(",") if chat.strip()]

URLS = [
    "https://qy64m4juabaffl7tjakii4gdoa.appsync-api.eu-west-1.amazonaws.com/graphql",
    "https://www.jobsatamazon.co.uk/app#/jobSearch?query=Warehouse%20Operative&locale=en-GB" # replace
]

CHECK_INTERVAL = 5  # seconds (fast but safe)

# =========================================

seen_results = set()

def send_telegram(message):
    for chat_id in CHAT_IDS:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                data={"chat_id": chat_id, "text": message}
            )
        except Exception as e:
            print(f"Telegram error: {e}")

def check_page(browser, url):
    global seen_results

    try:
        context = browser.new_context()
        page = context.new_page()

        # 🚀 Block heavy resources (speed boost)
        page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "stylesheet", "font"] else route.continue_())

        page.goto(url, timeout=30000)

        content = page.content()

        # 🔍 Simple detection logic (customize this)
        if "No jobs found" not in content:
            if url not in seen_results:
                seen_results.add(url)
                print(f"🔥 New job found: {url}")
                send_telegram(f"🚨 Amazon Job Alert!\n{url}")

        context.close()

    except Exception as e:
        print(f"Error checking {url}: {e}")

def run_parallel(browser, urls):
    threads = []

    for url in urls:
        t = threading.Thread(target=check_page, args=(browser, url))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

def job_loop():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        print("🚀 Bot started (FAST MODE)")

        while True:
            start = time.time()

            run_parallel(browser, URLS)

            elapsed = time.time() - start
            sleep_time = max(1, CHECK_INTERVAL - elapsed)

            print(f"⏱ Cycle done in {round(elapsed,2)}s | sleeping {round(sleep_time,2)}s")

            time.sleep(sleep_time)

# ================= RUN =================
if __name__ == "__main__":
    job_loop()
