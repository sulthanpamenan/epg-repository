import base64
import json
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
}

HTTP_SESSION = requests.Session()
retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=10)
HTTP_SESSION.mount("https://", adapter)
HTTP_SESSION.mount("http://", adapter)
HTTP_SESSION.headers.update(HEADERS)

def format_xmltv_date(dt_obj, utc_offset="+0700"):
    return dt_obj.strftime(f"%Y%m%d%H%M%S {utc_offset}")

def clean_text_str(val):
    if not val: return ""
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F\xa0]", " ", str(val)).strip()
    return re.sub(r"\s+", " ", text)

# Uji coba dengan beberapa channel sampel populer dari Tivie.id (misal: SCTV, Indosiar, RCTI, ANTV)
TIVIE_TEST_CHANNELS = [
    {"id": "sctv", "name": "SCTV"},
    {"id": "indosiar", "name": "Indosiar"},
    {"id": "rcti", "name": "RCTI"},
    {"id": "antv", "name": "ANTV"}
]

CF_WORKER_URL = "https://tivie-proxy.sulthan-pamenan.workers.dev"

def scrape_single_tivie_channel(ch):
    ch_id, ch_name = ch["id"], ch["name"]
    url = f"{CF_WORKER_URL}/channel/{ch_id}"
    programmes = []
    wib_tz = timezone(timedelta(hours=7))
    today_wib = datetime.now(timezone.utc).astimezone(wib_tz).date()

    raw_list = []
    try:
        res = HTTP_SESSION.get(url, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # Cari elemen baris jadwal yang membungkus waktu dan program
            # Berdasarkan struktur website tivie.id, kita cari elemen yang memuat pola waktu WIB
            # Atau kita parse berdasarkan elemen card jadwal terstruktur
            
            # Alternatif: Cari semua blok teks yang berpasangan dengan waktu WIB
            text_blocks = [line.strip() for line in soup.get_text("\n", strip=True).split("\n") if line.strip()]
            
            i = 0
            while i < len(text_blocks):
                line = text_blocks[i]
                match = re.match(r'^(\d{2}:\d{2})(?:\s*WIB)?$', line, re.I)
                if match:
                    time_str = match.group(1)
                    collected_lines = []
                    
                    j = i + 1
                    while j < len(text_blocks):
                        next_line = text_blocks[j]
                        if re.match(r'^\d{2}:\d{2}', next_line) or not next_line:
                            break
                        if next_line.upper() not in ["WIB", "LIVE", "SELANJUTNYA"]:
                            clean_l = re.sub(r'^(?:WIB|LIVE)\s*', '', next_line, flags=re.I).strip()
                            clean_l = re.sub(r'\s+LIVE$', '', clean_l, flags=re.I).strip()
                            if clean_l and clean_l not in collected_lines:
                                collected_lines.append(clean_l)
                        j += 1
                    
                    if collected_lines:
                        # Logika penyusunan judul dan deskripsi yang lebih rapi:
                        # Baris 1: Kategori/Judul Utama (misal: "Mega Film Asia" atau "Premier League 2026/27")
                        # Baris 2/seterusnya: Judul Spesifik / Detail (misal: "The Medallion" atau "Tottenham Hotspur vs Everton")
                        
                        main_title = collected_lines[0]
                        sub_desc = ""

                        if len(collected_lines) > 1:
                            # Jika ada baris kedua, jadikan itu sebagai judul utama jika baris pertama adalah kategori umum,
                            # atau gabungkan sebagai detail/deskripsi acara.
                            if collected_lines[0] in ["Mega Film Asia", "Bioskop Indonesia", "Special Program"]:
                                main_title = collected_lines[1]
                                sub_desc = f"{collected_lines[0]} - " + " ".join(collected_lines[2:]) if len(collected_lines) > 2 else collected_lines[0]
                            else:
                                sub_desc = " ".join(collected_lines[1:])
                        else:
                            sub_desc = f"Acara {main_title} di {ch_name}"

                        if not any(p['time'] == time_str and p['title'] == main_title for p in raw_list):
                            raw_list.append({
                                "time": time_str, 
                                "title": main_title, 
                                "desc": sub_desc if sub_desc else f"Acara {main_title} di {ch_name}"
                            })
                i += 1

        for idx in range(len(raw_list)):
            curr = raw_list[idx]
            t_str = curr['time']
            start_dt = datetime.strptime(f"{today_wib} {t_str}", "%Y-%m-%d %H:%M").replace(tzinfo=wib_tz)
            if idx < len(raw_list) - 1:
                stop_time_str = raw_list[idx + 1]['time']
                stop_dt = datetime.strptime(f"{today_wib} {stop_time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=wib_tz)
                if stop_dt <= start_dt: stop_dt += timedelta(days=1)
            else:
                stop_dt = start_dt + timedelta(hours=1)

            programmes.append({
                "channel": f"Tivie_{ch_id}.id",
                "start": format_xmltv_date(start_dt, "+0700"),
                "stop": format_xmltv_date(stop_dt, "+0700"),
                "title": curr["title"],
                "desc": curr["desc"],
                "lang": "id"
            })
            
        print(f"[✓] Tivie.id [{ch_name}]: Berhasil memuat {len(programmes)} program.")
    except Exception as e:
        print(f"[!] Tivie Error [{ch_name}]: {e}")

    return {"id": f"Tivie_{ch_id}.id", "name": ch_name}, programmes

def test_tivie_extraction():
    print("=" * 50)
    print("[*] Memulai Uji Coba Khusus Parser Tivie.id")
    print("=" * 50)
    
    tv_elem = ET.Element("tv", {"generator-info-name": "Tivie Test Parser"})
    all_channels, all_programmes = [], []

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = executor.map(scrape_single_tivie_channel, TIVIE_TEST_CHANNELS)
        for ch_info, progs in results:
            if progs:
                all_channels.append(ch_info)
                all_programmes.extend(progs)

    # Cetak hasil ke terminal untuk verifikasi instan
    print("\n--- HASIL PARSING (SAMPLE) ---")
    for p in all_programmes[:10]:  # Tampilkan 10 program teratas
        print(f"Channel : {p['channel']}")
        print(f"Waktu   : {p['start']} s/d {p['stop']}")
        print(f"Title   : {p['title']}")
        print(f"Desc    : {p['desc']}")
        print("-" * 30)

    # Simpan ke file uji coba
    for ch in all_channels:
        c_elem = ET.SubElement(tv_elem, "channel", id=ch["id"])
        ET.SubElement(c_elem, "display-name").text = ch["name"]

    for p in all_programmes:
        p_elem = ET.SubElement(tv_elem, "programme", {"start": p["start"], "stop": p["stop"], "channel": p["channel"]})
        ET.SubElement(p_elem, "title", lang=p.get("lang", "id")).text = p["title"]
        if p.get("desc"): 
            ET.SubElement(p_elem, "desc", lang=p.get("lang", "id")).text = p["desc"]

    try:
        ET.indent(tv_elem, space="  ")
    except AttributeError: pass

    ET.ElementTree(tv_elem).write("test_tivie.xml", encoding="utf-8", xml_declaration=True)
    print(f"\n[SUCCESS] File uji coba tersimpan sebagai `test_tivie.xml` (Total Channel: {len(all_channels)}, Program: {len(all_programmes)})")
    print("=" * 50)

if __name__ == "__main__":
    test_tivie_extraction()
