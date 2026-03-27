import requests
from bs4 import BeautifulSoup
import os
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
ADMIN_CHAT_ID = os.environ["ADMIN_CHAT_ID"]

# ── Customise these ────────────────────────────────────────────────────────────

# (location, distance_miles) — use None for no distance param
SEARCH_LOCATIONS = [
    ("London",      None),
    ("Sheffield",   25),
    ("Leeds",       25),
    ("Manchester",  25),
    ("Rotherham",   25),
    ("Nottingham",  25),
    ("Derby",       25),
    ("Doncaster",   25),
    ("Guildford",   25),
    ("Dorking",     25),
    ("Epsom",       25),
]

# A job matches if its title contains ANY of these strings (case-insensitive)
TARGET_TITLES = [
    "mental health support worker",
    "healthcare assistant",
    "health care assistant",     # split spelling
    "social worker",
    "rehabilitation assistant",
    "research assistant",
    "assistant psychologist",
]

# A job also matches if its employer field contains ANY of these (case-insensitive)
TARGET_EMPLOYERS = [
    "south west london and st georges mental",
    "sw17 0yf",
]

alerted_links = set()  # tracks links we've already sent an alert for

def clean_link(link):
    """Strip query string from a job link so _cb and other params don't cause duplicates."""
    return link.split("?")[0]

# ── Base URL builder ───────────────────────────────────────────────────────────

def build_urls():
    """Return one search URL per location (no keyword — filtered locally)."""
    urls = []
    for location, distance in SEARCH_LOCATIONS:
        url = (
            "https://beta.jobs.nhs.uk/candidate/search/results"
            f"?location={location.replace(' ', '+')}"
            "&searchFormType=sortBy"
            "&sort=publicationDateDesc"
            "&searchByLocationOnly=true"
            "&language=en"
        )
        if distance:
            url += f"&distance={distance}"
        urls.append((location, url))
    return urls

# ── Matching ───────────────────────────────────────────────────────────────────

def is_match(job):
    title_lower = job["title"].lower()
    employer_lower = job["employer"].lower()
    title_match = any(t in title_lower for t in TARGET_TITLES)
    employer_match = any(t in employer_lower for t in TARGET_EMPLOYERS)
    return title_match or employer_match

# ── Scraping ───────────────────────────────────────────────────────────────────

def fetch_page(base_url, page):
    url = f"{base_url}&page={page}&_cb={int(time.time())}"
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; job-alert-bot/1.0)",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    return r.text


def parse_jobs(html):
    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    for li in soup.select("li[data-test='search-result']"):
        title_el = li.select_one("a[data-test='search-result-job-title']")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        link = title_el.get("href", "")
        if not link.startswith("http"):
            link = "https://beta.jobs.nhs.uk" + link

        employer_el = li.select_one("div[data-test='search-result-location'] h3")
        employer = employer_el.get_text(separator=" ", strip=True) if employer_el else "Unknown"

        date_el = li.select_one("li[data-test='search-result-publicationDate'] strong")
        date_posted = date_el.get_text(strip=True) if date_el else "Unknown"

        closing_el = li.select_one("li[data-test='search-result-closingDate'] strong")
        closing = closing_el.get_text(strip=True) if closing_el else "Unknown"

        salary_el = li.select_one("li[data-test='search-result-salary'] strong")
        salary = salary_el.get_text(strip=True) if salary_el else "Unknown"

        jobs.append({
            "title": title,
            "employer": employer,
            "date_posted": date_posted,
            "closing": closing,
            "salary": salary,
            "link": link,
        })

    return jobs


def get_todays_jobs_for_location(base_url, location, today_str):
    todays_jobs = []
    page = 1

    while True:
        print(f"  [{location}] Fetching page {page}...")
        html = fetch_page(base_url, page)
        jobs = parse_jobs(html)
        time.sleep(0.1)
        if not jobs:
            print(f"  [{location}] No jobs on page {page}, stopping.")
            break

        for i, job in enumerate(jobs, 1):
            print(f"    {i}. {job['title']} | {job['employer']} | Posted: {job['date_posted']}")

        hit_old = False
        for job in jobs:
            if job["date_posted"] == today_str:
                todays_jobs.append({**job, "search_location": location})
            else:
                hit_old = True
                break

        if hit_old:
            print(f"  [{location}] Hit older job, stopping pagination.")
            break

        page += 1
        time.sleep(0.9)

    return todays_jobs


def get_all_todays_jobs(today_str):
    all_jobs = []
    seen_links = set()

    for location, url in build_urls():
        jobs = get_todays_jobs_for_location(url, location, today_str)
        for job in jobs:
            job["link"] = clean_link(job["link"])
            if job["link"] not in seen_links:
                seen_links.add(job["link"])
                all_jobs.append(job)
        time.sleep(2)

    return all_jobs

# ── Telegram ───────────────────────────────────────────────────────────────────

def send_telegram(msg, chat_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(url, json={"chat_id": chat_id, "text": msg}, timeout=10)
    print(f"  Telegram response ({chat_id}): {resp.status_code} {resp.text}")
    return resp

def alert(msg):
    send_telegram(msg, CHAT_ID)
    send_telegram(msg, ADMIN_CHAT_ID)

def log(msg):
    send_telegram(msg, ADMIN_CHAT_ID)

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    now = datetime.now()
    current_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
    today_str = now.strftime("%-d %B %Y")

    print(f"\n========================================================")
    print(f"[{current_time_str}] Checking NHS Jobs...")
    print(f"Looking for target date : {today_str}")
    print(f"Locations : {', '.join(loc for loc, _ in SEARCH_LOCATIONS)}")
    print(f"Titles    : {', '.join(TARGET_TITLES)}")
    print(f"========================================================\n")

    # NEW: Pass today_str into the scraper
    todays_jobs = get_all_todays_jobs(today_str)

    print(f"\n--- Jobs posted TODAY ({today_str}): {len(todays_jobs)} ---\n")

    matched = [j for j in todays_jobs if is_match(j)]
    print(f"--- Matched jobs to alert: {len(matched)} ---\n")

    new_matched = [j for j in matched if j["link"] not in alerted_links]

    if new_matched:
        alert(f"🔍 Found {len(new_matched)} job alert(s) on NHS Jobs today!")
        for job in new_matched:
            print(f"  Alerting: {job['title']} | {job['employer']} ({job['search_location']})")
            msg = (
                f"🚨 NHS Job Alert!\n\n"
                f"{job['title']}\n"
                f"📍 Search area: {job['search_location']}\n"
                f"🏥 {job['employer']}\n"
                f"💰 {job['salary']}\n"
                f"📅 Closes: {job['closing']}\n"
                f"🔗 {job['link']}"
            )
            alert(msg)
            alerted_links.add(job["link"])
    else:
        print("No matching jobs today.")
        log("✅ NHS checker ran - no matching jobs today.")


if __name__ == "__main__":
    while True:
        try:
            main()
        except Exception as e:
            print(f"❌ An unexpected error occurred: {e}")
            log(f"⚠️ NHS Scraper encountered an error: {e}")
            
        print("Sleeping for 15 minutes...")
        time.sleep(900)