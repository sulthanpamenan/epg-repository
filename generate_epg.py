import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urljoin
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,kk;q=0.8,th;q=0.7,id;q=0.6",
}

TIME_PATTERN_HM = re.compile(r"(\b[0-2]?\d[:.][0-5]\d\b)")
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
# SCRAPERS WITH DIAGNOSTIC LOGS
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
    
    try:
        res = HTTP_SESSION.get(api_url, timeout=12)
        print(f"[DIAGNOSTIC] TPChannel HTTP Response: {res.status_code}")
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
                    stop_dt = start_dt + timedelta(hours=1)
                    programmes.append({"channel": epg_id, "start": format_xmltv_date(start_dt, offset), "stop": format_xmltv_date(stop_dt, offset), "title": title, "desc": title, "lang": "th"})
                except Exception:
                    continue
    except Exception as e:
        print(f"[DIAGNOSTIC] TPChannel Error: {e}")

    print(f"[RESULT] TPChannel found {len(programmes)} programs")
    return channels, programmes

def fetch_epg_redbull(target):
    epg_id = target["id"]
    programmes = []
    icon = target.get("icon") or get_auto_icon(target["url"])
    channels = [{"id": epg_id, "name": target["name"], "icon": icon}]
    api_url = "https://tv-api.redbull.com/products/dynamic/v5.2/rbtv/en/id/rrn:content:video-channels:c81f8686-ab67-4965-ba04-5f6658bb96cc"
    
    try:
        res = HTTP_SESSION.get(api_url, timeout=12)
        print(f"[DIAGNOSTIC] RedBull HTTP Response: {res.status_code}")
        if res.status_code == 200:
            data = res.json()
            items = data.get("epg", []) or data.get("schedules", []) or data.get("items", [])
            for item in items:
                title = item.get("title") or "Red Bull TV Special"
                start_iso = item.get("start_time") or item.get("startTime")
                end_iso = item.get("end_time") or item.get("endTime")
                if start_iso and end_iso:
                    try:
                        start_dt = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
                        end_dt = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
                        programmes.append({"channel": epg_id, "start": format_xmltv_date(start_dt, "+0000"), "stop": format_xmltv_date(end_dt, "+0000"), "title": clean_text_str(title), "desc": title, "lang": "en"})
                    except Exception:
                        continue
    except Exception as e:
        print(f"[DIAGNOSTIC] RedBull Error: {e}")

    print(f"[RESULT] RedBull found {len(programmes)} programs")
    return channels, programmes

def fetch_epg_mncvision(target):
    channels, programmes = [], []
    default_icon = target.get("icon") or get_auto_icon("https://www.mncvision.id")
    today_local = get_now_in_channel_tz("+0700")
    today_str = today_local.strftime("%Y-%m-%d")

    post_url = "https://www.mncvision.id/schedule/formSearch"
    post_data = {"fdate": today_str, "submit": "Submit"}
    mnc_headers = {
        "User-Agent": HEADERS["User-Agent"],
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://www.mncvision.id",
        "Referer": "https://www.mncvision.id/schedule/formSearch",
    }

    try:
        res = HTTP_SESSION.post(post_url, data=post_data, headers=mnc_headers, timeout=15)
        print(f"[DIAGNOSTIC] MNC Vision POST HTTP Response: {res.status_code}")
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            rows = soup.find_all("tr")
            print(f"[DIAGNOSTIC] MNC Vision table rows found: {len(rows)}")
            
            for row in rows:
                ch_cell = row.find(["td", "th"], class_=re.compile(r"channel|ch", re.I)) or row.find("a", href=MNC_LINK_PATTERN)
                if not ch_cell:
                    continue
                
                img_tag = ch_cell.find("img")
                raw_ch_name = img_tag.get("alt") if img_tag and img_tag.get("alt") else ch_cell.get_text(strip=True)
                ch_name = clean_text_str(raw_ch_name)
                clean_ch_id = re.sub(r"[^a-zA-Z0-9]", "", ch_name) + ".mnc"

                prog_cells = row.find_all(["td", "div"], class_=re.compile(r"prog|schedule|event", re.I))
                extracted_items = []

                for cell in prog_cells:
                    text = cell.get_text(" ", strip=True)
                    match = TIME_PATTERN_HM.search(text)
                    if match:
                        t_str = match.group(1).replace(".", ":").zfill(5)
                        title = text[match.end():].strip(" -–:\t\n\r[]")
                        if title:
                            extracted_items.append((t_str, clean_text_str(title)))

                if extracted_items:
                    channels.append({"id": clean_ch_id, "name": f"{ch_name} (MNC)", "icon": default_icon})
                    for i in range(len(extracted_items)):
                        t_str, title = extracted_items[i]
                        try:
                            start_dt = datetime.strptime(f"{today_str} {t_str}", "%Y-%m-%d %H:%M")
                            stop_dt = start_dt + timedelta(hours=1)
                            programmes.append({"channel": clean_ch_id, "start": format_xmltv_date(start_dt, "+0700"), "stop": format_xmltv_date(stop_dt, "+0700"), "title": title, "desc": title, "lang": "id"})
                        except Exception:
                            continue
    except Exception as e:
        print(f"[DIAGNOSTIC] MNC Vision Error: {e}")

    print(f"[RESULT] MNC Vision found {len(channels)} channels and {len(programmes)} programs")
    return channels, programmes

def fetch_epg_cltv36(target):
    epg_id = target["id"]
    programmes = []
    icon = target.get("icon") or get_auto_icon(target["url"])
    channels = [{"id": epg_id, "name": target["name"], "icon": icon}]
    
    try:
        res = HTTP_SESSION.get(target["url"], timeout=15)
        print(f"[DIAGNOSTIC] CLTV36 HTTP Response: {res.status_code}")
    except Exception as e:
        print(f"[DIAGNOSTIC] CLTV36 Error: {e}")

    return channels, programmes

def fetch_epg_qazaqstan(target):
    epg_id = target["id"]
    icon = target.get("icon") or get_auto_icon(target["url"])
    channels = [{"id": epg_id, "name": target["name"], "icon": icon}]
    programmes = []
    kz_now = get_now_in_channel_tz("+0500")
    today_str = kz_now.strftime("%Y-%m-%d")
    direct_url = f"{target['url'].rstrip('/')}/{today_str}"

    try:
        res = HTTP_SESSION.get(direct_url, timeout=15)
        print(f"[DIAGNOSTIC] Qazaqstan Network [{target['name']}] HTTP Response: {res.status_code}")
    except Exception as e:
        print(f"[DIAGNOSTIC] Qazaqstan Network [{target['name']}] Error: {e}")

    return channels, programmes

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
        return fetch_epg_tpchannel(target)

def generate_xmltv():
    print("[*] Starting EPG scraping with Diagnostics...")
    tv_elem = ET.Element("tv", {"generator-info-name": "Universal IPTV EPG Generator"})

    all_channels = []
    all_programmes = []

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = executor.map(process_single_target, EPG_TARGET_SOURCES)

    for ch_list, progs in results:
        all_channels.extend(ch_list)
        all_programmes.extend(progs)

    all_programmes = fix_and_sort_epg_programmes(all_programmes)

    for ch in all_channels:
        c_elem = ET.SubElement(tv_elem, "channel", id=ch["id"])
        d_elem = ET.SubElement(c_elem, "display-name")
        d_elem.text = ch["name"]

    for prog in all_programmes:
        p_elem = ET.SubElement(tv_elem, "programme", {"start": prog["start"], "stop": prog["stop"], "channel": prog["channel"]})
        t_elem = ET.SubElement(p_elem, "title", lang=prog.get("lang", "en"))
        t_elem.text = prog["title"]

    ET.indent(tv_elem, space=" ")
    tree = ET.ElementTree(tv_elem)
    tree.write("epg.xml", encoding="utf-8", xml_declaration=True)

    print(f"\n[FINAL RESULT] `epg.xml` file generated with {len(all_channels)} channels and {len(all_programmes)} programs!")

if __name__ == "__main__":
    generate_xmltv()
