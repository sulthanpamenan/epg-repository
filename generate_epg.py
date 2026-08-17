import sys
import os
import re
import requests
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
from xml.dom import minidom
from bs4 import BeautifulSoup
from urllib.parse import urljoin

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

def auto_scrape_epg(target):
    """Fungsi universal untuk mengekstrak jam & judul dari URL manapun."""
    epg_id = target["id"]
    url = target["url"]
    utc_offset = target.get("utc_offset", "+0700")
    programmes = []
    extracted_icon = target.get("icon", "")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"[!] HTTP Error {response.status_code} saat mengakses {url}")
            return programmes, extracted_icon

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

    return programmes, extracted_icon

# =========================================================================
# GENERATOR UTAMA XMLTV
# =========================================================================
def generate_xmltv():
    print("[*] Memproses EPG dari seluruh daftar URL target...")
    
    tv_elem = ET.Element("tv", {
        "generator-info-name": "Universal IPTV EPG Generator",
        "generator-info-url": "https://github.com/sulthanpamenan"
    })

    all_programmes = []

    for target in EPG_TARGET_SOURCES:
        print(f"[*] Scraping EPG: {target['name']} ({target['id']})...")
        
        progs, icon_url = auto_scrape_epg(target)
        all_programmes.extend(progs)

        channel_elem = ET.SubElement(tv_elem, "channel", id=target["id"])
        display_name = ET.SubElement(channel_elem, "display-name")
        display_name.text = target["name"]
        if icon_url:
            ET.SubElement(channel_elem, "icon", src=icon_url)

        print(f"[✓] Ditemukan {len(progs)} acara untuk {target['name']}")

    for prog in all_programmes:
        prog_elem = ET.SubElement(tv_elem, "programme", {
            "start": prog["start"],
            "stop": prog["stop"],
            "channel": prog["channel"]
        })
        title_elem = ET.SubElement(prog_elem, "title", lang="en")
        title_elem.text = prog["title"]
        
        if prog.get("desc"):
            desc_elem = ET.SubElement(prog_elem, "desc", lang="en")
            desc_elem.text = prog["desc"]

    pretty_xml = indent_xml(tv_elem)
    with open("epg.xml", "w", encoding="utf-8") as f:
        f.write(pretty_xml)
        
    print(f"\n[SUCCESS] Selesai! `epg.xml` berhasil diperbarui dengan total {len(all_programmes)} acara.")

if __name__ == "__main__":
    generate_xmltv()
