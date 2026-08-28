import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urljoin
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
import requests

# =========================================================================
# CONSTANTS & COMPILED REGEX
# =========================================================================
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,kk;q=0.8,th;q=0.7,id;q=0.6",
}

TIME_PATTERN_HM = re.compile(r"(\b[0-2]?\d[:.][0-5]\d\b)")
TIME_PATTERN_EXACT = re.compile(r"^([0-2]?\d:[0-5]\d)$")
TIME_PATTERN_AMPM = re.compile(r"(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))", re.IGNORECASE)
MNC_LINK_PATTERN = re.compile(r"/channel/detail/")

IGNORE_WORDS_KZ = {
    "LIVE", "ЭФИРДЕ", "Бағдарлама", "Драма", "Көркем фильм", "Телехикая", 
    "Шоу", "Онлайн көру", "Онлайн қарау", "ҚАЗІР ЭФИРДЕ", "ЖАҢA", "ТІКЕЛЕЙ",
    "ТІКЕЛЕЙ ЭФИР", "LIVE NOW", "СЕГОДНЯ", "ТАҢҒЫ", "ТҮСКІ", "КЕШКІ"
}

EPG_TARGET_SOURCES = [
  {"id": "TPChannel.th", "name": "TP Channel", "url": "https://www.tpchannel.org/tv/schedule", "icon": "", "utc_offset": "+0700"},
  {"id": "PadangTV.id", "name": "Padang TV", "url": "https://padangtv.id/schedule/", "icon": "", "utc_offset": "+0700"},
  {"id": "RedBullTV.global", "name": "Red Bull TV", "url": "https://www.redbull.tv/en/epg", "icon": "", "utc_offset": "+0000"},
  {"id": "MNCVision.all", "name": "MNC Vision All Channels", "url": "https://www.mncvision.id/channel", "icon": "", "utc_offset": "+0700"},
  {"id": "CLTV36.ph", "name": "CLTV36", "url": "https://cltv36.tv/tv-programs/", "icon": "", "utc_offset": "+0800"},
  {"id": "Qazaqstan.kz", "name": "Qazaqstan TV", "url": "https://qazaqstan.tv/program", "icon": "", "utc_offset": "+0500"},
  {"id": "QazaqstanInt.kz", "name": "Qazaqstan International", "url": "https://qazaqstan.tv/program", "icon": "", "utc_offset": "+0500"},
  {"id": "Balapan.kz", "name": "Balapan TV", "url": "https://balapan.tv/program", "icon": "", "utc_offset": "+0500"},
  {"id": "AbaiTV.kz", "name": "Abai TV", "url": "https://abaitv.kz/kz/program", "icon": "", "utc_offset": "+0500"},
  {"id": "Qazsport.kz", "name": "Qazsport", "url": "https://qazsporttv.kz/kz/program", "icon": "", "utc_offset": "+0500"},
  {"id": "AqjaiyqTV.kz", "name": "Aqjaiyq TV", "url": "https://aqjaiyqtv.kz/kz/program", "icon": "", "utc_offset": "+0500"},
  {"id": "AqtobeTV.kz", "name": "Aqtobe TV", "url": "https://aqtobetv.kz/kz/program", "icon": "", "utc_offset": "+0500"},
  {"id": "AltaiTV.kz", "name": "Altai TV", "url": "https://altaitv.kz/kz/program", "icon": "", "utc_offset": "+0500"},
  {"id": "AtyrauTV.kz", "name": "Atyrau TV", "url": "https://atyrautv.kz/kz/program", "icon": "", "utc_offset": "+0500"},
  {"id": "ErtisTV.kz", "name": "Ertis TV", "url": "https://ertistv.kz/kz/program", "icon": "", "utc_offset": "+0500"},
  {"id": "JambylTV.kz", "name": "Jambyl TV", "url": "https://jambyltv.kz/kz/program", "icon": "", "utc_offset": "+0500"},
  {"id": "KoksheTV.kz", "name": "Kokshe TV", "url": "https://kokshetv.kz/kz/program", "icon": "", "utc_offset": "+0500"},
  {"id": "MangystauTV.kz", "name": "Mangystau TV", "url": "https://mangystautv.kz/kz/program", "icon": "", "utc_offset": "+0500"},
  {"id": "OntustikTV.kz", "name": "Ontustik TV", "url": "https://ontustiktv.kz/kz/program", "icon": "", "utc_offset": "+0500"},
  {"id": "QostanaiTV.kz", "name": "Qostanai TV", "url": "https://qostanaitv.kz/kz/program", "icon": "", "utc_offset": "+0500"},
  {"id": "QyzyljarTV.kz", "name": "Qyzyljar TV", "url": "https://qyzyljartv.kz/kz/program", "icon": "", "utc_offset": "+0500"},
  {"id": "QyzylordaTV.kz", "name": "Qyzylorda TV", "url": "https://qyzylordatv.kz/kz/program", "icon": "", "utc_offset": "+0500"},
  {"id": "SaryarqaTV.kz", "name": "Saryarqa TV", "url": "https://saryarqatv.kz/kz/program", "icon": "", "utc_offset": "+0500"},
  {"id": "SemeiTV.kz", "name": "Semei TV", "url": "https://semeitv.kz/kz/program", "icon": "", "utc_offset": "+0500"}
]

HTTP_SESSION = requests.Session()
HTTP_SESSION.headers.update(HEADERS)

def format_xmltv_date(dt_obj, utc_offset="+0700"):
    return dt_obj.strftime(f"%Y%m%d%H%M%S {utc_offset}")

def get_auto_icon(target_url):
    domain = target_url.split("//")[-1].split("/")[0]
    return f"https://www.google.com/s2/favicons?domain={domain}&sz=128"

def parse_offset_hours(offset_str):
    try:
        sign = -1 if offset_str[0] == "-" else 1
        hours = int(offset_str[1:3])
        return sign * hours
    except Exception:
        return 7

def get_now_in_channel_tz(utc_offset_str):
    hours = parse_offset_hours(utc_offset_str)
    return datetime.now(timezone.utc) + timedelta(hours=hours)

def clean_text_str(val):
    if not val:
        return ""
    return re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", str(val)).strip()

# =========================================================================
# 0. TP CHANNEL (THAILAND) - IMPROVED
# =========================================================================
def fetch_epg_tpchannel(target):
    epg_id = target["id"]
    programmes = []
    icon = target.get("icon") or get_auto_icon(target["url"])
    channels = [{"id": epg_id, "name": target["name"], "icon": icon}]
    offset = target.get("utc_offset", "+0700")
    today_local = get_now_in_channel_tz(offset)
    today_str = today_local.strftime("%Y-%m-%d")

    try:
        res = HTTP_SESSION.get(target["url"], timeout=15)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            extracted = []

            # Try multiple selectors
            selectors = [
                ".schedule-item", ".program-list li", ".tv-guide-item",
                ".program-item", "table.schedule tr", ".timeline-item",
                ".epg-item", ".show-item"
            ]
            items = []
            for sel in selectors:
                items = soup.select(sel)
                if items:
                    break
            
            if not items:
                # Fallback: find rows with time patterns
                for elem in soup.find_all(["div", "tr", "li", "p"]):
                    text = elem.get_text(" ", strip=True)
                    if TIME_PATTERN_HM.search(text) and len(text) < 200:
                        items.append(elem)

            for row in items:
                text = row.get_text(" ", strip=True)
                time_match = re.search(r"(\d{1,2}[:.]\d{2})", text)
                if time_match:
                    t_str = time_match.group(1).replace(".", ":").zfill(5)
                    # Remove time and Thai suffixes
                    clean_text = re.sub(r"\d{1,2}[:.]\d{2}\s*(?:น\.|น)?", "", text).strip()
                    clean_text = re.sub(r"\s+", " ", clean_text)
                    # Remove extra numbers at start
                    clean_text = re.sub(r"^\d{2}\s+", "", clean_text).strip()

                    if clean_text and len(clean_text) > 2 and not clean_text.isdigit():
                        if not extracted or extracted[-1][0] != t_str:
                            extracted.append((t_str, clean_text))

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

                    programmes.append({
                        "channel": epg_id,
                        "start": format_xmltv_date(start_dt, offset),
                        "stop": format_xmltv_date(stop_dt, offset),
                        "title": clean_text_str(title),
                        "desc": clean_text_str(f"Broadcast of {title} on {target['name']}"),
                        "lang": "th",
                    })
                except Exception:
                    continue
    except Exception as e:
        print(f"[!] TPChannel Error: {e}")

    return channels, programmes

# =========================================================================
# 1. PADANG TV - IMPROVED
# =========================================================================
def fetch_epg_padangtv(target):
    epg_id = target["id"]
    programmes = []
    icon = target.get("icon") or get_auto_icon(target["url"])
    channels = [{"id": epg_id, "name": target["name"], "icon": icon}]
    offset = target.get("utc_offset", "+0700")
    today_local = get_now_in_channel_tz(offset)
    today_str = today_local.strftime("%Y-%m-%d")

    try:
        res = HTTP_SESSION.get(target["url"], timeout=15)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            extracted = []

            # Try WordPress schedule table or list
            for elem in soup.find_all(["tr", "li", "div", "p"]):
                text = elem.get_text(" ", strip=True)
                if len(text) > 150:
                    continue
                # Match time patterns like 06:00, 6.00, 06.00
                match = re.search(r"(\d{1,2}[:.]\d{2})\s*[-–]?\s*(.+)", text)
                if match:
                    t_str = match.group(1).replace(".", ":").zfill(5)
                    title = match.group(2).strip()
                    # Clean title
                    title = re.sub(r"^[-–:\s]+", "", title)
                    if title and len(title) > 2:
                        extracted.append((t_str, title))

            # Also try generic time pattern
            if not extracted:
                for elem in soup.find_all(["tr", "li", "div"]):
                    text = elem.get_text(" ", strip=True)
                    match = TIME_PATTERN_HM.search(text)
                    if match:
                        t_str = match.group(1).replace(".", ":").zfill(5)
                        title = text[match.end():].strip(" -–:\t\n\r")
                        if title and len(title) > 2:
                            extracted.append((t_str, title))

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

                    programmes.append({
                        "channel": epg_id,
                        "start": format_xmltv_date(start_dt, offset),
                        "stop": format_xmltv_date(stop_dt, offset),
                        "title": clean_text_str(title),
                        "desc": clean_text_str(f"Program {title} on {target['name']}"),
                        "lang": "id",
                    })
                except Exception:
                    continue
    except Exception as e:
        print(f"[!] PadangTV Error: {e}")

    return channels, programmes

# =========================================================================
# 2. RED BULL TV - IMPROVED WITH FALLBACK
# =========================================================================
def fetch_epg_redbull(target):
    epg_id = target["id"]
    programmes = []
    icon = target.get("icon") or get_auto_icon(target["url"])
    channels = [{"id": epg_id, "name": target["name"], "icon": icon}]

    # Try multiple endpoints
    endpoints = [
        "https://api.redbull.tv/v3/epg/live",
        "https://api.redbull.tv/v3/products/schedule",
        "https://www.redbull.tv/api/epg",
    ]

    for endpoint in endpoints:
        try:
            res = HTTP_SESSION.get(endpoint, timeout=12)
            if res.status_code == 200:
                data = res.json()
                items = data.get("items", []) or data.get("data", []) or data.get("schedule", [])
                if not items and isinstance(data, list):
                    items = data

                for item in items:
                    title = item.get("title") or item.get("label") or item.get("name") or "Red Bull Special"
                    desc = item.get("description", f"Show {title} on Red Bull TV")
                    start_iso = item.get("start_time") or item.get("startTime") or item.get("start")
                    end_iso = item.get("end_time") or item.get("endTime") or item.get("end")

                    if start_iso and end_iso:
                        try:
                            # Handle various ISO formats
                            start_iso = start_iso.replace("Z", "+00:00")
                            end_iso = end_iso.replace("Z", "+00:00")
                            start_dt = datetime.fromisoformat(start_iso)
                            end_dt = datetime.fromisoformat(end_iso)
                            programmes.append({
                                "channel": epg_id,
                                "start": format_xmltv_date(start_dt, "+0000"),
                                "stop": format_xmltv_date(end_dt, "+0000"),
                                "title": clean_text_str(title),
                                "desc": clean_text_str(desc),
                                "lang": "en",
                            })
                        except Exception:
                            continue
                if programmes:
                    break
        except Exception:
            continue

    return channels, programmes

# =========================================================================
# 3. MNC VISION - IMPROVED
# =========================================================================
def fetch_single_mnc(args):
    href, raw_name, base_url, today_local, default_icon = args
    programmes = []
    clean_name = re.sub(r"[^a-zA-Z0-9]", "", raw_name)
    if not clean_name:
        return None, []

    epg_id = f"{clean_name}.mnc"
    ch_info = {"id": epg_id, "name": f"{raw_name} (MNC)", "icon": default_icon}

    try:
        res = HTTP_SESSION.get(urljoin(base_url, href), timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            items = []

            # Look for schedule in various containers
            for row in soup.find_all(["tr", "li", "div", "p"]):
                text = row.get_text(strip=True)
                if len(text) > 120:
                    continue

                match = TIME_PATTERN_HM.search(text)
                if match:
                    t_str = match.group(1).replace(".", ":").zfill(5)
                    raw_title = text[match.end() :].strip(" -–:\t\n\r[]")
                    clean_title = re.sub(r"^\d{1,2}[:.]\d{2}\s*", "", raw_title)
                    clean_title = re.sub(r"^\d{2}\b", "", clean_title).strip()

                    if clean_title and len(clean_title) > 2:
                        items.append((t_str, clean_title))

            today_str = today_local.strftime("%Y-%m-%d")
            for i in range(len(items)):
                t_str, title = items[i]
                start_dt = datetime.strptime(f"{today_str} {t_str}", "%Y-%m-%d %H:%M")
                if i + 1 < len(items):
                    stop_dt = datetime.strptime(f"{today_str} {items[i+1][0]}", "%Y-%m-%d %H:%M")
                    if stop_dt <= start_dt:
                        stop_dt += timedelta(days=1)
                else:
                    stop_dt = start_dt + timedelta(hours=1)

                programmes.append({
                    "channel": epg_id,
                    "start": format_xmltv_date(start_dt, "+0700"),
                    "stop": format_xmltv_date(stop_dt, "+0700"),
                    "title": clean_text_str(title),
                    "desc": clean_text_str(f"Broadcast of {title} on {raw_name}"),
                    "lang": "id",
                })
    except Exception:
        pass
    return ch_info, programmes

def fetch_epg_mncvision(target):
    channels, programmes = [], []
    default_icon = target.get("icon") or get_auto_icon(target["url"])
    today_local = get_now_in_channel_tz("+0700")

    try:
        res = HTTP_SESSION.get(target["url"], timeout=12)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            links = soup.find_all("a", href=MNC_LINK_PATTERN)
            visited, tasks = set(), []

            for l in links:
                href = l.get("href")
                if href in visited:
                    continue
                visited.add(href)
                raw_name = l.get_text(strip=True) or href.split("/")[-1]
                tasks.append((
                    href,
                    raw_name,
                    "https://www.mncvision.id",
                    today_local,
                    default_icon,
                ))

            with ThreadPoolExecutor(max_workers=8) as executor:
                results = executor.map(fetch_single_mnc, tasks)

            for ch_info, progs in results:
                # Only add channel if it has programmes
                if ch_info and progs:
                    channels.append(ch_info)
                    programmes.extend(progs)
    except Exception as e:
        print(f"[!] MNC Error: {e}")
    return channels, programmes

# =========================================================================
# 4. CLTV36
# =========================================================================
def fetch_epg_cltv36(target):
    epg_id = target["id"]
    programmes = []
    icon = target.get("icon") or get_auto_icon(target["url"])
    channels = [{"id": epg_id, "name": target["name"], "icon": icon}]
    today_local = get_now_in_channel_tz("+0800")

    try:
        res = HTTP_SESSION.get(target["url"], timeout=12)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")

            for container in soup.find_all(["div", "article", "tr", "p"]):
                text = container.get_text(" ", strip=True)
                time_matches = TIME_PATTERN_AMPM.findall(text)

                if time_matches:
                    title_tag = container.find(["h1", "h2", "h3", "h4", "h5", "strong", "b"])
                    title = title_tag.get_text(strip=True) if title_tag else ""
                    if not title or len(title) < 3 or "program" in title.lower():
                        clean_t = re.sub(TIME_PATTERN_AMPM, "", text).strip()
                        title = clean_t if len(clean_t) > 2 else title

                    if not title:
                        continue

                    try:
                        start_str = time_matches[0].upper().replace(" ", "")
                        start_dt = datetime.combine(
                            today_local.date(),
                            datetime.strptime(start_str.zfill(7), "%I:%M%p").time(),
                        )

                        if len(time_matches) > 1:
                            end_str = time_matches[1].upper().replace(" ", "")
                            stop_dt = datetime.combine(
                                today_local.date(),
                                datetime.strptime(end_str.zfill(7), "%I:%M%p").time(),
                            )
                            if stop_dt <= start_dt:
                                stop_dt += timedelta(days=1)
                        else:
                            stop_dt = start_dt + timedelta(hours=1)

                        prog_data = {
                            "channel": epg_id,
                            "start": format_xmltv_date(start_dt, "+0800"),
                            "stop": format_xmltv_date(stop_dt, "+0800"),
                            "title": clean_text_str(title),
                            "desc": clean_text_str(f"Broadcast of {title} on CLTV36"),
                            "lang": "en",
                        }
                        if prog_data not in programmes:
                            programmes.append(prog_data)
                    except Exception:
                        continue
    except Exception as e:
        print(f"[!] CLTV36 Error: {e}")
    return channels, programmes

# =========================================================================
# 5. QAZAQSTAN NETWORK - MAJOR IMPROVEMENTS
# =========================================================================
def fetch_epg_qazaqstan(target):
    epg_id = target["id"]
    icon = target.get("icon") or get_auto_icon(target["url"])
    channels = [{"id": epg_id, "name": target["name"], "icon": icon}]
    programmes = []

    kz_now = get_now_in_channel_tz("+0500")
    today_str = kz_now.strftime("%Y-%m-%d")

    raw_progs = []
    
    # Try direct URL first, then with proxy fallback
    urls_to_try = [
        f"{target['url'].rstrip('/')}/{today_str}",
    ]
    
    # Add proxy fallback if needed
    proxy = "https://iptv-playlist.sulthan-pamenan.workers.dev/?url="
    urls_to_try.append(f"{proxy}{quote(urls_to_try[0], safe='')}")

    for url in urls_to_try:
        try:
            res = HTTP_SESSION.get(url, timeout=20)
            if res.status_code != 200:
                continue

            soup = BeautifulSoup(res.text, "html.parser")

            # 1. Try extraction via Livewire Snapshot Data
            wire_el = soup.find(lambda tag: tag.has_attr("wire:snapshot") or tag.has_attr("wire:initial-data"))
            if wire_el:
                try:
                    raw_json = wire_el.get("wire:snapshot") or wire_el.get("wire:initial-data")
                    data = json.loads(raw_json)
                    
                    # Navigate various possible structures
                    schedules = []
                    if "memo" in data and "data" in data["memo"]:
                        schedules = data["memo"]["data"].get("schedules", [])
                    elif "data" in data:
                        schedules = data["data"].get("schedules", [])
                    elif "schedules" in data:
                        schedules = data["schedules"]
                    
                    for item in schedules:
                        t_start = item.get("time") or item.get("start_time") or item.get("start")
                        title = item.get("title") or item.get("name") or item.get("program")
                        if t_start and title:
                            try:
                                start_dt = datetime.strptime(f"{today_str} {t_start}", "%Y-%m-%d %H:%M")
                                raw_progs.append({
                                    "start_dt": start_dt,
                                    "title": clean_text_str(title),
                                    "desc": clean_text_str(f"Program {title} di {target['name']}"),
                                })
                            except Exception:
                                continue
                    if raw_progs:
                        break
                except Exception:
                    pass

            # 2. Try HTML Parsing fallback
            if not raw_progs:
                # Try various selectors common on Kazakh TV sites
                selectors = [
                    ".schedule-item", ".program-item", ".tv-program", 
                    ".schedule-list li", ".program-list li",
                    "[class*='schedule']", "[class*='program']"
                ]
                schedule_blocks = []
                for sel in selectors:
                    schedule_blocks = soup.select(sel)
                    if schedule_blocks:
                        break
                
                if not schedule_blocks:
                    schedule_blocks = soup.find_all(["li", "tr", "div", "article"])

                seen_times = set()
                for block in schedule_blocks:
                    txt = block.get_text(" ", strip=True)
                    # Look for time pattern
                    match = TIME_PATTERN_HM.search(txt)
                    if match:
                        t_str = match.group(1).replace(".", ":").zfill(5)
                        title_candidate = txt[match.end():].strip(" -–:\t\n\r")
                        
                        # Remove ignore words
                        for w in IGNORE_WORDS_KZ:
                            title_candidate = title_candidate.replace(w, "").strip()
                        
                        # Clean up
                        title_candidate = re.sub(r"^\d{1,2}[:.]\d{2}\s*", "", title_candidate)
                        title_candidate = re.sub(r"^\d{2}\b", "", title_candidate).strip()

                        if title_candidate and len(title_candidate) > 2:
                            try:
                                start_dt = datetime.strptime(f"{today_str} {t_str}", "%Y-%m-%d %H:%M")
                                time_key = start_dt.strftime("%H:%M")
                                if time_key not in seen_times:
                                    seen_times.add(time_key)
                                    raw_progs.append({
                                        "start_dt": start_dt,
                                        "title": clean_text_str(title_candidate),
                                        "desc": clean_text_str(f"Program {title_candidate} di {target['name']}"),
                                    })
                            except Exception:
                                continue
                if raw_progs:
                    break
        except Exception as e:
            print(f"[!] Scraper Warning [{target['name']}] on {url}: {e}")
            continue

    if raw_progs:
        return build_xmltv_programmes(epg_id, target, channels, raw_progs)
    
    return channels, programmes

def build_xmltv_programmes(epg_id, target, channels, raw_progs):
    programmes = []
    raw_progs.sort(key=lambda x: x["start_dt"])
    offset = target.get("utc_offset", "+0500")

    for i in range(len(raw_progs)):
        curr = raw_progs[i]
        start_dt = curr["start_dt"]

        if i + 1 < len(raw_progs):
            stop_dt = raw_progs[i + 1]["start_dt"]
            if stop_dt <= start_dt:
                stop_dt += timedelta(days=1)
        else:
            stop_dt = start_dt + timedelta(hours=1)

        programmes.append({
            "channel": epg_id,
            "start": format_xmltv_date(start_dt, offset),
            "stop": format_xmltv_date(stop_dt, offset),
            "title": curr["title"],
            "desc": curr["desc"],
            "lang": "kk",
        })
    return channels, programmes

# =========================================================================
# 6. UNIVERSAL SCRAPER - IMPROVED
# =========================================================================
def auto_scrape_epg(target):
    epg_id = target["id"]
    programmes = []
    icon = target.get("icon") or get_auto_icon(target["url"])
    channels = [{"id": epg_id, "name": target["name"], "icon": icon}]

    offset = target.get("utc_offset", "+0700")
    today_local = get_now_in_channel_tz(offset)
    today_str = today_local.strftime("%Y-%m-%d")

    try:
        res = HTTP_SESSION.get(target["url"], timeout=12)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            extracted = []

            for element in soup.find_all(["tr", "li", "p", "div", "article", "section"]):
                text = element.get_text(" ", strip=True)
                if len(text) > 150:
                    continue
                match = TIME_PATTERN_HM.search(text)
                if match:
                    t_str = match.group(1).replace(".", ":").zfill(5)
                    title = text[match.end() :].strip(" -–:\t\n\r")
                    # Remove leading numbers that might be durations
                    title = re.sub(r"^\d{2,3}\s*[-–]?\s*", "", title).strip()
                    if title and len(title) > 2:
                        extracted.append((t_str, title))

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

                    programmes.append({
                        "channel": epg_id,
                        "start": format_xmltv_date(start_dt, offset),
                        "stop": format_xmltv_date(stop_dt, offset),
                        "title": clean_text_str(title),
                        "desc": clean_text_str(f"Program {title} on {target['name']}"),
                        "lang": "en",
                    })
                except Exception:
                    continue
    except Exception as e:
        print(f"[!] Universal Scraper Error [{target['name']}]: {e}")

    return channels, programmes

# ROUTER
def process_single_target(target):
    t_url = target["url"].lower()
    t_id = target["id"]

    if "tpchannel.org" in t_url or t_id == "TPChannel.th":
        return fetch_epg_tpchannel(target)
    elif "padangtv.id" in t_url or t_id == "PadangTV.id":
        return fetch_epg_padangtv(target)
    elif "mncvision" in t_url:
        return fetch_epg_mncvision(target)
    elif "redbull" in t_url or t_id == "RedBullTV.global":
        return fetch_epg_redbull(target)
    elif "cltv36" in t_url or t_id == "CLTV36.ph":
        return fetch_epg_cltv36(target)
    elif t_id.endswith(".kz") or "qazaqstan" in t_url:
        return fetch_epg_qazaqstan(target)
    else:
        return auto_scrape_epg(target)

# =========================================================================
# MAIN LOGIC
# =========================================================================
def generate_xmltv():
    print("[*] Starting EPG scraping...")
    tv_elem = ET.Element(
        "tv",
        {
            "generator-info-name": "Universal IPTV EPG Generator",
            "generator-info-url": "https://github.com/sulthanpamenan",
        },
    )

    all_channels = []
    all_programmes = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(process_single_target, EPG_TARGET_SOURCES)

    for ch_list, progs in results:
        all_channels.extend(ch_list)
        all_programmes.extend(progs)

    # 1. Channels
    for ch in all_channels:
        c_elem = ET.SubElement(tv_elem, "channel", id=ch["id"])
        d_elem = ET.SubElement(c_elem, "display-name")
        d_elem.text = ch["name"]
        if ch.get("icon"):
            ET.SubElement(c_elem, "icon", src=ch["icon"])

    # 2. Programmes
    for prog in all_programmes:
        p_elem = ET.SubElement(tv_elem, "programme", {
            "start": prog["start"],
            "stop": prog["stop"],
            "channel": prog["channel"],
        })
        t_elem = ET.SubElement(p_elem, "title", lang=prog.get("lang", "en"))
        t_elem.text = prog["title"]
        if prog.get("desc"):
            d_elem = ET.SubElement(p_elem, "desc", lang=prog.get("lang", "en"))
            d_elem.text = prog["desc"]

    ET.indent(tv_elem, space=" ")
    tree = ET.ElementTree(tv_elem)
    tree.write("epg.xml", encoding="utf-8", xml_declaration=True)

    print(
        f"\n[SUCCESS] `epg.xml` file updated with {len(all_channels)} channels"
        f" and {len(all_programmes)} programs!"
    )

if __name__ == "__main__":
    generate_xmltv()
