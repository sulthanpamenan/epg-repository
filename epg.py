import base64
import html
import json
import re
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from bs4 import BeautifulSoup
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
}

TIME_PATTERN_HM = re.compile(r"(\b[0-2]?\d[:.][0-5]\d\b)")
TIME_PATTERN_AMPM = re.compile(r"(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))", re.IGNORECASE)

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

    # 3. CLTV36 PHILIPPINES
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
retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
adapter = HTTPAdapter(max_retries=retries, pool_connections=50, pool_maxsize=50)
HTTP_SESSION.mount("https://", adapter)
HTTP_SESSION.mount("http://", adapter)
HTTP_SESSION.headers.update(HEADERS)

def format_xmltv_date(dt_obj, utc_offset="+0700"):
    return dt_obj.strftime(f"%Y%m%d%H%M%S {utc_offset}")

def get_now_in_channel_tz(offset_str):
    sign = -1 if offset_str[0] == "-" else 1
    hours = int(offset_str[1:3])
    return datetime.now(timezone.utc) + timedelta(hours=sign * hours)

def clean_text_str(val):
    if not val: return ""
    text = str(val).replace("\xa0", " ")
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", " ", text).strip()
    return re.sub(r"\s+", " ", text)

def decode_base64_json(data_b64):
    try:
        decoded_bytes = base64.b64decode(data_b64)
        return json.loads(decoded_bytes.decode('utf-8'))
    except Exception:
        return None

def parse_cltv36_day_matches(day_text, target_weekday_name, is_weekend):
    dt, t_day = day_text.upper(), target_weekday_name.upper()
    if t_day in dt or "DAILY" in dt: return True
    if ("MONDAY - FRIDAY" in dt or "MON - FRI" in dt or "MONDAY – FRIDAY" in dt) and not is_weekend: return True
    if ("MONDAY - SATURDAY" in dt or "MONDAY – SATURDAY" in dt) and t_day != "SUNDAY": return True
    return False

# --- 1. TIVIE.ID MODULE ---
TIVIE_MASTER_FALLBACK = [
    {"id": "antv", "name": "ANTV"}, {"id": "btv", "name": "BTV"},
    {"id": "cnnindonesia", "name": "CNN Indonesia"}, {"id": "garudatv", "name": "Garuda TV"},
    {"id": "gtv", "name": "GTV"}, {"id": "indosiar", "name": "Indosiar"},
    {"id": "inews", "name": "iNews"}, {"id": "kompastv", "name": "Kompas TV"},
    {"id": "mdtv", "name": "MDTV"}, {"id": "mentaritv", "name": "Mentari TV"},
    {"id": "metrotv", "name": "Metro TV"}, {"id": "mnctv", "name": "MNC TV"},
    {"id": "moji", "name": "MOJI"}, {"id": "nusantaratv", "name": "Nusantara TV"},
    {"id": "rcti", "name": "RCTI"}, {"id": "rtv", "name": "RTV"},
    {"id": "sctv", "name": "SCTV"}, {"id": "sinpotv", "name": "Sin Po TV"},
    {"id": "transtv", "name": "Trans TV"}, {"id": "trans7", "name": "Trans 7"},
    {"id": "tvone", "name": "tvOne"}, {"id": "tvri", "name": "TVRI"},
    {"id": "vtv", "name": "VTV"}, {"id": "sindonews", "name": "Sindonews TV"}
]

def discover_tivie_channels():
    channels, added_ids = [], set()
    for m_ch in TIVIE_MASTER_FALLBACK:
        if m_ch["id"] not in added_ids:
            added_ids.add(m_ch["id"])
            channels.append({
                "id": f"Tivie_{m_ch['id']}.id",
                "real_id": m_ch["id"],
                "name": m_ch["name"]
            })
    return channels

CF_WORKER_URL = "https://tivie-proxy.sulthan-pamenan.workers.dev"

def scrape_single_tivie_channel(ch):
    ch_id, real_id, ch_name = ch["id"], ch["real_id"], ch["name"]
    url = f"{CF_WORKER_URL}/channel/{real_id}"
    programmes = []
    wib_tz = timezone(timedelta(hours=7))
    today_wib = datetime.now(timezone.utc).astimezone(wib_tz).date()

    raw_list = []
    try:
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'id,en-US;q=0.9,en-US;q=0.8',
            }
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            if response.status == 200:
                html_content = response.read().decode('utf-8')
                soup = BeautifulSoup(html_content, 'html.parser')
                
                for unwanted in soup.select("footer, .footer, script, style, .ads, .cookie-banner"):
                    unwanted.decompose()

                event_items = soup.select("li[id^='event-']")
                if not event_items:
                    event_items = [li for li in soup.find_all("li") if TIME_PATTERN_HM.search(li.get_text())]

                for item in event_items:
                    full_text = item.get_text(" ", strip=True)
                    time_match = TIME_PATTERN_HM.search(full_text)
                    if not time_match:
                        continue
                    t_str = time_match.group(1).replace(".", ":").zfill(5)[:5]

                    cat_div = item.select_one("div.text-sm.tracking-wide")
                    cat_str = clean_text_str(cat_div.get_text()) if cat_div else ""

                    h_elem = item.select_one("h5, h4")
                    prog_title = ""
                    if h_elem:
                        h_clone = BeautifulSoup(str(h_elem), 'html.parser')
                        for sub in h_clone.select("div.text-sm.tracking-wide, span.sr-only"):
                            sub.decompose()
                        texts = [clean_text_str(t) for t in h_clone.stripped_strings if t not in ["WIB", "LIVE"]]
                        texts = [t for t in texts if t != cat_str]
                        prog_title = " ".join(texts) if texts else ""

                    if not prog_title and cat_str:
                        prog_title = cat_str
                        cat_str = ""

                    if not prog_title:
                        continue

                    title = prog_title
                    category = cat_str if cat_str else "General"

                    if not any(p['time'] == t_str and p['title'] == title for p in raw_list):
                        raw_list.append({
                            "time": t_str,
                            "title": title,
                            "desc": "",
                            "category": category
                        })

        for idx in range(len(raw_list)):
            curr = raw_list[idx]
            t_str = curr['time']
            start_dt = datetime.strptime(f"{today_wib} {t_str}", "%Y-%m-%d %H:%M").replace(tzinfo=wib_tz)
            if idx < len(raw_list) - 1:
                stop_time_str = raw_list[idx + 1]['time']
                stop_dt = datetime.strptime(f"{today_wib} {stop_time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=wib_tz)
                if stop_dt <= start_dt: 
                    stop_dt += timedelta(days=1)
            else:
                stop_dt = start_dt + timedelta(hours=1)

            programmes.append({
                "channel": ch_id,
                "start": format_xmltv_date(start_dt, "+0700"),
                "stop": format_xmltv_date(stop_dt, "+0700"),
                "title": curr["title"],
                "desc": curr["desc"],
                "category": curr["category"],
                "lang": "id"
            })
            
        if programmes:
            print(f"[✓] Tivie.id [{ch_name}]: Loaded full schedule -> {len(programmes)} programs found.")
    except Exception as e:
        print(f"[!] Tivie Error [{ch_name}]: {e}")

    return {"id": ch_id, "name": ch_name}, programmes

def fetch_all_tivie_parallel():
    channels = discover_tivie_channels()
    print(f"[*] Starting parallel EPG extraction for {len(channels)} Tivie.id channels...")
    all_channels, all_programmes = [], []

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = executor.map(scrape_single_tivie_channel, channels)
        for ch_info, progs in results:
            if progs:
                all_channels.append(ch_info)
                all_programmes.extend(progs)

    print(f"[✓] Tivie.id: Successfully extracted {len(all_channels)} active channels & {len(all_programmes)} programs!")
    return all_channels, all_programmes

# --- 2. DENS.TV MODULE ---
def get_official_dens_channels():
    return [
        {"id_num": "3", "slug": "live-streaming-1", "id": "Dens_live-streaming-1.id", "name": "Live Streaming 1", "cat": "tv-local"},
        {"id_num": "107", "slug": "densplay", "id": "Dens_densplay.id", "name": "DensPlay", "cat": "tv-local"},
        {"id_num": "42", "slug": "denslifestyle", "id": "Dens_denslifestyle.id", "name": "Dens Lifestyle", "cat": "tv-local"},
        {"id_num": "117", "slug": "densfood-channel", "id": "Dens_densfood-channel.id", "name": "Dens Food Channel", "cat": "tv-local"},
        {"id_num": "102", "slug": "densshowbiz", "id": "Dens_densshowbiz.id", "name": "Dens ShowBiz", "cat": "tv-local"},
        {"id_num": "1", "slug": "densknowledge", "id": "Dens_densknowledge.id", "name": "Dens Knowledge", "cat": "tv-local"},
        {"id_num": "137", "slug": "channel-jowo", "id": "Dens_channel-jowo.id", "name": "Channel Jowo", "cat": "tv-local"},
        {"id_num": "131", "slug": "berita-satu", "id": "Dens_berita-satu.id", "name": "BeritaSatu World", "cat": "tv-local"},
        {"id_num": "94", "slug": "elshinta-tv", "id": "Dens_elshinta-tv.id", "name": "Elshinta TV", "cat": "tv-local"},
        {"id_num": "122", "slug": "magna-channel", "id": "Dens_magna-channel.id", "name": "Magna Channel", "cat": "tv-local"},
        {"id_num": "118", "slug": "tvri-sport", "id": "Dens_tvri-sport.id", "name": "TVRI Sport", "cat": "tv-local"},
        {"id_num": "112", "slug": "jak-tv", "id": "Dens_jak-tv.id", "name": "Jak TV", "cat": "tv-local"},
        {"id_num": "21", "slug": "rodjatv", "id": "Dens_rodjatv.id", "name": "Rodja TV", "cat": "tv-local"},
        {"id_num": "23", "slug": "daai-tv", "id": "Dens_daai-tv.id", "name": "DAAI TV", "cat": "tv-local"},
        {"id_num": "92", "slug": "my-cinema-europe-hd", "id": "Dens_my-cinema-europe-hd.id", "name": "My Cinema Europe", "cat": "tv-premium"},
        {"id_num": "127", "slug": "crema-tv", "id": "Dens_crema-tv.id", "name": "Crema TV", "cat": "tv-premium"},
        {"id_num": "143", "slug": "qwest-tv", "id": "Dens_qwest-tv.id", "name": "Qwest TV", "cat": "tv-premium"},
        {"id_num": "128", "slug": "stingray-classica", "id": "Dens_stingray-classica.id", "name": "Stingray Classica", "cat": "tv-premium"},
        {"id_num": "130", "slug": "dance-tv", "id": "Dens_dance-tv.id", "name": "Dance TV", "cat": "tv-premium"},
        {"id_num": "98", "slug": "motorvision", "id": "Dens_motorvision.id", "name": "Motorvision+", "cat": "tv-premium"},
        {"id_num": "61", "slug": "cna", "id": "Dens_cna.id", "name": "CNA", "cat": "tv-international"},
        {"id_num": "77", "slug": "nhk-world-japan", "id": "Dens_nhk-world-japan.id", "name": "NHK World Japan", "cat": "tv-international"},
        {"id_num": "56", "slug": "al-jazeera-english", "id": "Dens_al-jazeera-english.id", "name": "Al Jazeera English", "cat": "tv-international"},
        {"id_num": "41", "slug": "trt-world", "id": "Dens_trt-world.id", "name": "TRT World", "cat": "tv-international"},
        {"id_num": "144", "slug": "russia-today-rt", "id": "Dens_russia-today-rt.id", "name": "RT News", "cat": "tv-international"},
        {"id_num": "79", "slug": "wion", "id": "Dens_wion.id", "name": "WION", "cat": "tv-international"},
        {"id_num": "104", "slug": "freedom", "id": "Dens_freedom.id", "name": "FreeDOM", "cat": "tv-international"},
        {"id_num": "27", "slug": "al-jazeera-arabic", "id": "Dens_al-jazeera-arabic.id", "name": "Al Jazeera Arabic", "cat": "tv-international"},
        {"id_num": "85", "slug": "cctv-4", "id": "Dens_cctv-4.id", "name": "CCTV-4", "cat": "tv-international"},
        {"id_num": "69", "slug": "france-24", "id": "Dens_france-24.id", "name": "France 24", "cat": "tv-international"},
        {"id_num": "90", "slug": "tv5monde-asie", "id": "Dens_tv5monde-asie.id", "name": "TV5Monde Asie", "cat": "tv-international"},
        {"id_num": "81", "slug": "dw-tv", "id": "Dens_dw-tv.id", "name": "DW TV", "cat": "tv-international"},
        {"id_num": "132", "slug": "dim-tv", "id": "Dens_dim-tv.id", "name": "DIM TV", "cat": "tv-international"},
        {"id_num": "16", "slug": "cgtn-documentary", "id": "Dens_cgtn-documentary.id", "name": "CGTN Documentary", "cat": "tv-international"},
        {"id_num": "78", "slug": "tbn", "id": "Dens_tbn.id", "name": "TBN", "cat": "tv-international"},
        {"id_num": "88", "slug": "sunna-tv", "id": "Dens_sunna-tv.id", "name": "Saudi Sunnah TV", "cat": "tv-international"},
        {"id_num": "139", "slug": "wedotvmovies", "id": "Dens_wedotvmovies.id", "name": "wedo Movies", "cat": "tv-free-streaming"},
        {"id_num": "142", "slug": "wedotvamor", "id": "Dens_wedotvamor.id", "name": "wedo Amor", "cat": "tv-free-streaming"},
        {"id_num": "140", "slug": "wedotvbig-stories", "id": "Dens_wedotvbig-stories.id", "name": "wedo Big Stories", "cat": "tv-free-streaming"},
        {"id_num": "141", "slug": "wedosports", "id": "Dens_wedosports.id", "name": "wedoSports", "cat": "tv-free-streaming"}
    ]

def fetch_single_dens_channel(channel_info):
    programmes = []
    wib_tz = timezone(timedelta(hours=7))
    
    primary_cat = channel_info.get('cat', 'tv-local')
    url = f"https://www.dens.tv/{primary_cat}/watch/{channel_info['id_num']}/{channel_info['slug']}"
    
    try:
        res = HTTP_SESSION.get(url, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            epg_list = []

            for script in soup.find_all("script"):
                if script.string and "tvEpg" in script.string:
                    matches = re.findall(r"(tvEpg\w*)\s*=\s*(\[.*?\]);", script.string)
                    for _, json_str in matches:
                        try:
                            parsed_data = json.loads(json_str)
                            if isinstance(parsed_data, list):
                                epg_list.extend(parsed_data)
                        except json.JSONDecodeError:
                            continue

            raw_progs = []
            for item in epg_list:
                title = item.get("title")
                desc = item.get("description") or ""
                start_time_str = item.get("start_time")

                if start_time_str and title:
                    try:
                        start_dt = datetime.strptime(str(start_time_str).strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=wib_tz)
                        raw_progs.append({
                            "start_dt": start_dt, 
                            "title": clean_text_str(title), 
                            "desc": clean_text_str(desc)
                        })
                    except ValueError:
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

                    programmes.append({
                        "channel": channel_info["id"],
                        "start": format_xmltv_date(start_dt, "+0700"),
                        "stop": format_xmltv_date(stop_dt, "+0700"),
                        "title": curr["title"],
                        "desc": curr["desc"],
                        "lang": "id"
                    })
                print(f"[✓] Dens.TV [{channel_info['name']}]: Loaded {len(programmes)} programs!")
    except Exception: 
        pass
        
    return channel_info, programmes

def fetch_all_dens_parallel():
    channels_list = get_official_dens_channels()
    print(f"[*] Starting parallel EPG extraction for {len(channels_list)} Dens.TV channels...")
    all_channels, all_programmes = [], []

    with ThreadPoolExecutor(max_workers=9) as executor:
        results = executor.map(fetch_single_dens_channel, channels_list)
        for ch_info, progs in results:
            if progs:
                all_channels.append({"id": ch_info["id"], "name": ch_info["name"]})
                all_programmes.extend(progs)

    print(f"[✓] Dens.TV: Successfully extracted {len(all_channels)} active channels & {len(all_programmes)} programs!")
    return all_channels, all_programmes

# --- 3. TP CHANNEL ---
def fetch_epg_tpchannel(target):
    epg_id, offset = target["id"], target.get("utc_offset", "+0700")
    channels = [{"id": epg_id, "name": target["name"]}]
    programmes = []
    
    today_local = get_now_in_channel_tz(offset)
    date_param = f"{today_local.year + 543}-{today_local.strftime('%m-%d')}"
    today_str = today_local.strftime("%Y-%m-%d")

    api_url = f"https://www.tpchannel.org/tv/schedule/get-by-date?master_type_id=2&date={date_param}"
    try:
        res = HTTP_SESSION.get(api_url, headers={"X-Requested-With": "XMLHttpRequest", "Referer": target["url"]}, timeout=12)
        if res.status_code == 200:
            data = res.json()
            
            items = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = data.get("data", []) or data.get("result", [])
            
            extracted = []
            for item in items:
                t_raw = item.get("starttime") or item.get("time")
                title = item.get("title_th") or item.get("title") or item.get("program_name")
                
                if t_raw and title:
                    t_str = str(t_raw).strip()
                    if len(t_str) >= 5:
                        clean_time = t_str.replace(".", ":")[:5]
                        if re.match(r'^\d{2}:\d{2}$', clean_time):
                            extracted.append((clean_time, clean_text_str(title)))
                            continue
                    
                    match = TIME_PATTERN_HM.search(t_str)
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
                        
                    programmes.append({
                        "channel": epg_id, 
                        "start": format_xmltv_date(start_dt, offset), 
                        "stop": format_xmltv_date(stop_dt, offset), 
                        "title": title, 
                        "desc": "", 
                        "lang": "th"
                    })
                except Exception: 
                    continue
                    
            print(f"[✓] TP Channel: Successfully loaded {len(programmes)} programs!")
    except Exception as e: 
        print(f"[!] TP Channel Error: {e}")
        
    return channels, programmes

# --- 4. CLTV36 ---
def fetch_epg_cltv36(target):
    epg_id, offset = target["id"], target.get("utc_offset", "+0800")
    channels = [{"id": epg_id, "name": target["name"]}]
    programmes = []
    today_local = get_now_in_channel_tz(offset)
    today_name, is_weekend = today_local.strftime("%A"), today_local.weekday() >= 5

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
                            
                            start_dt = datetime.combine(today_local.date(), start_time)
                            stop_dt = datetime.combine(today_local.date(), stop_time)
                            
                            if stop_dt <= start_dt: 
                                stop_dt += timedelta(days=1)
                                
                            programmes.append({
                                "channel": epg_id, 
                                "start": format_xmltv_date(start_dt, offset), 
                                "stop": format_xmltv_date(stop_dt, offset), 
                                "title": title, 
                                "desc": desc_text, 
                                "lang": "en"
                            })
                        except Exception: 
                            continue
            print(f"[✓] CLTV36: Successfully loaded {len(programmes)} programs!")
    except Exception as e: 
        print(f"[!] CLTV36 Error: {e}")
        
    return channels, programmes

# --- 5. MNC VISION ---
def get_mnc_channel_options():
    url = "https://www.mncvision.id/schedule/table"
    EXCLUDED_MNC_IDS = {
        "78", "80", "81", "82", "83", "84", "87", "89", "97", "103", "106", "107", "110", "113", "115", "116",
        "118", "205", "330", "331", "352", "355", "357", "430", "431", "432", "433", "434", "437", "438"
    }
    
    channels = []
    try:
        res = HTTP_SESSION.get(url, timeout=25)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            select = soup.find("select", {"name": "fchannel"}) or soup.find("select", {"id": "fchannel"})
            if select:
                for opt in select.find_all("option"):
                    val = opt.get("value")
                    raw_name = clean_text_str(opt.get_text())
                    if val and str(val) != "0" and raw_name and "Pilih Channel" not in raw_name and "Toggle" not in raw_name:
                        if str(val) in EXCLUDED_MNC_IDS:
                            continue

                        clean_channel_name = re.sub(r"\s*-\s*\[.*?\]", "", raw_name).strip()
                        slug = re.sub(r"[-\s]+", "-", re.sub(r"[^\w\s-]", "", clean_channel_name.lower().strip()))
                        slug_id = f"MNC_{slug}_{val}.id"

                        channels.append({
                            "code": str(val),
                            "clean_name": clean_channel_name,
                            "slug_id": slug_id,
                        })
    except Exception as e:
        print(f"[!] Failed to retrieve the channel list: {e}")
    return channels

def fetch_single_mnc_epg(ch_info):
    today_str = get_now_in_channel_tz("+0700").strftime("%Y-%m-%d")
    mnc_headers = {
        "User-Agent": HEADERS["User-Agent"],
        "Origin": "https://www.mncvision.id",
        "Referer": "https://www.mncvision.id/schedule/table",
    }

    programmes = []
    seen_prog_keys = set()
    ch_id = ch_info["slug_id"]
    ch_name = ch_info["clean_name"]
    
    local_session = requests.Session()
    local_session.headers.update(HEADERS)

    for startno in [0, 50, 100]:
        try:
            if startno == 0:
                post_url = "https://www.mncvision.id/schedule/table"
                payload = {
                    "search_model": "channel",
                    "af0rmelement": "aformelement",
                    "fdate": today_str,
                    "fchannel": ch_info["code"],
                    "submit": "Cari"
                }
                res = HTTP_SESSION.post(post_url, data=payload, headers=mnc_headers, timeout=35)
            else:
                get_url = f"https://www.mncvision.id/schedule/table/startno/{startno}"
                res = local_session.get(get_url, headers=mnc_headers, timeout=25)

            if res.status_code != 200:
                break

            soup = BeautifulSoup(res.text, "html.parser")
            table = soup.find("table", class_=re.compile(r"table", re.I)) or soup.find("table")
            
            if not table:
                break

            rows = table.find_all("tr")[1:]
            if not rows:
                break
            
            for row in rows:
                cols = row.find_all(["td", "th"])
                if len(cols) >= 2:
                    time_str = clean_text_str(cols[0].get_text())
                    title_str = clean_text_str(cols[1].get_text())
                    duration_str = clean_text_str(cols[2].get_text()) if len(cols) >= 3 else ""

                    if time_str and title_str and "Toggle navigation" not in title_str and "Jadwal Tidak Ditemukan" not in title_str:
                        match = TIME_PATTERN_HM.search(time_str)
                        if match:
                            t_clean = match.group(1).replace(".", ":").zfill(5)[:5]
                            try:
                                start_dt = datetime.strptime(f"{today_str} {t_clean}", "%Y-%m-%d %H:%M")
                                stop_dt = start_dt + timedelta(hours=1)
                                dur_match = re.search(r"(\d{2}):(\d{2})", duration_str)
                                if dur_match:
                                    h_dur, m_dur = int(dur_match.group(1)), int(dur_match.group(2))
                                    stop_dt = start_dt + timedelta(hours=h_dur, minutes=m_dur)
                                    if stop_dt <= start_dt:
                                        stop_dt += timedelta(days=1)

                                start_formatted = format_xmltv_date(start_dt, "+0700")
                                unique_key = (start_formatted, title_str)

                                if unique_key not in seen_prog_keys:
                                    seen_prog_keys.add(unique_key)
                                    programmes.append({
                                        "channel": ch_id,
                                        "start": start_formatted,
                                        "stop": format_xmltv_date(stop_dt, "+0700"),
                                        "title": title_str,
                                        "desc": "",
                                        "lang": "id"
                                    })
                            except Exception:
                                continue

            if len(rows) < 50:
                break

        except Exception:
            break

    if programmes:
        print(f"[✓] MNC Vision [{ch_name}]: Loaded {len(programmes)} programs total!")
        return [{"id": ch_id, "name": ch_name}], programmes

    return [], []

def fetch_all_mncvision_parallel():
    channels_list = get_mnc_channel_options()
    if not channels_list:
        return [], []

    print(f"[*] Starting precision extraction for {len(channels_list)} MNC Vision channels...")
    all_channels, all_programmes = [], []
    with ThreadPoolExecutor(max_workers=20) as executor:
        results = executor.map(fetch_single_mnc_epg, channels_list)
        for ch_list, progs in results:
            if progs:
                all_channels.extend(ch_list)
                all_programmes.extend(progs)

    print(f"[✓] MNC Vision: Successfully extracted {len(all_channels)} active channels & {len(all_programmes)} programs!")
    return all_channels, all_programmes

# --- 6. QAZAQSTAN NETWORK ---
def fetch_epg_qazaqstan(target):
    epg_id, offset = target["id"], target.get("utc_offset", "+0500")
    channels = [{"id": epg_id, "name": target["name"]}]
    programmes = []
    today_str = get_now_in_channel_tz(offset).strftime("%Y-%m-%d")
    base_url = target['url'].rstrip('/')
    direct_url = f"{base_url}/{today_str}" if not base_url.endswith(today_str) else base_url

    for url in [direct_url, f"https://iptv-playlist.sulthan-pamenan.workers.dev/?url={quote(direct_url, safe='')}"]:
        try:
            res = HTTP_SESSION.get(url, timeout=15)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, "html.parser")
            
            items = soup.select("div.flex.items-center.justify-between.w-full, .program-item")
            
            raw_progs = []
            for item in items:
                time_elem = item.select_one(".font-bold.text-h5, [class*='text-h5'], [class*='font-bold']")
                time_text = time_elem.get_text(strip=True) if time_elem else ""
                
                match = TIME_PATTERN_HM.search(time_text) or TIME_PATTERN_HM.search(item.get_text(" ", strip=True))
                if match:
                    t_str = match.group(1).replace(".", ":").zfill(5)[:5]
                    
                    category_elem = item.select_one("div.text-xs, [class*='text-xs']")
                    title_elem = item.select_one(".program-title, [class*='program-title']")
                    
                    cat_text = clean_text_str(category_elem.get_text(strip=True)) if category_elem else ""
                    title_text = clean_text_str(title_elem.get_text(strip=True)) if title_elem else ""
                    
                    genre_keywords = [
                        "деректі фильм", "деректі фильмдер", "телехикая", "телехикаялар", "бағдарлама", "бағдарламалар", "мультхикая", 
                        "мультхикаялар", "мегажоба", "мегажобалар", "көркем фильм", "көркем фильмдер", "ақпараттық-саяси бағдарлама"
                    ]
                    
                    if any(kw in title_text.lower() for kw in genre_keywords) and not any(kw in cat_text.lower() for kw in genre_keywords):
                        category = title_text
                        raw_title = cat_text
                    else:
                        category = cat_text
                        raw_title = title_text
                        
                    if not raw_title:
                        bold_elems = item.select("div.font-bold, [class*='font-bold']")
                        for b in bold_elems:
                            b_text = b.get_text(strip=True)
                            if b_text and not TIME_PATTERN_HM.search(b_text) and b_text != category:
                                raw_title = b_text
                                break

                    clean_title = re.sub(r"^[–\-\:\s\.\,]+|[–\-\:\s\.\,]+$", "", raw_title)
                    clean_title = re.sub(r"(онлайн көру|live|эфирде)", "", clean_title, flags=re.IGNORECASE)
                    clean_title = clean_text_str(clean_title)

                    if clean_title and len(clean_title) >= 2 and not TIME_PATTERN_HM.match(clean_title):
                        if not any(r["start_str"] == t_str and r["title"] == clean_title for r in raw_progs):
                            if category and category != clean_title:
                                desc_text = category
                            else:
                                desc_text = ""
                                
                            raw_progs.append({
                                "start_str": t_str,
                                "title": clean_title,
                                "desc": desc_text
                            })

            if raw_progs:
                for i in range(len(raw_progs)):
                    curr = raw_progs[i]
                    t_str = curr["start_str"]
                    try:
                        start_dt = datetime.strptime(f"{today_str} {t_str}", "%Y-%m-%d %H:%M")
                        if i + 1 < len(raw_progs):
                            stop_dt = datetime.strptime(f"{today_str} {raw_progs[i+1]['start_str']}", "%Y-%m-%d %H:%M")
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
                            "lang": "kk"
                        })
                    except Exception:
                        continue
                print(f"[✓] {target['name']}: Successfully extracted {len(programmes)} valid programs!")
                break
        except Exception:
            continue

    return channels, programmes

# --- 7. RED BULL TV ---
def fetch_single_redbull_channel(t):
    api_url = f"https://tv-api.redbull.com/guides/v5.1/rbtv/id_ID/id/{t['rrn']}"
    programmes = []
    try:
        res = HTTP_SESSION.get(api_url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            cards = data.get("cards", [])
            for item in cards:
                title = item.get("title")
                desc = item.get("short_description") or item.get("long_description") or ""
                start_iso = item.get("start_time")
                end_iso = item.get("end_time")

                if start_iso and title:
                    start_dt = datetime.fromisoformat(str(start_iso).replace("Z", "+00:00"))
                    end_dt = datetime.fromisoformat(str(end_iso).replace("Z", "+00:00")) if end_iso else start_dt + timedelta(hours=1)

                    programmes.append({
                        "channel": t["id"], 
                        "start": format_xmltv_date(start_dt, "+0000"), 
                        "stop": format_xmltv_date(end_dt, "+0000"), 
                        "title": clean_text_str(title), 
                        "desc": clean_text_str(desc), 
                        "lang": "en"
                    })
            print(f"[✓] Red Bull TV [{t['name']}]: Loaded {len(programmes)} programs successfully!")
    except Exception as e:
        print(f"[!] Red Bull TV Error [{t['name']}]: {e}")
    return {"id": t["id"], "name": t["name"]}, programmes

def fetch_epg_redbull_all(targets):
    channels = []
    all_programmes = []
    with ThreadPoolExecutor(max_workers=9) as executor:
        results = executor.map(fetch_single_redbull_channel, targets)
        for ch_info, progs in results:
            if progs:
                channels.append(ch_info)
                all_programmes.extend(progs)
    return channels, all_programmes

# --- ROUTER & EXECUTION ---
def process_single_target(target):
    t_id = target["id"]
    if t_id == "TPChannel.th": return fetch_epg_tpchannel(target)
    elif t_id == "CLTV36.ph": return fetch_epg_cltv36(target)
    elif t_id.endswith(".kz"): return fetch_epg_qazaqstan(target)
    return [], []

def generate_xmltv():
    print("=" * 60)
    print("[*] Starting EPG XMLTV Generation")
    print("=" * 60)
    
    tv_elem = ET.Element("tv", {"generator-info-name": "Universal Master EPG Generator"})
    all_channels, all_programmes = [], []

    # 1. Fetch Tivie.id Channels
    tivie_channels, tivie_programmes = fetch_all_tivie_parallel()
    all_channels.extend(tivie_channels)
    all_programmes.extend(tivie_programmes)

    # 2. Fetch Dens.TV Channels
    dens_channels, dens_programmes = fetch_all_dens_parallel()
    all_channels.extend(dens_channels)
    all_programmes.extend(dens_programmes)

    # 3. Fetch Red Bull TV
    redbull_targets = [t for t in EPG_TARGET_SOURCES if "rrn" in t]
    if redbull_targets:
        rb_channels, rb_programmes = fetch_epg_redbull_all(redbull_targets)
        all_channels.extend(rb_channels)
        all_programmes.extend(rb_programmes)

    # 4. MNC Vision Mass Precision Scan
    mnc_channels, mnc_programmes = fetch_all_mncvision_parallel()
    all_channels.extend(mnc_channels)
    all_programmes.extend(mnc_programmes)

    # 5. Fetch Other Sources (TP Channel, CLTV36, Qazaqstan Network)
    other_targets = [t for t in EPG_TARGET_SOURCES if "rrn" not in t]
    with ThreadPoolExecutor(max_workers=9) as executor:
        for ch_list, progs in executor.map(process_single_target, other_targets):
            all_channels.extend(ch_list)
            all_programmes.extend(progs)

    # 6. Write Channels to XML Element (Deduplicated)
    seen_channels = set()
    for ch in all_channels:
        if ch["id"] not in seen_channels:
            seen_channels.add(ch["id"])
            c_elem = ET.SubElement(tv_elem, "channel", id=ch["id"])
            ET.SubElement(c_elem, "display-name").text = ch["name"]

    # 7. Write Programs & Deduplicate
    seen_programmes = set()
    for p in all_programmes:
        key = (p["channel"], p["start"])
        if key not in seen_programmes:
            seen_programmes.add(key)
            p_elem = ET.SubElement(tv_elem, "programme", {"start": p["start"], "stop": p["stop"], "channel": p["channel"]})
            
            title_val = str(p["title"]) if not isinstance(p["title"], (set, list, dict)) else " ".join(p["title"])
            cleaned_title = html.unescape(clean_text_str(title_val))
            ET.SubElement(p_elem, "title", lang=p.get("lang", "en")).text = cleaned_title
            
            if p.get("desc") and str(p["desc"]).strip():
                desc_val = str(p["desc"]) if not isinstance(p["desc"], (set, list, dict)) else " ".join(p["desc"])
                cleaned_desc = html.unescape(clean_text_str(desc_val))
                ET.SubElement(p_elem, "desc", lang=p.get("lang", "en")).text = cleaned_desc

            if p.get("category") and str(p["category"]).strip() and p.get("category") != "General":
                cat_val = str(p["category"])
                ET.SubElement(p_elem, "category", lang=p.get("lang", "en")).text = html.unescape(clean_text_str(cat_val))

    try:
        ET.indent(tv_elem, space="  ")
    except AttributeError: 
        pass

    ET.ElementTree(tv_elem).write("epg.xml", encoding="utf-8", xml_declaration=True)
    print("=" * 60)
    print(f"[SUCCESS] Successfully generated `epg.xml` with {len(seen_channels)} total channels & {len(seen_programmes)} programs!")
    print("=" * 60)

if __name__ == "__main__":
    generate_xmltv()
