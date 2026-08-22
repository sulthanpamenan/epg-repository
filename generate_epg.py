import sys
import os
import re
import time
import random
import requests
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
from xml.dom import minidom
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor

EPG_TARGET_SOURCES = [
    {
        "id": "PadangTV.id",
        "name": "Padang TV",
        "url": "https://padangtv.id/schedule/",
        "icon": "",
        "utc_offset": "+0700"
    },
    {
        "id": "RedBullTV.global",
        "name": "Red Bull TV",
        "url": "https://www.redbull.tv/en/epg",
        "icon": "https://www.google.com/s2/favicons?domain=redbull.tv&sz=128",
        "utc_offset": "+0000"
    },
    {
        "id": "MNCVision.all",
        "name": "MNC Vision All Channels",
        "url": "https://www.mncvision.id/channel",
        "icon": "https://www.google.com/s2/favicons?domain=mncvision.id&sz=128",
        "utc_offset": "+0700"
    },
    {
        "id": "CLTV36.ph",
        "name": "CLTV36",
        "url": "https://cltv36.tv/tv-programs/",
        "icon": "https://cltv36.tv/wp-content/uploads/2021/02/cltv36-logo.png",
        "utc_offset": "+0800"
    }
]

def format_xmltv_date(dt_obj, utc_offset="+0700"):
    return dt_obj.strftime(f"%Y%m%d%H%M%S {utc_offset}")

def indent_xml(elem):
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")

# =========================================================================
# 1. RED BULL TV SCRAPER
# =========================================================================
def fetch_epg_redbull(target):
    epg_id = target["id"]
    programmes = []
    channels = [{"id": epg_id, "name": target["name"], "icon": target["icon"]}]
    
    url = "https://api.redbull.tv/v3/epg/live"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json()
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
                        "desc": desc
                    })
    except Exception as e:
        print(f"[!] Error RedBull: {e}")

    return channels, programmes

# =========================================================================
# 2. MNC VISION SCRAPER
# =========================================================================
def fetch_single_mnc(args):
    href, raw_name, base_url, headers, today = args
    programmes = []
    clean_name = re.sub(r'[^a-zA-Z0-9]', '', raw_name)
    if not clean_name:
        return None, []
        
    epg_id = f"{clean_name}.mnc"
    ch_info = {"id": epg_id, "name": f"{raw_name} (MNC)", "icon": "https://www.google.com/s2/favicons?domain=mncvision.id&sz=128"}
    
    try:
        time.sleep(0.1)
        res = requests.get(urljoin(base_url, href), headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            time_pattern = re.compile(r'(\b[0-2]?\d[:.][0-5]\d\b)')
            items = []
            
            for row in soup.find_all(['tr', 'li', 'div']):
                text = row.get_text(strip=True)
                if len(text) > 120: continue
                match = time_pattern.search(text)
                if match:
                    t_str = match.group(1).replace('.', ':')
                    if len(t_str.split(':')[0]) == 1: t_str = "0" + t_str
                    title = text[match.end():].strip(" -–:\t\n\r[]")
                    if title and len(title) > 2: items.append((t_str, title))

            for i in range(len(items)):
                t_str, title = items[i]
                start_dt = datetime.strptime(f"{today.strftime('%Y-%m-%d')} {t_str}", "%Y-%m-%d %H:%M")
                if i + 1 < len(items):
                    stop_dt = datetime.strptime(f"{today.strftime('%Y-%m-%d')} {items[i+1][0]}", "%Y-%m-%d %H:%M")
                    if stop_dt <= start_dt: stop_dt += timedelta(days=1)
                else:
                    stop_dt = start_dt + timedelta(hours=1)

                programmes.append({
                    "channel": epg_id,
                    "start": format_xmltv_date(start_dt, "+0700"),
                    "stop": format_xmltv_date(stop_dt, "+0700"),
                    "title": title,
                    "desc": f"Siaran {title} di {raw_name}"
                })
    except Exception:
        pass
    return ch_info, programmes

def fetch_epg_mncvision(target):
    channels, programmes = [], []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        res = requests.get(target["url"], headers=headers, timeout=15)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            links = soup.find_all('a', href=re.compile(r'/channel/detail/'))
            visited, tasks, today = set(), [], datetime.now()
            
            for l in links:
                href = l.get('href')
                if href in visited: continue
                visited.add(href)
                raw_name = l.get_text(strip=True) or href.split('/')[-1]
                tasks.append((href, raw_name, "https://www.mncvision.id", headers, today))

            with ThreadPoolExecutor(max_workers=5) as executor:
                results = executor.map(fetch_single_mnc, tasks)

            for ch_info, progs in results:
                if ch_info:
                    channels.append(ch_info)
                    programmes.extend(progs)
    except Exception as e:
        print(f"[!] Error MNC: {e}")
    return channels, programmes

# =========================================================================
# 3. CLTV36 SCRAPER
# =========================================================================
def fetch_epg_cltv36(target):
    epg_id = target["id"]
    programmes = []
    channels = [{"id": epg_id, "name": target["name"], "icon": target["icon"]}]
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    try:
        res = requests.get(target["url"], headers=headers, timeout=15)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            today = datetime.now()
            
            for container in soup.find_all(['div', 'article', 'section']):
                text = container.get_text(" ", strip=True)
                time_matches = re.findall(r'(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))', text)
                
                if time_matches:
                    title_tag = container.find(['h1', 'h2', 'h3', 'h4', 'h5', 'strong'])
                    if not title_tag: continue
                    title = title_tag.get_text(strip=True)
                    if len(title) < 3 or 'program' in title.lower(): continue

                    try:
                        start_str = time_matches[0].upper().replace(" ", "")
                        if len(start_str.split(':')[0]) == 1: start_str = "0" + start_str
                        start_dt = datetime.combine(today.date(), datetime.strptime(start_str, "%I:%M%p").time())
                        
                        if len(time_matches) > 1:
                            end_str = time_matches[1].upper().replace(" ", "")
                            if len(end_str.split(':')[0]) == 1: end_str = "0" + end_str
                            stop_dt = datetime.combine(today.date(), datetime.strptime(end_str, "%I:%M%p").time())
                            if stop_dt <= start_dt: stop_dt += timedelta(days=1)
                        else:
                            stop_dt = start_dt + timedelta(hours=1)

                        prog_data = {
                            "channel": epg_id,
                            "start": format_xmltv_date(start_dt, "+0800"),
                            "stop": format_xmltv_date(stop_dt, "+0800"),
                            "title": title,
                            "desc": f"Broadcast of {title} on CLTV36"
                        }
                        if prog_data not in programmes: programmes.append(prog_data)
                    except Exception: continue
    except Exception as e:
        print(f"[!] Error CLTV36: {e}")
    return channels, programmes

# =========================================================================
# 4. UNIVERSAL SCRAPER (PADANG TV, DLL)
# =========================================================================
def auto_scrape_epg(target):
    epg_id = target["id"]
    programmes = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    try:
        res = requests.get(target["url"], headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        icon = target.get("icon") or f"https://www.google.com/s2/favicons?domain={target['url']}&sz=128"
        channels = [{"id": epg_id, "name": target["name"], "icon": icon}]
        
        today = datetime.now()
        time_pattern = re.compile(r'(\b[0-2]?\d[:.][0-5]\d\b)')
        extracted = []

        for element in soup.find_all(['tr', 'li', 'p', 'div']):
            text = element.get_text(strip=True)
            if len(text) > 120: continue
            match = time_pattern.search(text)
            if match:
                t_str = match.group(1).replace('.', ':')
                if len(t_str.split(':')[0]) == 1: t_str = "0" + t_str
                title = text[match.end():].strip(" -–:\t\n\r")
                if title and len(title) > 2: extracted.append((t_str, title))

        for i in range(len(extracted)):
            t_str, title = extracted[i]
            try:
                start_dt = datetime.strptime(f"{today.strftime('%Y-%m-%d')} {t_str}", "%Y-%m-%d %H:%M")
                if i + 1 < len(extracted):
                    stop_dt = datetime.strptime(f"{today.strftime('%Y-%m-%d')} {extracted[i+1][0]}", "%Y-%m-%d %H:%M")
                    if stop_dt <= start_dt: stop_dt += timedelta(days=1)
                else:
                    stop_dt = start_dt + timedelta(hours=1)

                programmes.append({
                    "channel": epg_id,
                    "start": format_xmltv_date(start_dt, target.get("utc_offset", "+0700")),
                    "stop": format_xmltv_date(stop_dt, target.get("utc_offset", "+0700")),
                    "title": title,
                    "desc": f"Program {title} di {target['name']}"
                })
            except Exception: continue
    except Exception as e:
        print(f"[!] Error Universal Scraper {target['name']}: {e}")
        channels = [{"id": epg_id, "name": target["name"], "icon": ""}]

    return channels, programmes

# =========================================================================
# MAIN GENERATOR LOGIC (FIXED)
# =========================================================================
def generate_xmltv():
    print("[*] Memulai scraping EPG...")
    tv_elem = ET.Element("tv", {
        "generator-info-name": "Universal IPTV EPG Generator",
        "generator-info-url": "https://github.com/sulthanpamenan"
    })

    all_channels = []
    all_programmes = []

    for target in EPG_TARGET_SOURCES:
        print(f"[*] Scraping: {target['name']}...")
        if "mncvision" in target["url"].lower():
            ch_list, progs = fetch_epg_mncvision(target)
        elif "redbull" in target["url"].lower() or target["id"] == "RedBullTV.global":
            ch_list, progs = fetch_epg_redbull(target)
        elif "cltv36" in target["url"].lower() or target["id"] == "CLTV36.ph":
            ch_list, progs = fetch_epg_cltv36(target)
        else:
            ch_list, progs = auto_scrape_epg(target)

        all_channels.extend(ch_list)
        all_programmes.extend(progs)
        print(f"[✓] Berhasil menambahkan {len(ch_list)} channel & {len(progs)} jadwal untuk {target['name']}")

    # 1. Tulis Tag <channel>
    for ch in all_channels:
        c_elem = ET.SubElement(tv_elem, "channel", id=ch["id"])
        d_elem = ET.SubElement(c_elem, "display-name")
        d_elem.text = ch["name"]
        if ch.get("icon"):
            ET.SubElement(c_elem, "icon", src=ch["icon"])

    # 2. Tulis Tag <programme>
    for prog in all_programmes:
        p_elem = ET.SubElement(tv_elem, "programme", {
            "start": prog["start"],
            "stop": prog["stop"],
            "channel": prog["channel"]
        })
        t_elem = ET.SubElement(p_elem, "title", lang="en")
        t_elem.text = prog["title"]
        if prog.get("desc"):
            d_elem = ET.SubElement(p_elem, "desc", lang="en")
            d_elem.text = prog["desc"]

    pretty_xml = indent_xml(tv_elem)
    with open("epg.xml", "w", encoding="utf-8") as f:
        f.write(pretty_xml)
        
    print(f"\n[SUKSES] File `epg.xml` berhasil diperbarui dengan total {len(all_channels)} channel dan {len(all_programmes)} jadwal acara!")

if __name__ == "__main__":
    generate_xmltv()
