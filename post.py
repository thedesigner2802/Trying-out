import requests
import tweepy
import json
import os
import hashlib
from bs4 import BeautifulSoup
from datetime import datetime

# ---------------- CONFIG ----------------

AFF_TAG = "anm2-21"
GITHUB_USERNAME = "YOUR_GITHUB_USERNAME"  # CHANGE THIS

POSTED_FILE = "posted.json"
COUNT_FILE = "daily_count.json"
PRICES_FILE = "prices.json"
SHORT_DIR = "go"

MAX_POSTS_PER_DAY = 24
MAX_LIGHTNING_PER_DAY = 8

# Category rotation (one per hour)
CATEGORIES = [
    {
        "name": "Mobiles",
        "url": "https://www.amazon.in/deals?i=electronics&ref=nav_cs_gb"
    },
    {
        "name": "Laptops",
        "url": "https://www.amazon.in/deals?i=computers&ref=nav_cs_gb"
    },
    {
        "name": "Headphones",
        "url": "https://www.amazon.in/deals?i=electronics&ref=nav_cs_gb"
    },
    {
        "name": "TV",
        "url": "https://www.amazon.in/deals?i=electronics&ref=nav_cs_gb"
    },
    {
        "name": "Appliances",
        "url": "https://www.amazon.in/deals?i=kitchen&ref=nav_cs_gb"
    }
]

HEADERS = {"User-Agent": "Mozilla/5.0"}

# ---------------- UTILITIES ----------------

def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f)

def add_affiliate(url):
    return url + ("&" if "?" in url else "?") + f"tag={AFF_TAG}"

def shorten(url):
    os.makedirs(SHORT_DIR, exist_ok=True)
    slug = hashlib.md5(url.encode()).hexdigest()[:6]
    path = f"{SHORT_DIR}/{slug}.html"
    with open(path, "w") as f:
        f.write(f'<meta http-equiv="refresh" content="0;url={url}">')
    return f"https://{thedesigner2802}.github.io/{SHORT_DIR}/{slug}.html"

# ---------------- SCRAPING ----------------

def extract_product_links(category_url, limit=15):
    r = requests.get(category_url, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")

    links = []
    for a in soup.select("a[href*='/dp/']"):
        href = a.get("href")
        if "/dp/" in href:
            link = "https://www.amazon.in" + href.split("?")[0]
            if link not in links:
                links.append(link)
        if len(links) >= limit:
            break

    return links

def extract_product_data(url):
    r = requests.get(url, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")
    text = soup.get_text().lower()

    price = soup.select_one(".a-price-whole")
    mrp = soup.select_one(".a-text-price span")
    image = soup.select_one("#imgTagWrapperId img")

    lightning = "lightning deal" in text

    bank = []
    if "hdfc" in text: bank.append("HDFC")
    if "sbi" in text: bank.append("SBI")
    if "icici" in text: bank.append("ICICI")

    asin = url.split("/dp/")[1].split("/")[0]

    return {
        "asin": asin,
        "price": int(price.text.replace(",", "")) if price else None,
        "mrp": int(mrp.text.replace("₹", "").replace(",", "")) if mrp else None,
        "image": image["src"] if image else None,
        "lightning": lightning,
        "bank": " | ".join(bank)
    }

# ---------------- MAIN ----------------

def main():
    posted = set(load_json(POSTED_FILE, {"posted": []})["posted"])
    prices = load_json(PRICES_FILE, {})
    counts = load_json(COUNT_FILE, {"date": "", "total": 0, "lightning": 0})

    today = datetime.utcnow().strftime("%Y-%m-%d")
    if counts["date"] != today:
        counts = {"date": today, "total": 0, "lightning": 0}

    if counts["total"] >= MAX_POSTS_PER_DAY:
        return

    # Rotate category by hour
    hour = datetime.utcnow().hour
    category = CATEGORIES[hour % len(CATEGORIES)]

    product_links = extract_product_links(category["url"])

    for link in product_links:
        data = extract_product_data(link)
        asin = data["asin"]

        if not data["price"]:
            continue

        prev_price = prices.get(asin, {}).get("price")
        prices[asin] = {
            "price": data["price"],
            "category": category["name"],
            "seen": today
        }

        should_post = False

        if data["lightning"] and counts["lightning"] < MAX_LIGHTNING_PER_DAY:
            should_post = True
        elif prev_price and data["price"] < prev_price:
            should_post = True

        if not should_post or asin in posted:
            continue

        text = (
            ("⚡ LIGHTNING DEAL ⚡\n" if data["lightning"] else "📉 PRICE DROP\n") +
            f"{category['name']} Deal\n"
            f"₹{data['price']}\n"
            f"{data['bank']}\n"
            f"👉 {shorten(add_affiliate(link))}\n"
            "#DealsHubIN #AmazonDeals #PriceDrop"
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
            open("img.jpg", "wb").write(requests.get(data["image"]).content)
            media = api.media_upload("img.jpg")
            client.create_tweet(text=text, media_ids=[media.media_id])
        else:
            client.create_tweet(text=text)

        posted.add(asin)
        counts["total"] += 1
        if data["lightning"]:
            counts["lightning"] += 1

        save_json(POSTED_FILE, {"posted": list(posted)})
        save_json(PRICES_FILE, prices)
        save_json(COUNT_FILE, counts)
        break

if __name__ == "__main__":
    main()
