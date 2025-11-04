from flask import Flask
from playwright.sync_api import sync_playwright
import threading
import time

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Amazon Job Bot is running on Render!"

# ------------- Bot Settings -------------
LOCATION = "Sheffield"
WAIT_TIME_MS = 5000
REFRESH_INTERVAL = 3600
printed_job_ids = set()

# ------------- Job Fetch Function -------------
def fetch_jobs():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        graphql_responses = []

        def handle_response(response):
            if "graphql" in response.url and response.status == 200:
                try:
                    data = response.json()
                    graphql_responses.append(data)
                except:
                    pass

        page.on("response", handle_response)
        page.goto(f"https://www.jobsatamazon.co.uk/search?location={LOCATION.lower()}")
        page.wait_for_timeout(WAIT_TIME_MS)
        browser.close()

        jobs_list = []
        for r in graphql_responses:
            if "data" in r and "searchJobCardsByLocation" in r["data"]:
                job_cards = r["data"]["searchJobCardsByLocation"].get("jobCards", [])
                jobs_list.extend(job_cards)

        return jobs_list

# ------------- Background Job Loop -------------
def job_loop():
    while True:
        try:
            jobs = fetch_jobs()
            new_jobs = []

            for job in jobs:
                job_id = f"{job.get('jobTitle')}_{job.get('city')}"
                if job_id not in printed_job_ids:
                    new_jobs.append(job)
                    printed_job_ids.add(job_id)

            if new_jobs:
                print(f"\n📢 Found {len(new_jobs)} new jobs in {LOCATION}:")
                for job in new_jobs:
                    print(f"- {job.get('jobTitle')} | {job.get('city')} | {job.get('jobType')}")
            else:
                print("No new jobs found.")

        except Exception as e:
            print("⚠️ Error:", e)

        time.sleep(REFRESH_INTERVAL)

# ------------- Run Flask + Bot Thread -------------
if __name__ == "__main__":
    threading.Thread(target=job_loop, daemon=True).start()
    import os
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)