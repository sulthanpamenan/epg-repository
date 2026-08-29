import json
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from bs4 import BeautifulSoup
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
}

TIME_PATTERN_HM = re.compile(r"(\b[0-2]?\d[:.][0-5]\d\b)")
TIME_PATTERN_AMPM = re.compile(r"(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))", re.IGNORECASE)

IGNORE_WORDS_KZ = {
    "LIVE", "ЭФИРДЕ", "Бағдарлама", "Драма", "Көркем фильм", "Телехикая", 
    "Шоу", "Онлайн көру", "Онлайн қарау", "ҚАЗІР ЭФИРДЕ", "ЖАҢA", 
    "ТІКЕЛЕЙ", "ТІКЕЛЕЙ ЭФИР", "LIVE NOW", "СЕГОДНЯ", "ТАҢҒЫ", "ТҮСКІ", "КЕШКІ",
}

EPG_TARGET_SOURCES = [
    # 1. TP CHANNEL THAILAND
    {"id": "TPChannel.th", "name": "TP Channel", "url": "https://www.tpchannel.org/tv/schedule", "utc_offset": "+0700"},

    # 2. RED BULL TV CHANNELS
    {"id": "RedBullTV.global", "name": "Red Bull TV: World of Red Bull", "rrn": "rrn:content:video-channels:c81f8686-ab67-4965-ba04-5f6658bb96cc", "utc_offset": "+0000"},
    {"id": "RedBullPadel.global", "name": "Red Bull TV: Padel", "rrn": "rrn:content:video-channels:e0e6dee0-8c39-4de1-9488-72828468efe0", "utc_offset": "+0000"},
    {"id": "RedBullBike.global", "name": "Red Bull TV: Bike", "rrn": "rrn:content:video-channels:ee30c528-32b1-4604-8976-e3bcee4ae7f0", "utc_offset": "+0000"},
    {"id": "RedBullAdventure.global", "name": "Red Bull TV: Adventure", "rrn": "rrn:content:video-channels:870bcfa8-62b1-4e84-9c85-39f083df368a", "utc_offset": "+0000"},
    {"id": "RedBullMotorsports.global", "name": "Red Bull TV: Motorsports", "rrn": "rrn:content:video-channels:fd4ed3c9-1800-477b-9909-53255da06632", "utc_offset": "+0000"},
    {"id": "RedBullSurfing.global", "name": "Red Bull TV: Surfing", "rrn": "rrn:content:video-channels:2f6afaec-7ade-4fb8-961a-a51aa8279a99", "utc_offset": "+0000"},
    {"id": "RedBullSkateboarding.global", "name": "Red Bull TV: Skateboarding", "rrn": "rrn:content:video-channels:5021f46c-6f34-4f51-ba1f-967f2885ac97", "utc_offset": "+0000"},
    {"id": "RedBullWinter.global", "name": "Red Bull TV: Winter", "rrn": "rrn:content:video-channels:f4aa4fe4-5ce6-4b1c-a60b-abc6f21f16d0", "utc_offset": "+0000"},
    {"id": "RedBullActionReel.global", "name": "Red Bull TV: Action Reel", "rrn": "rrn:content:video-channels:69a66f02-21fd-42a1-be5b-6965541cfe6a", "utc_offset": "+0000"},

    # 3. CLTV36 FILIPINA
    {"id": "CLTV36.ph", "name": "CLTV36", "url": "https://cltv36.tv/tv-programs/", "utc_offset": "+0800"},

    # 4. QAZAQSTAN NETWORK
    {"id": "Qazaqstan.kz", "name": "Qazaqstan TV", "url": "https://qazaqstan.tv/program", "utc_offset": "+0500"},
    {"id": "QazaqstanInt.kz", "name": "Qazaqstan International", "url": "https://qazaqstan.tv/program", "utc_offset": "+0500"},
    {"id": "Balapan.kz", "name": "Balapan TV", "url": "https://balapan.tv/program", "utc_offset": "+0500"},
    {"id": "AbaiTV.kz", "name": "Abai TV", "url": "https://abaitv.kz/kz/program", "utc_offset": "+0500"},
    {"id": "Qazsport.kz", "name": "Qazsport", "url": "https://qazsporttv.kz/kz/program", "utc_offset": "+0500"},
    {"id": "AqjaiyqTV.kz", "name": "Aqjaiyq TV", "url": "https://aqjaiyqtv.kz/kz/program", "utc_offset": "+0500"},
    {"id": "AqtobeTV.kz", "name": "Aqtobe TV", "url": "https://aqtobetv.kz/kz/program", "utc_offset": "+0500"},
    {"id": "AltaiTV.kz", "name": "Altai TV", "url": "https://altaitv.kz/kz/program", "utc_offset": "+0500"},
    {"id": "AtyrauTV.kz", "name": "Atyrau TV", "url": "https://atyrautv.kz/kz/program", "utc_offset": "+0500"},
    {"id": "ErtisTV.kz", "name": "Ertis TV", "url": "https://ertistv.kz/kz/program", "utc_offset": "+0500"},
    {"id": "JambylTV.kz", "name": "Jambyl TV", "url": "https://jambyltv.kz/kz/program", "utc_offset": "+0500"},
    {"id": "KoksheTV.kz", "name": "Kokshe TV", "url": "https://kokshetv.kz/kz/program", "utc_offset": "+0500"},
    {"id": "MangystauTV.kz", "name": "Mangystau TV", "url": "https://mangystautv.kz/kz/program", "utc_offset": "+0500"},
    {"id": "OntustikTV.kz", "name": "Ontustik TV", "url": "https://ontustiktv.kz/kz/program", "utc_offset": "+0500"},
    {"id": "QostanaiTV.kz", "name": "Qostanai TV", "url": "https://qostanaitv.kz/kz/program", "utc_offset": "+0500"},
    {"id": "QyzyljarTV.kz", "name": "Qyzyljar TV", "url": "https://qyzyljartv.kz/kz/program", "utc_offset": "+0500"},
    {"id": "QyzylordaTV.kz", "name": "Qyzylorda TV", "url": "https://qyzylordatv.kz/kz/program", "utc_offset": "+0500"},
    {"id": "SaryarqaTV.kz", "name": "Saryarqa TV", "url": "https://saryarqatv.kz/kz/program", "utc_offset": "+0500"},
    {"id": "SemeiTV.kz", "name": "Semei TV", "url": "https://semeitv.kz/kz/program", "utc_offset": "+0500"},
]

HTTP_SESSION = requests.Session()
HTTP_SESSION.headers.update(HEADERS)

def format_xmltv_date(dt_obj, utc_offset="+0700"):
    return dt_obj.strftime(f"%Y%m%d%H%M%S {utc_offset}")

def get_now_in_channel_tz(offset_str):
    sign = -1 if offset_str[0] == "-" else 1
    hours = int(offset_str[1:3])
    return datetime.now(timezone.utc) + timedelta(hours=sign * hours)

def clean_text_str(val):
    if not val: 
        return ""
    return re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", str(val)).strip()

def parse_cltv36_day_matches(day_text, target_weekday_name, is_weekend):
    dt, t_day = day_text.upper(), target_weekday_name.upper()
    if t_day in dt or "DAILY" in dt: 
        return True
    if ("MONDAY - FRIDAY" in dt or "MON - FRI" in dt or "MONDAY – FRIDAY" in dt) and not is_weekend: 
        return True
    if ("MONDAY - SATURDAY" in dt or "MONDAY – SATURDAY" in dt) and t_day != "SUNDAY": 
        return True
    return False

# --- 1. TP CHANNEL ---
def fetch_epg_tpchannel(target):
    epg_id, offset = target["id"], target.get("utc_offset", "+0700")
    channels = [{"id": epg_id, "name": target["name"], "icon": target.get("icon", "")}]
    programmes = []
    
    today_local = get_now_in_channel_tz(offset)
    thai_year = today_local.year + 543
    date_param = f"{thai_year}-{today_local.strftime('%m-%d')}"
    today_str = today_local.strftime("%Y-%m-%d")

    api_url = f"https://www.tpchannel.org/tv/schedule/get-by-date?master_type_id=2&date={date_param}"
    
    try:
        res = HTTP_SESSION.get(api_url, headers={"X-Requested-With": "XMLHttpRequest", "Referer": target["url"]}, timeout=12)
        if res.status_code == 200:
            data = res.json()
            items = data if isinstance(data, list) else data.get("data", []) or data.get("result", [])
            extracted = []
            
            for item in items:
                t_raw = item.get("time") or item.get("start_time")
                title = item.get("title") or item.get("program_name")
                if t_raw and title:
                    match = TIME_PATTERN_HM.search(str(t_raw))
                    if match:
                        extracted.append((match.group(1).replace(".", ":").zfill(5)[:5], clean_text_str(title)))

            for i in range(len(extracted)):
                t_str, title = extracted[i]
                try:
                    start_dt = datetime.strptime(f"{today_str} {t_str}", "%Y-%m-%d %H:%M")
                    if i + 1 < len(extracted):
                        stop_dt = datetime.strptime(f"{today_str} {extracted[i+1][0]}", "%Y-%m-%d %H:%M")
                        if stop_dt <= start_dt: 
                            stop_dt += timedelta(days=1)
                    else:
                        stop_dt = start_dt + timedelta(hours=1)

                    programmes.append({"channel": epg_id, "start": format_xmltv_date(start_dt, offset), "stop": format_xmltv_date(stop_dt, offset), "title": title, "desc": f"Watch {title}", "lang": "th"})
                except Exception: 
                    continue
            print(f"[✓] TP Channel: Successfully loaded {len(programmes)} program!")
    except Exception as e:
        print(f"[!] TP Channel Error: {e}")
    return channels, programmes

# --- 2. CLTV36 ---
def fetch_epg_cltv36(target):
    epg_id, offset = target["id"], target.get("utc_offset", "+0800")
    channels = [{"id": epg_id, "name": target["name"], "icon": target.get("icon", "")}]
    programmes = []
    
    today_local = get_now_in_channel_tz(offset)
    today_name, today_str, is_weekend = today_local.strftime("%A"), today_local.strftime("%Y-%m-%d"), today_local.weekday() >= 5

    try:
        res = HTTP_SESSION.get(target["url"], timeout=15)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            retired_heading = soup.find(lambda tag: tag.name in ["h2", "h3"] and "RETIRED" in tag.get_text().upper())
            wrappers = soup.select(".elementor-widget-wrap.elementor-element-populated")

            for wrap in wrappers:
                if retired_heading and retired_heading in wrap.parents: 
                    continue
                h2_tag = wrap.find(["h2", "h3"], class_="elementor-heading-title")
                if not h2_tag: 
                    continue
                
                title = clean_text_str(h2_tag.get_text(strip=True))
                if "RETIRED" in title.upper(): 
                    continue

                desc_text = f"Watch {title} on CLTV36."
                for p in wrap.find_all("p"):
                    p_str = p.get_text(strip=True)
                    if p_str and not TIME_PATTERN_AMPM.search(p_str) and "NN" not in p_str and len(p_str) > 15:
                        desc_text = clean_text_str(p_str)
                        break

                for line in wrap.get_text("\n", strip=True).split("\n"):
                    line_clean = line.replace("NN", "PM").replace("nn", "pm")
                    if not parse_cltv36_day_matches(line_clean, today_name, is_weekend): 
                        continue
                    
                    time_matches = TIME_PATTERN_AMPM.findall(line_clean)
                    for idx in range(0, len(time_matches) - 1, 2):
                        try:
                            start_str = time_matches[idx].upper().replace(" ", "")
                            stop_str = time_matches[idx + 1].upper().replace(" ", "")
                            start_time = datetime.strptime(start_str.zfill(7), "%I:%M%p").time()
                            stop_time = datetime.strptime(stop_str.zfill(7), "%I:%M%p").time()
                            
                            start_dt, stop_dt = datetime.combine(today_local.date(), start_time), datetime.combine(today_local.date(), stop_time)
                            if stop_dt <= start_dt: 
                                stop_dt += timedelta(days=1)

                            programmes.append({"channel": epg_id, "start": format_xmltv_date(start_dt, offset), "stop": format_xmltv_date(stop_dt, offset), "title": title, "desc": desc_text, "lang": "en"})
                        except Exception: 
                            continue
            print(f"[✓] CLTV36: Successfully loaded {len(programmes)} program!")
    except Exception as e:
        print(f"[!] CLTV36 Error: {e}")
    return channels, programmes

# --- 3. MNC VISION ---
def fetch_epg_mncvision_code(mnc_code):
    today_str = get_now_in_channel_tz("+0700").strftime("%Y-%m-%d")
    post_url = "https://www.mncvision.id/schedule/table"

    payload = {
        "search_model": "channel",
        "af0rmelement": "aformelement",
        "fdate": today_str,
        "fchannel": str(mnc_code),
        "submit": "Cari"
    }

    mnc_headers = {
        "User-Agent": HEADERS["User-Agent"],
        "Origin": "https://www.mncvision.id",
        "Referer": "https://www.mncvision.id/schedule/table",
    }

    try:
        res = HTTP_SESSION.post(post_url, data=payload, headers=mnc_headers, timeout=12)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            table = soup.find("table", class_=re.compile(r"table", re.I)) or soup.find("table")
            
            if table:
                rows = table.find_all("tr")[1:]
                raw_list = []
                
                for row in rows:
                    cols = row.find_all(["td", "th"])
                    if len(cols) >= 2:
                        time_str, title_str = cols[0].get_text(strip=True), cols[1].get_text(strip=True)
                        if time_str and title_str:
                            raw_list.append((time_str.replace(".", ":").zfill(5)[:5], clean_text_str(title_str)))

                if raw_list:
                    ch_id = f"MNC_{mnc_code}.id"
                    ch_name = f"MNC Channel {mnc_code}"
                    
                    channels = [{"id": ch_id, "name": ch_name}]
                    programmes = []

                    for i in range(len(raw_list)):
                        t_str, title = raw_list[i]
                        try:
                            start_dt = datetime.strptime(f"{today_str} {t_str}", "%Y-%m-%d %H:%M")
                            if i + 1 < len(raw_list):
                                stop_dt = datetime.strptime(f"{today_str} {raw_list[i+1][0]}", "%Y-%m-%d %H:%M")
                                if stop_dt <= start_dt: 
                                    stop_dt += timedelta(days=1)
                            else: 
                                stop_dt = start_dt + timedelta(hours=1)

                            programmes.append({
                                "channel": ch_id,
                                "start": format_xmltv_date(start_dt, "+0700"),
                                "stop": format_xmltv_date(stop_dt, "+0700"),
                                "title": title,
                                "desc": f"Acara {title} di {ch_name}",
                                "lang": "id",
                            })
                        except Exception: 
                            continue
                    return channels, programmes
    except Exception:
        pass
    return [], []

def fetch_all_mncvision_parallel():
    print("[*] Starting mass scan of MNC Vision (ID 1 - 473)...")
    all_channels, all_programmes = [], []
    
    with ThreadPoolExecutor(max_workers=20) as executor:
        results = executor.map(fetch_epg_mncvision_code, range(1, 474))
        for ch_list, progs in results:
            if progs:
                all_channels.extend(ch_list)
                all_programmes.extend(progs)

    print(f"[✓] MNC Vision: Successfully extracted active {len(all_channels)} channels & {len(all_programmes)} program!")
    return all_channels, all_programmes

# --- 4. QAZAQSTAN NETWORK ---
def fetch_epg_qazaqstan(target):
    epg_id, offset = target["id"], target.get("utc_offset", "+0500")
    channels = [{"id": epg_id, "name": target["name"], "icon": target.get("icon", "")}]
    programmes = []
    
    today_str = get_now_in_channel_tz(offset).strftime("%Y-%m-%d")
    base_url = target['url'].rstrip('/')
    direct_url = f"{base_url}/{today_str}" if not base_url.endswith(today_str) else base_url
    
    for url in [direct_url, f"https://iptv-playlist.sulthan-pamenan.workers.dev/?url={quote(direct_url, safe='')}"]:
        try:
            res = HTTP_SESSION.get(url, timeout=15)
            if res.status_code != 200: 
                continue
            soup = BeautifulSoup(res.text, "html.parser")
            raw_progs = []

            # Skema 1: Qazaqstan, Qazsport, Abai, Aqjaiyq
            items_schema1 = soup.select(".program-item, a.program-item")
            if items_schema1:
                for item in items_schema1:
                    text_content = item.get_text(" ", strip=True)
                    match = TIME_PATTERN_HM.search(text_content)
                    if match:
                        t_str = match.group(1).replace(".", ":").zfill(5)[:5]
                        title_elem = item.select_one(".program-title") or item.find(class_=re.compile(r"title|name", re.I))
                        title = clean_text_str(title_elem.get_text(strip=True)) if title_elem else clean_text_str(text_content[match.end():].strip(" -–:\t\n\r"))
                        if title and len(title) >= 2 and not any(r["title"] == title for r in raw_progs):
                            try: 
                                raw_progs.append({"start_dt": datetime.strptime(f"{today_str} {t_str}", "%Y-%m-%d %H:%M"), "title": title})
                            except Exception: 
                                continue

            # Skema 2: Balapan TV (.rounded-full / .drop-shadow)
            if not raw_progs:
                for card in soup.find_all("a", class_=re.compile(r"rounded-full|group", re.I)):
                    text_content = card.get_text(" ", strip=True)
                    match = TIME_PATTERN_HM.search(text_content)
                    if match:
                        title = ""
                        for sdiv in card.find_all("div", class_=re.compile(r"drop-shadow|bg-white", re.I)):
                            stext = sdiv.get_text(strip=True)
                            if not TIME_PATTERN_HM.search(stext) and len(stext) >= 2:
                                title = clean_text_str(stext)
                                break
                        if not title: 
                            title = clean_text_str(text_content[match.end():].strip(" -–:\t\n\r"))
                        if title and len(title) >= 2 and not any(r["title"] == title for r in raw_progs):
                            try: 
                                raw_progs.append({"start_dt": datetime.strptime(f"{today_str} {match.group(1).replace('.', ':').zfill(5)[:5]}", "%Y-%m-%d %H:%M"), "title": title})
                            except Exception: 
                                continue

            if raw_progs:
                raw_progs.sort(key=lambda x: x["start_dt"])
                for i in range(len(raw_progs)):
                    curr, start_dt = raw_progs[i], raw_progs[i]["start_dt"]
                    if i + 1 < len(raw_progs):
                        stop_dt = raw_progs[i + 1]["start_dt"]
                        if stop_dt <= start_dt: 
                            stop_dt += timedelta(days=1)
                    else: 
                        stop_dt = start_dt + timedelta(hours=1)
                    programmes.append({"channel": epg_id, "start": format_xmltv_date(start_dt, offset), "stop": format_xmltv_date(stop_dt, offset), "title": curr["title"], "desc": f"Бағдарлама {curr['title']}", "lang": "kk"})
                print(f"[✓] Qazaqstan Network [{target['name']}]: Successfully loaded {len(programmes)} program!")
                break
        except Exception: 
            continue
    return channels, programmes

# --- 5. RED BULL TV ---
def fetch_epg_redbull_all(targets):
    channels = [{"id": t["id"], "name": t["name"], "icon": t.get("icon", "")} for t in targets]
    programmes = []
    
    def extract_raw_items(data):
        if isinstance(data, list): 
            return data
        if isinstance(data, dict):
            if "items" in data and isinstance(data["items"], list): 
                return data["items"]
            if "cards" in data and isinstance(data["cards"], list): 
                return data["cards"]
            for key in ["data", "epg", "collection"]:
                if key in data and isinstance(data[key], dict):
                    res = extract_raw_items(data[key])
                    if res: 
                        return res
        return []

    for t in targets:
        try:
            res = requests.get(f"https://tv-api.redbull.com/guides/v5.1/rbtv/id_ID/id/{t['rrn']}", headers=HEADERS, timeout=8)
            if res.status_code == 200:
                for item in extract_raw_items(res.json()):
                    title, desc = item.get("title") or item.get("label"), item.get("description") or item.get("short_description")
                    start_iso, end_iso = item.get("start_time") or item.get("startTime"), item.get("end_time") or item.get("endTime")
                    if start_iso and title:
                        start_dt = datetime.fromisoformat(str(start_iso).replace("Z", "+00:00"))
                        end_dt = datetime.fromisoformat(str(end_iso).replace("Z", "+00:00")) if end_iso else start_dt + timedelta(hours=1)
                        programmes.append({"channel": t["id"], "start": format_xmltv_date(start_dt, "+0000"), "stop": format_xmltv_date(end_dt, "+0000"), "title": clean_text_str(title), "desc": clean_text_str(desc), "lang": "en"})
                print(f"[✓] Red Bull TV [{t['name']}]: Direct Fetch Successful!")
        except Exception as e: 
            print(f"[!] Red Bull API Error: {e}")
    return channels, programmes

# --- MAIN ROUTER & EXECUTION ---
def process_single_target(target):
    t_id = target["id"]
    if t_id == "TPChannel.th": 
        return fetch_epg_tpchannel(target)
    elif t_id == "CLTV36.ph": 
        return fetch_epg_cltv36(target)
    elif t_id.endswith(".kz"): 
        return fetch_epg_qazaqstan(target)
    return [], []

def generate_xmltv():
    print("=" * 60)
    print("[*] Starting EPG XMLTV Generation")
    print("=" * 60)
    
    tv_elem = ET.Element("tv", {"generator-info-name": "Universal IPTV EPG Generator"})
    all_channels, all_programmes = [], []

    # 1. Fetch Red Bull TV
    redbull_targets = [t for t in EPG_TARGET_SOURCES if "rrn" in t]
    if redbull_targets:
        rb_channels, rb_programmes = fetch_epg_redbull_all(redbull_targets)
        all_channels.extend(rb_channels)
        all_programmes.extend(rb_programmes)

    # 2. MNC Vision Mass Scan
    mnc_channels, mnc_programmes = fetch_all_mncvision_parallel()
    all_channels.extend(mnc_channels)
    all_programmes.extend(mnc_programmes)

    # 3. Multi-threaded Scraping from Other Sources
    other_targets = [t for t in EPG_TARGET_SOURCES if "rrn" not in t]
    with ThreadPoolExecutor(max_workers=8) as executor:
        for ch_list, progs in executor.map(process_single_target, other_targets):
            all_channels.extend(ch_list)
            all_programmes.extend(progs)

    # 4. Write Channel Element to XML
    for ch in all_channels:
        c_elem = ET.SubElement(tv_elem, "channel", id=ch["id"])
        ET.SubElement(c_elem, "display-name").text = ch["name"]

    # 5. Write Program Elements to XML & Deduplicate
    seen = set()
    for p in all_programmes:
        key = (p["channel"], p["start"])
        if key not in seen:
            seen.add(key)
            p_elem = ET.SubElement(tv_elem, "programme", {"start": p["start"], "stop": p["stop"], "channel": p["channel"]})
            ET.SubElement(p_elem, "title", lang=p.get("lang", "en")).text = p["title"]
            if p.get("desc"): 
                ET.SubElement(p_elem, "desc", lang=p.get("lang", "en")).text = p["desc"]

    # 6. Format Indentasi secara Aman (Standard ASCII Spaces)
    try:
        ET.indent(tv_elem, space="  ")
    except AttributeError:
        pass  # Jaga-jaga jika menggunakan Python versi tua (<3.9)

    # 7. Tulis File Menggunakan Context Manager + Flush
    with open("epg.xml", "wb") as f:
        tree = ET.ElementTree(tv_elem)
        tree.write(f, encoding="utf-8", xml_declaration=True)
        f.flush()

    print("=" * 60)
    print(f"[SUCCESS] Successfully created epg.xml with {len(all_channels)} channel & {len(seen)} programs!")
    print("=" * 60)

if __name__ == "__main__":
    generate_xmltv()
