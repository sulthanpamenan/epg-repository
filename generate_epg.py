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
from concurrent.futures import ThreadPoolExecutor  # Modul multithreading

# =========================================================================
# 🎯 DAFTAR TARGET EPG (TAMBAHKAN SAKLAR URL & METADATA DI SINI)
# =========================================================================
EPG_TARGET_SOURCES = [
    {
        "id": "PadangTV.id",
        "name": "Padang TV",
        "url": "https://padangtv.id/schedule/",
        "icon": "",  # Auto-fetch jika dikosongkan
        "utc_offset": "+0700"  # WIB
    },
    {
        "id": "RedBullTV.global",
        "name": "Red Bull TV",
        "url": "https://www.redbull.tv/en/epg",
        "icon": "",
        "utc_offset": "+0000"  # UTC Global
    },
    {
        "id": "MNCVision.all",
        "name": "MNC Vision All Channels",
        "url": "https://www.mncvision.id/channel",
        "icon": "",
        "utc_offset": "+0700"
    }
]

# =========================================================================
# UTILS & EXTRACTION HELPERS
# =========================================================================
def format_xmltv_date(dt_obj, utc_offset="+0700"):
    return dt_obj.strftime(f"%Y%m%d%H%M%S {utc_offset}")

def indent_xml(elem):
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")

def extract_website_icon(soup, target_url):
    """Mengambil favicon/logo dari meta tag website target."""
    try:
        icon_tag = soup.find("link", rel=lambda r: r and ('icon' in r.lower() or 'shortcut' in r.lower()))
        if icon_tag and icon_tag.get("href"):
            href = icon_tag["href"]
            if href.startswith("http"):
                return href
            elif href.startswith("//"):
                return "https:" + href
            else:
                return urljoin(target_url, href)
    except Exception:
        pass
            
    domain = target_url.split("//")[-1].split("/")[0]
    return f"https://www.google.com/s2/favicons?domain={domain}&sz=128"

# =========================================================================
# SCRAPER 1: RED BULL TV (VIA API)
# =========================================================================
def fetch_epg_redbull(target):
    """Mengambil jadwal EPG presisi langsung dari API internal Red Bull TV."""
    epg_id = target["id"]
    programmes = []
    channels = [{"id": epg_id, "name": target["name"], "icon": "https://www.google.com/s2/favicons?domain=redbull.tv&sz=128"}]
    
    url = "https://api.redbull.tv/v3/epg/live"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json()
            for item in data.get("items", []):
                title = item.get("title") or item.get("label", "Red Bull TV Live")
                desc = item.get("description", f"Program {title} di Red Bull TV")
                
                start_iso = item.get("start_time")
                end_iso = item.get("end_time")
                
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
        print(f"[!] Gagal mengambil EPG Red Bull TV via API: {e}")

    return channels, programmes

# =========================================================================
# SCRAPER 2: MNC VISION (PARALEL / MULTITHREADING)
# =========================================================================
def fetch_single_mnc_channel(args):
    """Worker function untuk mengekstrak 1 detail channel MNC Vision secara paralel."""
    href, raw_name, base_url, headers, today = args
    programmes = []
    
    clean_name = re.sub(r'[^a-zA-Z0-9]', '', raw_name)
    if not clean_name:
        return None, []
        
    epg_id = f"{clean_name}.mnc"
    ch_info = {
        "id": epg_id,
        "name": f"{raw_name} (MNC)",
        "icon": "https://www.google.com/s2/favicons?domain=mncvision.id&sz=128"
    }

    full_ch_url = urljoin(base_url, href)
    time_pattern = re.compile(r'(\b[0-2]?\d[:.][0-5]\d\b)')

    try:
        # Delay acak tipis (0.2 - 0.5 detik) agar tidak membanjiri server sekaligus
        time.sleep(random.uniform(0.2, 0.5))
        
        ch_res = requests.get(full_ch_url, headers=headers, timeout=10)
        if ch_res.status_code == 200:
            ch_soup = BeautifulSoup(ch_res.text, 'html.parser')
            extracted_items = []
            
            for row in ch_soup.find_all(['tr', 'li', 'p', 'div']):
                text = row.get_text(strip=True)
                if len(text) > 150:
                    continue
                match = time_pattern.search(text)
                if match:
                    time_str = match.group(1).replace('.', ':')
                    if len(time_str.split(':')[0]) == 1:
                        time_str = "0" + time_str
                    title = text[match.end():].strip(" -–:\t\n\r[]")
                    if title and len(title) > 2:
                        extracted_items.append((time_str, title))

            for i in range(len(extracted_items)):
                time_str, title = extracted_items[i]
                start_dt = datetime.strptime(f"{today.strftime('%Y-%m-%d')} {time_str}", "%Y-%m-%d %H:%M")
                
                if i + 1 < len(extracted_items):
                    next_time_str = extracted_items[i+1][0]
                    stop_dt = datetime.strptime(f"{today.strftime('%Y-%m-%d')} {next_time_str}", "%Y-%m-%d %H:%M")
                    if stop_dt <= start_dt:
                        stop_dt += timedelta(days=1)
                else:
                    stop_dt = start_dt + timedelta(hours=1)

                programmes.append({
                    "channel": epg_id,
                    "start": format_xmltv_date(start_dt, "+0700"),
                    "stop": format_xmltv_date(stop_dt, "+0700"),
                    "title": title,
                    "desc": f"Program {title} di {raw_name}"
                })
    except Exception:
        pass

    return ch_info, programmes


def fetch_epg_mncvision(target):
    """Mengambil EPG seluruh channel MNC Vision menggunakan ThreadPoolExecutor."""
    programmes = []
    channels = []
    base_url = "https://www.mncvision.id"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        response = requests.get(target["url"], headers=headers, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            channel_links = soup.find_all('a', href=re.compile(r'/channel/detail/'))
            
            visited_channels = set()
            today = datetime.now()
            tasks = []

            for link in channel_links:
                href = link.get('href')
                if href in visited_channels:
                    continue
                visited_channels.add(href)
                
                raw_name = link.get_text(strip=True)
                if not raw_name:
                    parts = href.strip('/').split('/')
                    raw_name = parts[-1] if len(parts) > 0 else "Unknown"

                tasks.append((href, raw_name, base_url, headers, today))

            # Proses hingga 5 channel sekaligus dalam satu waktu
            with ThreadPoolExecutor(max_workers=5) as executor:
                results = executor.map(fetch_single_mnc_channel, tasks)

            for ch_info, progs in results:
                if ch_info:
                    channels.append(ch_info)
                    programmes.extend(progs)

    except Exception as e:
        print(f"[!] Gagal mengekstrak EPG MNC Vision: {e}")

    return channels, programmes

# =========================================================================
# SCRAPER 3: UNIVERSAL PARSER (SINGLE CHANNEL WEB)
# =========================================================================
def auto_scrape_epg(target):
    """Fungsi universal untuk mengekstrak jam & judul dari URL manapun."""
    epg_id = target["id"]
    url = target["url"]
    utc_offset = target.get("utc_offset", "+0700")
    programmes = []
    extracted_icon = target.get("icon", "")

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"[!] HTTP Error {response.status_code} saat mengakses {url}")
            return [{"id": epg_id, "name": target["name"], "icon": extracted_icon}], programmes

        soup = BeautifulSoup(response.text, 'html.parser')
        
        if not extracted_icon:
            extracted_icon = extract_website_icon(soup, url)

        today = datetime.now()
        time_pattern = re.compile(r'(\b[0-2]?\d[:.][0-5]\d\b)')
        extracted_items = []

        for element in soup.find_all(['tr', 'li', 'p', 'div', 'article', 'section']):
            text = element.get_text(strip=True)
            if len(text) > 150:
                continue

            match = time_pattern.search(text)
            if match:
                time_str = match.group(1).replace('.', ':')
                if len(time_str.split(':')[0]) == 1:
                    time_str = "0" + time_str
                
                title = text[match.end():].strip(" -–:\t\n\r")
                if title and len(title) > 2:
                    extracted_items.append((time_str, title))

        clean_items = []
        for item in extracted_items:
            if not clean_items or clean_items[-1] != item:
                clean_items.append(item)

        for i in range(len(clean_items)):
            time_str, title = clean_items[i]
            try:
                start_dt = datetime.strptime(f"{today.strftime('%Y-%m-%d')} {time_str}", "%Y-%m-%d %H:%M")
                
                if i + 1 < len(clean_items):
                    next_time_str = clean_items[i+1][0]
                    stop_dt = datetime.strptime(f"{today.strftime('%Y-%m-%d')} {next_time_str}", "%Y-%m-%d %H:%M")
                    if stop_dt <= start_dt:
                        stop_dt += timedelta(days=1)
                else:
                    stop_dt = start_dt + timedelta(hours=1)

                programmes.append({
                    "channel": epg_id,
                    "start": format_xmltv_date(start_dt, utc_offset),
                    "stop": format_xmltv_date(stop_dt, utc_offset),
                    "title": title,
                    "desc": f"Program {title} di {target['name']}"
                })
            except Exception:
                continue

    except Exception as e:
        print(f"[!] Gagal mengekstrak EPG dari {url}: {e}")

    channels = [{"id": epg_id, "name": target["name"], "icon": extracted_icon}]
    return channels, programmes

# =========================================================================
# GENERATOR UTAMA XMLTV
# =========================================================================
def generate_xmltv():
    print("[*] Memproses EPG dari seluruh daftar URL target...")
    
    tv_elem = ET.Element("tv", {
        "generator-info-name": "Universal IPTV EPG Generator",
        "generator-info-url": "https://github.com/sulthanpamenan"
    })

    all_channels = []
    all_programmes = []

    for target in EPG_TARGET_SOURCES:
        print(f"[*] Scraping EPG: {target['name']} ({target['id']})...")
        
        # Routing handler
        if "mncvision" in target["url"].lower():
            ch_list, progs = fetch_epg_mncvision(target)
        elif "redbull" in target["url"].lower() or target["id"] == "RedBullTV.global":
            ch_list, progs = fetch_epg_redbull(target)
        else:
            ch_list, progs = auto_scrape_epg(target)

        all_channels.extend(ch_list)
        all_programmes.extend(progs)
        print(f"[✓] Ditemukan {len(ch_list)} channel & {len(progs)} acara untuk {target['name']}")

    # 1. Menulis tag <channel>
    for ch in all_channels:
        channel_elem = ET.SubElement(tv_elem, "channel", id=ch["id"])
        display_name = ET.SubElement(channel_elem, "display-name")
        display_name.text = ch["name"]
        if ch.get("icon"):
            ET.SubElement(channel_elem, "icon", src=ch["icon"])

    # 2. Menulis tag <programme>
    for prog in all_programmes:
        prog_elem = ET.SubElement(tv_elem, "programme", {
            "start": prog["start"],
            "stop": prog["stop"],
            "channel": prog["channel"]
        })
        title_elem = ET.SubElement(prog_elem, "title", lang="id")
        title_elem.text = prog["title"]
        
        if prog.get("desc"):
            desc_elem = ET.SubElement(prog_elem, "desc", lang="id")
            desc_elem.text = prog["desc"]

    pretty_xml = indent_xml(tv_elem)
    with open("epg.xml", "w", encoding="utf-8") as f:
        f.write(pretty_xml)
        
    print(f"\n[SUCCESS] Selesai! `epg.xml` berhasil diperbarui dengan total {len(all_channels)} channel & {len(all_programmes)} acara.")

if __name__ == "__main__":
    generate_xmltv()
