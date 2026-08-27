import re
import json
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin, quote
from concurrent.futures import ThreadPoolExecutor

# =========================================================================
# CONSTANTS & COMPILED REGEX
# =========================================================================
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"}
TIME_PATTERN_HM = re.compile(r'(\b[0-2]?\d[:.][0-5]\d\b)')
TIME_PATTERN_EXACT = re.compile(r'^([0-2]?\d:[0-5]\d)$')
TIME_PATTERN_AMPM = re.compile(r'(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))')
MNC_LINK_PATTERN = re.compile(r'/channel/detail/')

IGNORE_WORDS_KZ = {"LIVE", "ЭФИРДЕ", "Бағдарлама", "Драма", "Көркем фильм", "Телехикая", "Шоу", "Онлайн көру", "Онлайн қарау", "ҚАЗІР ЭФИРДЕ"}

EPG_TARGET_SOURCES = [
    {"id": "PadangTV.id", "name": "Padang TV", "url": "https://padangtv.id/schedule/", "icon": "", "utc_offset": "+0700"},
    {"id": "RedBullTV.global", "name": "Red Bull TV", "url": "https://www.redbull.tv/en/epg", "icon": "", "utc_offset": "+0000"},
    {"id": "MNCVision.all", "name": "MNC Vision All Channels", "url": "https://www.mncvision.id/channel", "icon": "", "utc_offset": "+0700"},
    {"id": "CLTV36.ph", "name": "CLTV36", "url": "https://cltv36.tv/tv-programs/", "icon": "", "utc_offset": "+0800"},
    {"id": "TPChannel1.th", "name": "TP Channel 1", "url": "https://www.tpchannel.org/tv/schedule", "icon": "", "utc_offset": "+0700"},
    {"id": "TPChannel2.th", "name": "TP Channel 2", "url": "https://www.tpchannel.org/tv/schedule", "icon": "", "utc_offset": "+0700"},
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
        sign = -1 if offset_str[0] == '-' else 1
        hours = int(offset_str[1:3])
        return sign * hours
    except Exception:
        return 7

def get_now_in_channel_tz(utc_offset_str):
    hours = parse_offset_hours(utc_offset_str)
    return datetime.now(timezone.utc) + timedelta(hours=hours)

# =========================================================================
# 1. RED BULL TV
# =========================================================================
def fetch_epg_redbull(target):
    epg_id = target["id"]
    programmes = []
    icon = target.get("icon") or get_auto_icon(target["url"])
    channels = [{"id": epg_id, "name": target["name"], "icon": icon}]
    
    try:
        res = HTTP_SESSION.get("https://api.redbull.tv/v3/epg/live", timeout=12)
        if res.status_code == 200:
            data = res.json()
            items = data.get("items", []) or data.get("data", [])
            for item in items:
                title = item.get("title") or item.get("label") or "Red Bull Special"
                desc = item.get("description", f"Show {title} on Red Bull TV")
                start_iso = item.get("start_time") or item.get("startTime")
                end_iso = item.get("end_time") or item.get("endTime")
                
                if start_iso and end_iso:
                    start_dt = datetime.fromisoformat(start_iso.replace('Z', '+00:00'))
                    end_dt = datetime.fromisoformat(end_iso.replace('Z', '+00:00'))
                    programmes.append({
                        "channel": epg_id,
                        "start": format_xmltv_date(start_dt, "+0000"),
                        "stop": format_xmltv_date(end_dt, "+0000"),
                        "title": title,
                        "desc": desc,
                        "lang": "en"
                    })
    except Exception as e:
        print(f"[!] RedBull Error: {e}")

    return channels, programmes

# =========================================================================
# 2. MNC VISION
# =========================================================================
def fetch_single_mnc(args):
    href, raw_name, base_url, today_local, default_icon = args
    programmes = []
    clean_name = re.sub(r'[^a-zA-Z0-9]', '', raw_name)
    if not clean_name:
        return None, []
        
    epg_id = f"{clean_name}.mnc"
    ch_info = {"id": epg_id, "name": f"{raw_name} (MNC)", "icon": default_icon}
    
    try:
        res = HTTP_SESSION.get(urljoin(base_url, href), timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            items = []
            
            for row in soup.find_all(['tr', 'li', 'div']):
                text = row.get_text(strip=True)
                if len(text) > 120: continue
                match = TIME_PATTERN_HM.search(text)
                if match:
                    t_str = match.group(1).replace('.', ':').zfill(5)
                    title = text[match.end():].strip(" -–:\t\n\r[]")
                    if title and len(title) > 2: 
                        items.append((t_str, title))

            today_str = today_local.strftime('%Y-%m-%d')
            for i in range(len(items)):
                t_str, title = items[i]
                start_dt = datetime.strptime(f"{today_str} {t_str}", "%Y-%m-%d %H:%M")
                if i + 1 < len(items):
                    stop_dt = datetime.strptime(f"{today_str} {items[i+1][0]}", "%Y-%m-%d %H:%M")
                    if stop_dt <= start_dt: stop_dt += timedelta(days=1)
                else:
                    stop_dt = start_dt + timedelta(hours=1)

                programmes.append({
                    "channel": epg_id,
                    "start": format_xmltv_date(start_dt, "+0700"),
                    "stop": format_xmltv_date(stop_dt, "+0700"),
                    "title": title,
                    "desc": f"Broadcast of {title} on {raw_name}",
                    "lang": "en"
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
            soup = BeautifulSoup(res.text, 'html.parser')
            links = soup.find_all('a', href=MNC_LINK_PATTERN)
            visited, tasks = set(), []
            
            for l in links:
                href = l.get('href')
                if href in visited: continue
                visited.add(href)
                raw_name = l.get_text(strip=True) or href.split('/')[-1]
                tasks.append((href, raw_name, "https://www.mncvision.id", today_local, default_icon))

            with ThreadPoolExecutor(max_workers=6) as executor:
                results = executor.map(fetch_single_mnc, tasks)

            for ch_info, progs in results:
                if ch_info:
                    channels.append(ch_info)
                    programmes.extend(progs)
    except Exception as e:
        print(f"[!] MNC Error: {e}")
    return channels, programmes

# =========================================================================
# 3. CLTV36
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
            soup = BeautifulSoup(res.text, 'html.parser')
            
            for container in soup.find_all(['div', 'article', 'section']):
                text = container.get_text(" ", strip=True)
                time_matches = TIME_PATTERN_AMPM.findall(text)
                
                if time_matches:
                    title_tag = container.find(['h1', 'h2', 'h3', 'h4', 'h5', 'strong'])
                    if not title_tag: continue
                    title = title_tag.get_text(strip=True)
                    if len(title) < 3 or 'program' in title.lower(): continue

                    try:
                        start_str = time_matches[0].upper().replace(" ", "")
                        start_dt = datetime.combine(today_local.date(), datetime.strptime(start_str.zfill(7), "%I:%M%p").time())
                        
                        if len(time_matches) > 1:
                            end_str = time_matches[1].upper().replace(" ", "")
                            stop_dt = datetime.combine(today_local.date(), datetime.strptime(end_str.zfill(7), "%I:%M%p").time())
                            if stop_dt <= start_dt: stop_dt += timedelta(days=1)
                        else:
                            stop_dt = start_dt + timedelta(hours=1)

                        prog_data = {
                            "channel": epg_id,
                            "start": format_xmltv_date(start_dt, "+0800"),
                            "stop": format_xmltv_date(stop_dt, "+0800"),
                            "title": title,
                            "desc": f"Broadcast of {title} on CLTV36",
                            "lang": "en"
                        }
                        if prog_data not in programmes: programmes.append(prog_data)
                    except Exception: continue
    except Exception as e:
        print(f"[!] CLTV36 Error: {e}")
    return channels, programmes

# =========================================================================
# 4. TPTV THAILAND
# =========================================================================
def fetch_epg_tptv(target):
    epg_id = target["id"]
    programmes = []
    icon = target.get("icon") or get_auto_icon("https://www.tpchannel.org/")
    channels = [{"id": epg_id, "name": target["name"], "icon": icon}]
    
    offset = target.get("utc_offset", "+0700")
    today_local = get_now_in_channel_tz(offset)
    today_str = today_local.strftime('%Y-%m-%d')

    master_type = "2" if "1" in epg_id else "1"
    api_url = f"https://www.tpchannel.org/api/get-by-date?master_type_id={master_type}&date={today_str}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36",
        "Referer": "https://www.tpchannel.org/tv/schedule",
        "X-Requested-With": "XMLHttpRequest"
    }

    try:
        res = HTTP_SESSION.get(api_url, headers=headers, timeout=12)
        items = []
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, dict):
                items = data.get("data", []) or data.get("result", [])
            elif isinstance(data, list):
                items = data

        extracted = []
        for item in items:
            title = item.get("title") or item.get("name") or item.get("program_name")
            t_str = item.get("time") or item.get("start_time") or item.get("schedule_time")
            
            if t_str and title:
                t_clean = t_str.replace(".", ":").strip()[:5].zfill(5)
                extracted.append((t_clean, title.strip()))

        if not extracted:
            web_res = HTTP_SESSION.get("https://www.tpchannel.org/tv/schedule", headers=headers, timeout=12)
            if web_res.status_code == 200:
                soup = BeautifulSoup(web_res.text, 'html.parser')
                for row in soup.find_all(['div', 'li', 'tr']):
                    text = row.get_text(" ", strip=True)
                    match = TIME_PATTERN_HM.search(text)
                    if match:
                        t_clean = match.group(1).replace('.', ':').zfill(5)
                        title_candidate = text[match.end():].strip(" -–:\t\n\r[]u.")
                        if title_candidate and len(title_candidate) > 2 and "ดาวน์โหลด" not in title_candidate:
                            extracted.append((t_clean, title_candidate))

        for i in range(len(extracted)):
            t_str, title = extracted[i]
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
                "desc": f"Program {title} on {target['name']}",
                "lang": "th"
            })
    except Exception as e:
        print(f"[!] TPTV Scraper Error [{target['name']}]: {e}")

    return channels, programmes

# =========================================================================
# 5. QAZAQSTAN NETWORK
# =========================================================================
def fetch_epg_qazaqstan(target):
    epg_id = target["id"]
    icon = target.get("icon") or get_auto_icon(target["url"])
    channels = [{"id": epg_id, "name": target["name"], "icon": icon}]
    
    kz_now = get_now_in_channel_tz("+0500")
    today_str = kz_now.strftime("%Y-%m-%d")
    
    WORKER_PROXY = "https://qazaqstan-playlist.sulthan-pamenan.workers.dev/?url="
    dated_url = f"{target['url'].rstrip('/')}/{today_str}"
    proxied_url = f"{WORKER_PROXY}{quote(dated_url, safe='')}"
    
    raw_progs = []
    try:
        res = HTTP_SESSION.get(proxied_url, timeout=12)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            all_elements = soup.find_all(['span', 'p', 'div', 'h3', 'h4', 'a'])
            
            for i, elem in enumerate(all_elements):
                t_text = elem.get_text(strip=True)
                if TIME_PATTERN_EXACT.match(t_text):
                    time_start = t_text.zfill(5)
                    title_found = ""
                    
                    for j in range(i + 1, min(i + 8, len(all_elements))):
                        candidate = all_elements[j].get_text(strip=True)
                        for ignore_word in IGNORE_WORDS_KZ:
                            candidate = candidate.replace(ignore_word, "").strip()
                            
                        if candidate and len(candidate) > 2 and not TIME_PATTERN_EXACT.match(candidate) and not candidate.startswith("http"):
                            title_found = candidate
                            break
                    
                    if title_found:
                        try:
                            start_dt = datetime.strptime(f"{today_str} {time_start}", "%Y-%m-%d %H:%M")
                            if not any(p["start_dt"] == start_dt for p in raw_progs):
                                raw_progs.append({
                                    "start_dt": start_dt,
                                    "title": title_found,
                                    "desc": f"Program {title_found} di {target['name']}"
                                })
                        except Exception: 
                            continue

            if raw_progs:
                return build_xmltv_programmes(epg_id, target, channels, raw_progs)
    except Exception as e:
        print(f"[!] Scraper Error [{target['name']}]: {e}")

    return auto_scrape_epg(target)

def build_xmltv_programmes(epg_id, target, channels, raw_progs):
    programmes = []
    raw_progs.sort(key=lambda x: x["start_dt"])
    offset = target.get("utc_offset", "+0500")
    
    for i in range(len(raw_progs)):
        curr = raw_progs[i]
        start_dt = curr["start_dt"]
        
        if i + 1 < len(raw_progs):
            stop_dt = raw_progs[i+1]["start_dt"]
            if stop_dt <= start_dt: stop_dt += timedelta(days=1)
        else:
            stop_dt = start_dt + timedelta(hours=1)
            
        programmes.append({
            "channel": epg_id,
            "start": format_xmltv_date(start_dt, offset),
            "stop": format_xmltv_date(stop_dt, offset),
            "title": curr["title"],
            "desc": curr["desc"],
            "lang": "kk"
        })
    return channels, programmes

# =========================================================================
# 6. UNIVERSAL SCRAPER
# =========================================================================
def auto_scrape_epg(target):
    epg_id = target["id"]
    programmes = []
    icon = target.get("icon") or get_auto_icon(target["url"])
    channels = [{"id": epg_id, "name": target["name"], "icon": icon}]
    
    offset = target.get("utc_offset", "+0700")
    today_local = get_now_in_channel_tz(offset)
    today_str = today_local.strftime('%Y-%m-%d')
    
    try:
        res = HTTP_SESSION.get(target["url"], timeout=12)
        soup = BeautifulSoup(res.text, 'html.parser')
        extracted = []

        for element in soup.find_all(['tr', 'li', 'p', 'div']):
            text = element.get_text(strip=True)
            if len(text) > 120: continue
            match = TIME_PATTERN_HM.search(text)
            if match:
                t_str = match.group(1).replace('.', ':').zfill(5)
                title = text[match.end():].strip(" -–:\t\n\r")
                if title and len(title) > 2: extracted.append((t_str, title))

        for i in range(len(extracted)):
            t_str, title = extracted[i]
            try:
                start_dt = datetime.strptime(f"{today_str} {t_str}", "%Y-%m-%d %H:%M")
                if i + 1 < len(extracted):
                    stop_dt = datetime.strptime(f"{today_str} {extracted[i+1][0]}", "%Y-%m-%d %H:%M")
                    if stop_dt <= start_dt: stop_dt += timedelta(days=1)
                else:
                    stop_dt = start_dt + timedelta(hours=1)

                programmes.append({
                    "channel": epg_id,
                    "start": format_xmltv_date(start_dt, offset),
                    "stop": format_xmltv_date(stop_dt, offset),
                    "title": title,
                    "desc": f"Program {title} on {target['name']}",
                    "lang": "en"
                })
            except Exception: continue
    except Exception as e:
        print(f"[!] Universal Scraper Error [{target['name']}]: {e}")

    return channels, programmes

# ROUTER
def process_single_target(target):
    t_url = target["url"].lower()
    t_id = target["id"]
    
    if "tpchannel.org" in t_url or t_id.startswith("TPChannel"):
        return fetch_epg_tptv(target)
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
    tv_elem = ET.Element("tv", {
        "generator-info-name": "Universal IPTV EPG Generator",
        "generator-info-url": "https://github.com/sulthanpamenan"
    })

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
            "channel": prog["channel"]
        })
        t_elem = ET.SubElement(p_elem, "title", lang=prog.get("lang", "en"))
        t_elem.text = prog["title"]
        if prog.get("desc"):
            d_elem = ET.SubElement(p_elem, "desc", lang=prog.get("lang", "en"))
            d_elem.text = prog["desc"]

    ET.indent(tv_elem, space="  ")
    tree = ET.ElementTree(tv_elem)
    tree.write("epg.xml", encoding="utf-8", xml_declaration=True)

    print(f"\n[SUCCESS] `epg.xml` file updated with {len(all_channels)} channels and {len(all_programmes)} programs!")

if __name__ == "__main__":
    generate_xmltv()
