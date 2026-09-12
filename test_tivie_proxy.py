import re
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
import requests

CF_WORKER_URL = "https://tivie-proxy.sulthan-pamenan.workers.dev"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def clean_text_str(val):
    if not val: return ""
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", str(val)).strip()
    return re.sub(r"\s+", " ", text)

def format_xmltv_date(dt_obj, utc_offset="+0700"):
    return dt_obj.strftime(f"%Y%m%d%H%M%S {utc_offset}")

def test_parse_channel(ch_id="sctv", ch_name="SCTV"):
    url = f"{CF_WORKER_URL}/channel/{ch_id}"
    print("=" * 60)
    print(f"[*] Menguji Parsing DOM untuk Channel: {ch_name} ({ch_id})")
    print("=" * 60)

    session = requests.Session()
    session.headers.update(HEADERS)
    wib_tz = timezone(timedelta(hours=7))
    today_wib = datetime.now(timezone.utc).astimezone(wib_tz).date()

    try:
        res = session.get(url, timeout=15)
        print(f"[>] Status Code: {res.status_code}")
        
        if res.status_code != 200:
            print("[!] Gagal mengambil halaman.")
            return

        soup = BeautifulSoup(res.text, 'html.parser')
        raw_list = []

        # Logika parsing DOM text baru
        lines = [line.strip() for line in soup.get_text("\n", strip=True).split("\n") if line.strip()]
        i = 0
        while i < len(lines):
            line = lines[i]
            match = re.match(r'^(\d{2}:\d{2})(?:\s*WIB)?$', line, re.I)
            if match:
                time_str = match.group(1)
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    title_candidate = lines[i + 2] if next_line.upper() in ["WIB", "LIVE"] and i + 2 < len(lines) else next_line
                    clean_title = re.sub(r'^(?:WIB|LIVE)\s*', '', title_candidate, flags=re.I).strip()
                    clean_title = re.sub(r'\s+LIVE$', '', clean_title, flags=re.I).strip()

                    if clean_title and not re.match(r'^\d{2}:\d{2}', clean_title) and clean_title.upper() not in ["WIB", "LIVE"]:
                        if not any(p['time'] == time_str and p['title'] == clean_title for p in raw_list):
                            raw_list.append({"time": time_str, "title": clean_title})
            i += 1

        print(f"[✓] Total program mentah ditemukan: {len(raw_list)}")

        programmes = []
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
                "desc": f"Acara {curr['title']} di {ch_name}",
                "lang": "id"
            })

        print(f"[✓] Berhasil memformat {len(programmes)} program XMLTV siap pakai!")
        if programmes:
            print("\n--- Sampel Hasil Format XMLTV (3 Program Pertama) ---")
            for p in programmes[:3]:
                print(f"Channel ID : {p['channel']}")
                print(f"Waktu Mulai: {p['start']}")
                print(f"Waktu Selesai: {p['stop']}")
                print(f"Judul      : {p['title']}")
                print("-" * 40)

    except Exception as e:
        print(f"[!] Terjadi Error: {e}")

    print("=" * 60)

if __name__ == "__main__":
    test_parse_channel("sctv", "SCTV")
