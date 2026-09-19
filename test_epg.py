import json
import re
import urllib.request
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

TIME_PATTERN_HM = re.compile(r"(\b[0-2]?\d[:.][0-5]\d\b)")

def clean_text_str(val):
    if not val: return ""
    text = str(val).replace("\xa0", " ")
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", " ", text).strip()
    return re.sub(r"\s+", " ", text)

def test_tivie_full_schedule():
    test_channels = ["antv", "btv", "rcti"]
    cf_worker_url = "https://tivie-proxy.sulthan-pamenan.workers.dev"
    wib_tz = timezone(timedelta(hours=7))
    today_wib = datetime.now(timezone.utc).astimezone(wib_tz).date()

    print(f"Memulai uji coba penarikan jadwal penuh Tivie.id via Proxy Worker...\n" + "-"*50)

    for ch_id in test_channels:
        url = f"{cf_worker_url}/channel/{ch_id}"
        print(f"Mengakses: {url}")
        
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'id,en-US;q=0.9,en-US;q=0.8',
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                if response.status == 200:
                    soup = BeautifulSoup(response.read().decode('utf-8'), 'html.parser')
                    
                    for unwanted in soup.select("footer, .footer, script, style, .ads, .cookie-banner"):
                        unwanted.decompose()

                    event_items = soup.select("li[id^='event-']")
                    if not event_items:
                        event_items = [li for li in soup.find_all("li") if TIME_PATTERN_HM.search(li.get_text())]

                    raw_list = []
                    for item in event_items:
                        full_text = item.get_text(" ", strip=True)
                        time_match = TIME_PATTERN_HM.search(full_text)
                        if not time_match:
                            continue
                        t_str = time_match.group(1).replace(".", ":").zfill(5)[:5]

                        cat_div = item.select_one("div.text-sm.tracking-wide")
                        cat_str = clean_text_str(cat_div.get_text()) if cat_div else ""

                        h_elem = item.select_one("h5, h4")
                        if h_elem:
                            h_clone = BeautifulSoup(str(h_elem), 'html.parser')
                            for sub in h_clone.select("div.text-sm.tracking-wide, span.sr-only"):
                                sub.decompose()
                            texts = [clean_text_str(t) for t in h_clone.stripped_strings if t not in ["WIB", "LIVE"]]
                            texts = [t for t in texts if t != cat_str]
                            prog_title = " ".join(texts) if texts else ""
                        else:
                            prog_title = ""

                        if not prog_title and cat_str:
                            prog_title = cat_str
                            cat_str = ""

                        if not prog_title:
                            continue

                        title = prog_title if not cat_str else f"{cat_str} {prog_title}"
                        if not any(p['time'] == t_str and p['title'] == title for p in raw_list):
                            raw_list.append({"time": t_str, "title": title})

                    print(f"[OK] Channel [{ch_id}]: Berhasil menarik {len(raw_list)} program jadwal penuh.")
                    for prog in raw_list[:5]:
                        print(f"   -> [{prog['time']}] {prog['title']}")
                    print("-" * 30)
                else:
                    print(f"[FAIL] Channel [{ch_id}]: HTTP Status {response.status}")
        except Exception as e:
            print(f"[FAIL] Channel [{ch_id}]: Error -> {e}")

if __name__ == "__main__":
    test_tivie_full_schedule()
