import feedparser, tweepy, requests, json, os, random, hashlib
from bs4 import BeautifulSoup
from datetime import datetime

RSS_FEED = "https://www.amazon.in/gp/rss/deals"
AFF_TAG = "anm2-21"
POSTED_FILE = "posted.json"
COUNT_FILE = "daily_count.json"
SHORT_DIR = "go"

MAX_POSTS_PER_DAY = 24
MAX_LIGHTNING_PER_DAY = 8

def add_affiliate(url):
    return url + ("&" if "?" in url else "?") + f"tag={AFF_TAG}"

def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f)

def detect_bank_offers(text):
    offers = []
    t = text.lower()
    if "hdfc" in t: offers.append("HDFC")
    if "sbi" in t: offers.append("SBI")
    if "icici" in t: offers.append("ICICI")
    return " | ".join(offers)

def extract_data(url):
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")

    price = soup.select_one(".a-price-whole")
    mrp = soup.select_one(".a-text-price span")
    image = soup.select_one("#imgTagWrapperId img")

    text = soup.get_text()
    lightning = "lightning deal" in text.lower()

    return (
        price.text.replace(",", "") if price else None,
        mrp.text.replace("₹", "").replace(",", "") if mrp else None,
        image["src"] if image else None,
        detect_bank_offers(text),
        lightning
    )

def discount(price, mrp):
    try:
        p, m = float(price), float(mrp)
        off = int(m - p)
        return f"₹{off} OFF ({int(off/m*100)}%)"
    except:
        return ""

def hashtags(title):
    tags = ["#AmazonDeals", "#DealsIndia"]
    t = title.lower()
    if "mobile" in t: tags.append("#SmartphoneDeals")
    if "laptop" in t: tags.append("#LaptopDeals")
    return " ".join(tags[:4])

def shorten(url):
    os.makedirs(SHORT_DIR, exist_ok=True)
    slug = hashlib.md5(url.encode()).hexdigest()[:6]
    path = f"{SHORT_DIR}/{slug}.html"
    with open(path, "w") as f:
        f.write(f'<meta http-equiv="refresh" content="0;url={url}">')
    return f"https://thedesigner2802.github.io/{SHORT_DIR}/{slug}.html"

def main():
    posted = set(load_json(POSTED_FILE, {"posted": []})["posted"])
    counts = load_json(COUNT_FILE, {"date":"", "total":0, "lightning":0})
    today = datetime.utcnow().strftime("%Y-%m-%d")

    if counts["date"] != today:
        counts = {"date":today, "total":0, "lightning":0}

    if counts["total"] >= MAX_POSTS_PER_DAY:
        return

    feed = feedparser.parse(RSS_FEED)
    random.shuffle(feed.entries)

    lightning_deals, normal_deals = [], []

    for e in feed.entries:
        if e.link in posted: continue
        *_, lightning = extract_data(e.link)
        (lightning_deals if lightning else normal_deals).append(e)

    entry = None
    is_lightning = False

    if lightning_deals and counts["lightning"] < MAX_LIGHTNING_PER_DAY:
        entry = lightning_deals[0]
        is_lightning = True
    elif normal_deals:
        entry = normal_deals[0]

    if not entry: return

    price, mrp, img, bank, lightning = extract_data(entry.link)
    link = shorten(add_affiliate(entry.link))

    text = f"{'⚡ LIGHTNING DEAL ⚡\n' if lightning else ''}{entry.title[:160]}\n{discount(price,mrp)}\n{bank}\n👉 {link}\n{hashtags(entry.title)}"

    client = tweepy.Client(
        consumer_key=os.environ["X_KEY"],
        consumer_secret=os.environ["X_SECRET"],
        access_token=os.environ["X_AT"],
        access_token_secret=os.environ["X_ATS"]
    )

    if img:
        api = tweepy.API(tweepy.OAuth1UserHandler(
            os.environ["X_KEY"], os.environ["X_SECRET"],
            os.environ["X_AT"], os.environ["X_ATS"]
        ))
        open("img.jpg","wb").write(requests.get(img).content)
        media = api.media_upload("img.jpg")
        client.create_tweet(text=text, media_ids=[media.media_id])
    else:
        client.create_tweet(text=text)

    posted.add(entry.link)
    save_json(POSTED_FILE, {"posted": list(posted)})
    counts["total"] += 1
    if is_lightning: counts["lightning"] += 1
    save_json(COUNT_FILE, counts)

main()
