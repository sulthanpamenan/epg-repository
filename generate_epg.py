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
  {"id": "RedBullTV.global", "name": "Red Bull TV", "url": "https://www.redbull.tv/en/epg", "icon": "", "utc_offset": "+0000"},
  {"id": "MNCVision.all", "name": "MNC Vision All Channels", "url": "https://www.mncvision.id/schedule/formSearch", "icon": "", "utc_offset": "+0700"},
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

def fix_and_sort_epg_programmes(programmes):
    """
    Mengurutkan program berdasarkan channel dan waktu mulai secara kronologis,
    serta menghilangkan entri dengan slot waktu bentrok/duplikat.
    """
    seen_slots = set()
    cleaned_programmes = []

    sorted_programmes = sorted(
        programmes, 
        key=lambda x: (x['channel'], x['start'])
    )

    for prog in sorted_programmes:
        channel = prog['channel']
        start = prog['start']
        stop = prog['stop']

        if stop <= start:
            continue

        slot_key = (channel, start)
        if slot_key in seen_slots:
            continue
            
        seen_slots.add(slot_key)
        cleaned_programmes.append(prog)

    return cleaned_programmes

# =========================================================================
# 0. TP CHANNEL (THAILAND) - API JSON PARSER
# =========================================================================
def fetch_epg_tpchannel(target):
    epg_id = target["id"]
    programmes = []
    icon = target.get("icon") or get_auto_icon(target["url"])
    channels = [{"id": epg_id, "name": target["name"], "icon": icon}]
    
    offset = target.get("utc_offset", "+0700")
    today_local = get_now_in_channel_tz(offset)
    
    thai_year = today_local.year + 543
    date_param = f"{thai_year}-{today_local.strftime('%m-%d')}"
    today_str = today_local.strftime("%Y-%m-%d")

    api_url = f"https://www.tpchannel.org/tv/schedule/get-by-date?master_type_id=2&date={date_param}"
    
    tp_headers = {
        "User-Agent": HEADERS["User-Agent"],
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.tpchannel.org/tv/schedule",
    }

    try:
        res = HTTP_SESSION.get(api_url, headers=tp_headers, timeout=12)
        if res.status_code == 200:
            data = res.json()
            items = data if isinstance(data, list) else data.get("data", []) or data.get("result", [])

            extracted = []
            for item in items:
                t_str = item.get("time") or item.get("start_time") or item.get("schedule_time")
                title = item.get("title") or item.get("program_name") or item.get("name")

                if t_str and title:
                    t_str = str(t_str).replace(".", ":").zfill(5)[:5]
                    extracted.append((t_str, clean_text_str(title)))

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
                        "title": title,
                        "desc": clean_text_str(f"Program {title} on TP Channel"),
                        "lang": "th",
                    })
                except Exception:
                    continue
    except Exception as e:
        print(f"[!] TP Channel Error: {e}")

    if not programmes:
        return auto_scrape_epg(target)

    return channels, programmes

# =========================================================================
# 1. RED BULL TV
# =========================================================================
def fetch_epg_redbull(target):
    epg_id = target["id"]
    programmes = []
    icon = target.get("icon") or get_auto_icon(target["url"])
    channels = [{"id": epg_id, "name": target["name"], "icon": icon}]

    api_url = "https://tv-api.redbull.com/products/dynamic/v5.2/rbtv/en/id/rrn:content:video-channels:c81f8686-ab67-4965-ba04-5f6658bb96cc"
    rb_headers = {
        "User-Agent": HEADERS["User-Agent"],
        "Accept": "*/*",
        "Origin": "https://www.redbull.tv",
        "Referer": "https://www.redbull.tv/",
    }

    try:
        res = HTTP_SESSION.get(api_url, headers=rb_headers, timeout=12)
        if res.status_code == 200:
            data = res.json()
            items = data.get("epg", []) or data.get("schedules", []) or data.get("items", [])

            for item in items:
                title = item.get("title") or item.get("label") or "Red Bull TV Special"
                desc = item.get("description") or item.get("subTitle") or f"Program {title} on Red Bull TV"
                
                start_iso = item.get("start_time") or item.get("startTime")
                end_iso = item.get("end_time") or item.get("endTime")

                if start_iso and end_iso:
                    try:
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
    except Exception as e:
        print(f"[!] RedBullTV Error: {e}")

    return channels, programmes

# =========================================================================
# 2. MNC VISION - DIRECT POST FORM PARSER
# =========================================================================
def fetch_epg_mncvision(target):
    channels, programmes = [], []
    default_icon = target.get("icon") or get_auto_icon("https://www.mncvision.id")
    today_local = get_now_in_channel_tz("+0700")
    today_str = today_local.strftime("%Y-%m-%d")

    post_url = "https://www.mncvision.id/schedule/formSearch"
    post_data = {
        "fdate": today_str,
        "submit": "Submit"
    }
    mnc_headers = {
        "User-Agent": HEADERS["User-Agent"],
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://www.mncvision.id",
        "Referer": "https://www.mncvision.id/schedule/formSearch",
    }

    try:
        res = HTTP_SESSION.post(post_url, data=post_data, headers=mnc_headers, timeout=15)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            rows = soup.find_all("tr")
            
            for row in rows:
                ch_cell = row.find(["td", "th"], class_=re.compile(r"channel|ch", re.I)) or row.find("a", href=MNC_LINK_PATTERN)
                if not ch_cell:
                    continue
                
                ch_name = clean_text_str(ch_cell.get_text(strip=True))
                if not ch_name:
                    continue
                
                clean_ch_id = re.sub(r"[^a-zA-Z0-9]", "", ch_name) + ".mnc"
                
                if not any(c["id"] == clean_ch_id for c in channels):
                    channels.append({
                        "id": clean_ch_id,
                        "name": f"{ch_name} (MNC)",
                        "icon": default_icon
                    })

                prog_cells = row.find_all(["td", "div"], class_=re.compile(r"prog|schedule|event", re.I))
                extracted_items = []

                for cell in prog_cells:
                    text = cell.get_text(" ", strip=True)
                    match = TIME_PATTERN_HM.search(text)
                    if match:
                        t_str = match.group(1).replace(".", ":").zfill(5)
                        title = text[match.end():].strip(" -–:\t\n\r[]")
                        title = re.sub(r"^\d{1,2}[:.]\d{2}\s*", "", title).strip()
                        if title and len(title) > 2:
                            extracted_items.append((t_str, clean_text_str(title)))

                for i in range(len(extracted_items)):
                    t_str, title = extracted_items[i]
                    try:
                        start_dt = datetime.strptime(f"{today_str} {t_str}", "%Y-%m-%d %H:%M")
                        if i + 1 < len(extracted_items):
                            stop_dt = datetime.strptime(f"{today_str} {extracted_items[i+1][0]}", "%Y-%m-%d %H:%M")
                            if stop_dt <= start_dt:
                                stop_dt += timedelta(days=1)
                        else:
                            stop_dt = start_dt + timedelta(hours=1)

                        programmes.append({
                            "channel": clean_ch_id,
                            "start": format_xmltv_date(start_dt, "+0700"),
                            "stop": format_xmltv_date(stop_dt, "+0700"),
                            "title": title,
                            "desc": clean_text_str(f"Broadcast of {title} on {ch_name}"),
                            "lang": "id",
                        })
                    except Exception:
                        continue
    except Exception as e:
        print(f"[!] MNC Vision POST Error: {e}")

    return channels, programmes

# =========================================================================
# 3. CLTV36 (PHILIPPINES)
# =========================================================================
def fetch_epg_cltv36(target):
    epg_id = target["id"]
    programmes = []
    icon = target.get("icon") or get_auto_icon(target["url"])
    channels = [{"id": epg_id, "name": target["name"], "icon": icon}]
    today_local = get_now_in_channel_tz("+0800")

    try:
        res = HTTP_SESSION.get(target["url"], timeout=15)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            wrappers = soup.select(".elementor-widget-wrap.elementor-element-populated")
            
            for wrap in wrappers:
                h2_tag = wrap.find("h2", class_="elementor-heading-title")
                if not h2_tag:
                    continue
                title = clean_text_str(h2_tag.get_text(strip=True))
                
                text_content = wrap.get_text(" ", strip=True)
                time_matches = TIME_PATTERN_AMPM.findall(text_content)
                
                if title and time_matches:
                    try:
                        start_str = time_matches[0].upper().replace(" ", "")
                        start_time = datetime.strptime(start_str.zfill(7), "%I:%M%p").time()
                        start_dt = datetime.combine(today_local.date(), start_time)

                        if len(time_matches) > 1:
                            end_str = time_matches[1].upper().replace(" ", "")
                            end_time = datetime.strptime(end_str.zfill(7), "%I:%M%p").time()
                            stop_dt = datetime.combine(today_local.date(), end_time)
                            if stop_dt <= start_dt:
                                stop_dt += timedelta(days=1)
                        else:
                            stop_dt = start_dt + timedelta(hours=1)

                        prog_data = {
                            "channel": epg_id,
                            "start": format_xmltv_date(start_dt, "+0800"),
                            "stop": format_xmltv_date(stop_dt, "+0800"),
                            "title": title,
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
# 4. QAZAQSTAN NETWORK (WORKER PROXY ENFORCED)
# =========================================================================
def fetch_epg_qazaqstan(target):
    epg_id = target["id"]
    icon = target.get("icon") or get_auto_icon(target["url"])
    channels = [{"id": epg_id, "name": target["name"], "icon": icon}]
    programmes = []

    kz_now = get_now_in_channel_tz("+0500")
    today_str = kz_now.strftime("%Y-%m-%d")

    raw_progs = []
    direct_url = f"{target['url'].rstrip('/')}/{today_str}"
    proxy_prefix = "https://iptv-playlist.sulthan-pamenan.workers.dev/?url="
    
    urls_to_try = [
        f"{proxy_prefix}{quote(direct_url, safe='')}",
        direct_url
    ]

    for url in urls_to_try:
        try:
            res = HTTP_SESSION.get(url, timeout=20)
            if res.status_code != 200:
                continue

            soup = BeautifulSoup(res.text, "html.parser")

            wire_el = soup.find(lambda tag: tag.has_attr("wire:snapshot") or tag.has_attr("wire:initial-data"))
            if wire_el:
                try:
                    raw_json = wire_el.get("wire:snapshot") or wire_el.get("wire:initial-data")
                    data = json.loads(raw_json)
                    
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

            if not raw_progs:
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
                    match = TIME_PATTERN_HM.search(txt)
                    if match:
                        t_str = match.group(1).replace(".", ":").zfill(5)
                        title_candidate = txt[match.end():].strip(" -–:\t\n\r")
                        
                        for w in IGNORE_WORDS_KZ:
                            title_candidate = title_candidate.replace(w, "").strip()
                        
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
# 5. UNIVERSAL SCRAPER
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

    # Clean & Sort EPG Programmes Kronologis
    all_programmes = fix_and_sort_epg_programmes(all_programmes)

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
