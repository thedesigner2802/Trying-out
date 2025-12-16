import feedparser
import tweepy
import requests
import json
import os
import random
import hashlib
from bs4 import BeautifulSoup
from datetime import datetime

# ---------------- CONFIG ----------------

RSS_FEED = "https://www.amazon.in/gp/rss/deals"
AFF_TAG = "anm2-21"

POSTED_FILE = "posted.json"
COUNT_FILE = "daily_count.json"
SHORT_DIR = "go"

MAX_POSTS_PER_DAY = 24
MAX_LIGHTNING_PER_DAY = 8

GITHUB_USERNAME = "YOUR_GITHUB_USERNAME"  # <-- CHANGE THIS

# ---------------- HELPERS ----------------

def add_affiliate(url):
    return url + ("&" if "?" in url else "?") + f"tag={AFF_TAG}"

def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f)

def shorten_url(long_url):
    os.makedirs(SHORT_DIR, exist_ok=True)
    slug = hashlib.md5(long_url.encode()).hexdigest()[:6]
    file_path = f"{SHORT_DIR}/{slug}.html"

    with open(file_path, "w") as f:
        f.write(f'<meta http-equiv="refresh" content="0;url={long_url}">')

    return f"https://{thedesigner2802}.github.io/{SHORT_DIR}/{slug}.html"

def detect_bank_offers(text):
    text = text.lower()
    offers = []
    if "hdfc" in text:
        offers.append("HDFC Bank Offer")
    if "sbi" in text:
        offers.append("SBI Bank Offer")
    if "icici" in text:
        offers.append("ICICI Bank Offer")
    return " | ".join(offers)

def extract_product_data(url):
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")
    text = soup.get_text()

    price = soup.select_one(".a-price-whole")
    mrp = soup.select_one(".a-text-price span")
    image = soup.select_one("#imgTagWrapperId img")

    is_lightning = "lightning deal" in text.lower()

    return {
        "price": price.text.replace(",", "") if price else None,
        "mrp": mrp.text.replace("₹", "").replace(",", "") if mrp else None,
        "image": image["src"] if image else None,
        "bank": detect_bank_offers(text),
        "lightning": is_lightning
    }

def calc_discount(price, mrp):
    try:
        p = float(price)
        m = float(mrp)
        off = int(m - p)
        percent = int((off / m) * 100)
        return f"₹{off} OFF ({percent}% OFF)"
    except:
        return ""

def generate_hashtags(title):
    tags = ["#AmazonDeals", "#DealsIndia"]
    t = title.lower()
    if "mobile" in t or "phone" in t:
        tags.append("#SmartphoneDeals")
    if "laptop" in t:
        tags.append("#LaptopDeals")
    if "headphone" in t or "earbud" in t:
        tags.append("#AudioDeals")
    return " ".join(tags[:4])

# ---------------- MAIN ----------------

def main():
    posted = set(load_json(POSTED_FILE, {"posted": []})["posted"])
    counts = load_json(COUNT_FILE, {"date": "", "total": 0, "lightning": 0})

    today = datetime.utcnow().strftime("%Y-%m-%d")
    if counts["date"] != today:
        counts = {"date": today, "total": 0, "lightning": 0}

    if counts["total"] >= MAX_POSTS_PER_DAY:
        print("Daily limit reached")
        return

    feed = feedparser.parse(RSS_FEED)
    random.shuffle(feed.entries)

    lightning_deals = []
    normal_deals = []

    for entry in feed.entries:
        if entry.link in posted:
            continue

        data = extract_product_data(entry.link)
        if data["lightning"]:
            lightning_deals.append((entry, data))
        else:
            normal_deals.append((entry, data))

    selected = None
    is_lightning = False

    if lightning_deals and counts["lightning"] < MAX_LIGHTNING_PER_DAY:
        selected, data = lightning_deals[0]
        is_lightning = True
    elif normal_deals:
        selected, data = normal_deals[0]

    if not selected:
        print("No eligible deals found")
        return

    short_link = shorten_url(add_affiliate(selected.link))
    discount = calc_discount(data["price"], data["mrp"])
    hashtags = generate_hashtags(selected.title)

    lightning_text = "⚡ LIGHTNING DEAL ⚡\n" if is_lightning else ""

    tweet_text = (
        lightning_text +
        f"{selected.title[:160]}\n"
        f"{discount}\n"
        f"{data['bank']}\n"
        f"👉 {short_link}\n"
        f"{hashtags}"
    )

    client = tweepy.Client(
        consumer_key=os.environ["X_KEY"],
        consumer_secret=os.environ["X_SECRET"],
        access_token=os.environ["X_AT"],
        access_token_secret=os.environ["X_ATS"]
    )

    if data["image"]:
        api = tweepy.API(
            tweepy.OAuth1UserHandler(
                os.environ["X_KEY"],
                os.environ["X_SECRET"],
                os.environ["X_AT"],
                os.environ["X_ATS"]
            )
        )
        with open("img.jpg", "wb") as f:
            f.write(requests.get(data["image"]).content)

        media = api.media_upload("img.jpg")
        client.create_tweet(text=tweet_text, media_ids=[media.media_id])
    else:
        client.create_tweet(text=tweet_text)

    posted.add(selected.link)
    save_json(POSTED_FILE, {"posted": list(posted)})

    counts["total"] += 1
    if is_lightning:
        counts["lightning"] += 1

    save_json(COUNT_FILE, counts)
    print("Tweet posted successfully")

# ---------------- RUN ----------------

if __name__ == "__main__":
    main()
