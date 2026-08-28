import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,th;q=0.8,id;q=0.6",
}

TIME_PATTERN_HM = re.compile(r"(\b[0-2]?\d[:.][0-5]\d\b)")
TIME_PATTERN_AMPM = re.compile(r"(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))", re.IGNORECASE)

IGNORE_WORDS_KZ = {
    "LIVE", "ЭФИРДЕ", "Бағдарлама", "Драма", "Көркем фильм", "Телехикая", 
    "Шоу", "Онлайн көру", "Онлайн қарау", "ҚАЗІР ЭФИРДЕ", "ЖАҢA", "ТІКЕЛЕЙ",
    "ТІКЕЛЕЙ ЭФИР", "LIVE NOW", "СЕГОДНЯ", "ТАҢҒЫ", "ТҮСКІ", "КЕШКІ"
}

EPG_TARGET_SOURCES = [
  {"id": "TPChannel.th", "name": "TP Channel", "url": "https://www.tpchannel.org/tv/schedule", "icon": "", "utc_offset": "+0700"},
  
  # RED BULL TV CHANNELS
  {"id": "RedBullTV.global", "name": "Red Bull TV: World of Red Bull", "rrn": "rrn:content:video-channels:c81f8686-ab67-4965-ba04-5f6658bb96cc", "utc_offset": "+0000"},
  {"id": "RedBullPadel.global", "name": "Red Bull TV: Padel", "rrn": "rrn:content:video-channels:e0e6dee0-8c39-4de1-9488-72828468efe0", "utc_offset": "+0000"},
  {"id": "RedBullBike.global", "name": "Red Bull TV: Bike", "rrn": "rrn:content:video-channels:ee30c528-32b1-4604-8976-e3bcee4ae7f0", "utc_offset": "+0000"},
  {"id": "RedBullAdventure.global", "name": "Red Bull TV: Adventure", "rrn": "rrn:content:video-channels:870bcfa8-62b1-4e84-9c85-39f083df368a", "utc_offset": "+0000"},
  {"id": "RedBullMotorsports.global", "name": "Red Bull TV: Motorsports", "rrn": "rrn:content:video-channels:fd4ed3c9-1800-477b-9909-53255da06632", "utc_offset": "+0000"},
  {"id": "RedBullSurfing.global", "name": "Red Bull TV: Surfing", "rrn": "rrn:content:video-channels:2f6afaec-7ade-4fb8-961a-a51aa8279a99", "utc_offset": "+0000"},
  {"id": "RedBullSkateboarding.global", "name": "Red Bull TV: Skateboarding", "rrn": "rrn:content:video-channels:5021f46c-6f34-4f51-ba1f-967f2885ac97", "utc_offset": "+0000"},
  {"id": "RedBullWinter.global", "name": "Red Bull TV: Winter", "rrn": "rrn:content:video-channels:f4aa4fe4-5ce6-4b1c-a60b-abc6f21f16d0", "utc_offset": "+0000"},
  {"id": "RedBullActionReel.global", "name": "Red Bull TV: Action Reel", "rrn": "rrn:content:video-channels:69a66f02-21fd-42a1-be5b-6965541cfe6a", "utc_offset": "+0000"},

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

# =========================================================================
# 1. TP CHANNEL THAILAND
# =========================================================================
def fetch_epg_tpchannel(target):
    epg_id = target["id"]
    programmes = []
    channels = [{"id": epg_id, "name": target["name"]}]
    offset = target.get("utc_offset", "+0700")
    today_local = get_now_in_channel_tz(offset)
    
    date_param = today_local.strftime("%Y-%m-%d")
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
                title_th = item.get("title") or item.get("program_name") or item.get("name") or ""
                subtitle = item.get("subtitle") or item.get("sub_title") or item.get("title_en") or ""
                
                full_title = f"{title_th} {subtitle}".strip() if (title_th and subtitle) else (title_th or subtitle)

                if t_str and full_title:
                    t_str = str(t_str).replace(".", ":").zfill(5)[:5]
                    extracted.append((t_str, clean_text_str(full_title)))

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

    return channels, programmes

# =========================================================================
# 2. RED BULL TV (MULTI-CHANNEL GRAPHQL PARSER)
# =========================================================================
def fetch_epg_redbull(target):
    epg_id = target["id"]
    rrn_id = target["rrn"]
    programmes = []
    channels = [{"id": epg_id, "name": target["name"]}]

    graphql_url = "https://api.redbull.tv/v3/graphql"
    query = """
    query GetLinearEpg($channelId: ID!) {
      linearChannel(id: $channelId) {
        epg {
          items {
            title
            subtitle
            showTitle
            startTime
            endTime
            description
          }
        }
      }
    }
    """
    
    rb_headers = {
        "User-Agent": HEADERS["User-Agent"],
        "Content-Type": "application/json",
        "Accept": "*/*",
    }

    try:
        res = HTTP_SESSION.post(graphql_url, json={"query": query, "variables": {"channelId": rrn_id}}, headers=rb_headers, timeout=12)
        
        if res.status_code != 200:
            rest_url = f"https://tv-api.redbull.com/products/dynamic/v5.2/rbtv/en/id/{rrn_id}"
            res = HTTP_SESSION.get(rest_url, headers=rb_headers, timeout=12)

        if res.status_code == 200:
            data = res.json()
            items = []
            if "data" in data and data["data"].get("linearChannel"):
                items = data["data"]["linearChannel"]["epg"].get("items", [])
            else:
                items = data.get("epg", []) or data.get("schedules", []) or data.get("items", [])

            for item in items:
                main_title = item.get("showTitle") or item.get("title") or item.get("label") or ""
                sub_title = item.get("subtitle") or item.get("subTitle") or ""
                
                if main_title and sub_title and sub_title.lower() not in main_title.lower():
                    full_title = f"{main_title} - {sub_title}"
                else:
                    full_title = main_title or sub_title or "Red Bull TV Special"

                desc = item.get("description") or f"Program {full_title} on {target['name']}"
                
                start_iso = item.get("startTime") or item.get("start_time")
                end_iso = item.get("endTime") or item.get("end_time")

                if start_iso and end_iso:
                    try:
                        start_dt = datetime.fromisoformat(str(start_iso).replace("Z", "+00:00"))
                        end_dt = datetime.fromisoformat(str(end_iso).replace("Z", "+00:00"))

                        programmes.append({
                            "channel": epg_id,
                            "start": format_xmltv_date(start_dt, "+0000"),
                            "stop": format_xmltv_date(end_dt, "+0000"),
                            "title": clean_text_str(full_title),
                            "desc": clean_text_str(desc),
                            "lang": "en",
                        })
                    except Exception:
                        continue
    except Exception as e:
        print(f"[!] RedBullTV Error [{target['name']}]: {e}")

    return channels, programmes

# =========================================================================
# 3. CLTV36
# =========================================================================
def fetch_epg_cltv36(target):
    epg_id = target["id"]
    programmes = []
    channels = [{"id": epg_id, "name": target["name"]}]
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

                        programmes.append({
                            "channel": epg_id,
                            "start": format_xmltv_date(start_dt, "+0800"),
                            "stop": format_xmltv_date(stop_dt, "+0800"),
                            "title": title,
                            "desc": clean_text_str(f"Broadcast of {title} on CLTV36"),
                            "lang": "en",
                        })
                    except Exception:
                        continue
    except Exception as e:
        print(f"[!] CLTV36 Error: {e}")
    return channels, programmes

# =========================================================================
# 4. QAZAQSTAN NETWORK
# =========================================================================
def fetch_epg_qazaqstan(target):
    epg_id = target["id"]
    channels = [{"id": epg_id, "name": target["name"]}]
    programmes = []
    kz_now = get_now_in_channel_tz("+0500")
    today_str = kz_now.strftime("%Y-%m-%d")

    direct_url = f"{target['url'].rstrip('/')}/{today_str}"
    proxy_prefix = "https://iptv-playlist.sulthan-pamenan.workers.dev/?url="
    
    urls_to_try = [f"{proxy_prefix}{quote(direct_url, safe='')}", direct_url]

    for url in urls_to_try:
        try:
            res = HTTP_SESSION.get(url, timeout=15)
            if res.status_code != 200:
                continue

            soup = BeautifulSoup(res.text, "html.parser")
            raw_progs = []

            for element in soup.find_all(["div", "li", "tr"]):
                text = element.get_text(" ", strip=True)
                match = TIME_PATTERN_HM.search(text)
                if match:
                    t_str = match.group(1).replace(".", ":").zfill(5)
                    raw_title = text[match.end():].strip(" -–:\t\n\r")
                    
                    for w in IGNORE_WORDS_KZ:
                        raw_title = raw_title.replace(w, "").strip()
                    
                    title = clean_text_str(raw_title)
                    if title and len(title) >= 2 and not any(r["title"] == title for r in raw_progs):
                        try:
                            start_dt = datetime.strptime(f"{today_str} {t_str}", "%Y-%m-%d %H:%M")
                            raw_progs.append({"start_dt": start_dt, "title": title})
                        except Exception:
                            continue

            if raw_progs:
                raw_progs.sort(key=lambda x: x["start_dt"])
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
                        "start": format_xmltv_date(start_dt, "+0500"),
                        "stop": format_xmltv_date(stop_dt, "+0500"),
                        "title": curr["title"],
                        "desc": clean_text_str(f"Бағдарлама {curr['title']} - {target['name']}"),
                        "lang": "kk",
                    })
                break
        except Exception:
            continue

    return channels, programmes

# ROUTER
def process_single_target(target):
    t_id = target["id"]

    if "rrn" in target:
        return fetch_epg_redbull(target)
    elif t_id == "TPChannel.th":
        return fetch_epg_tpchannel(target)
    elif t_id == "CLTV36.ph":
        return fetch_epg_cltv36(target)
    elif t_id.endswith(".kz"):
        return fetch_epg_qazaqstan(target)
    else:
        return fetch_epg_tpchannel(target)

# MAIN LOGIC
def generate_xmltv():
    print("[*] Starting EPG scraping...")
    tv_elem = ET.Element("tv", {"generator-info-name": "Universal IPTV EPG Generator", "generator-info-url": "https://github.com/sulthanpamenan"})

    all_channels = []
    all_programmes = []

    with ThreadPoolExecutor(max_workers=8) as executor:
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
        if prog.get("desc"):
            d_elem = ET.SubElement(p_elem, "desc", lang=prog.get("lang", "en"))
            d_elem.text = prog["desc"]

    ET.indent(tv_elem, space=" ")
    tree = ET.ElementTree(tv_elem)
    tree.write("epg.xml", encoding="utf-8", xml_declaration=True)

    print(f"\n[SUCCESS] `epg.xml` file updated with {len(all_channels)} channels and {len(all_programmes)} programs!")

if __name__ == "__main__":
    generate_xmltv()
