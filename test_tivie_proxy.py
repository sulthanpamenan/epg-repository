import json
import re
from bs4 import BeautifulSoup
import requests

# URL Cloudflare Worker Anda
CF_WORKER_URL = "https://tivie-proxy.sulthan-pamenan.workers.dev"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

TIME_PATTERN_HM = re.compile(r"(\b[0-2]?\d[:.][0-5]\d\b)")

def clean_text_str(val):
    if not val: return ""
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", str(val)).strip()
    return re.sub(r"\s+", " ", text)

def test_single_channel(ch_id="sctv"):
    url = f"{CF_WORKER_URL}/channel/{ch_id}"
    print("=" * 60)
    print(f"[*] Menguji koneksi ke Channel: {ch_id}")
    print(f"[*] Target URL Proxy: {url}")
    print("=" * 60)

    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        res = session.get(url, timeout=15)
        print(f"[>] Status Code  : {res.status_code}")
        print(f"[>] Content-Type : {res.headers.get('Content-Type')}")
        print(f"[>] Panjang Respon: {len(res.text)} karakter")

        if res.status_code != 200:
            print(f"[!] Gagal! Respon HTTP bukan 200.")
            print(f"[Snippet Respon]: {res.text[:300]}")
            return

        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 1. Cek Apakah Ada Blokir Cloudflare / Text Mencurigakan
        page_title = soup.find('title')
        if page_title:
            print(f"[>] Judul Halaman: {page_title.get_text(strip=True)}")
            if "Attention Required" in page_title.get_text() or "Cloudflare" in page_title.get_text():
                print("[!] PERINGATAN: Halaman masih terdeteksi halaman blokir Cloudflare!")
                return

        # 2. Cek Inertia.js Data
        app_div = soup.find('div', id='app')
        raw_list = []
        
        if app_div and app_div.get('data-page'):
            print("[✓] Atribut 'data-page' Inertia.js ditemukan!")
            try:
                page_json = json.loads(app_div['data-page'])
                props = page_json.get('props', {})
                schedules = props.get('schedules', []) or props.get('epg', []) or props.get('channel', {}).get('schedules', [])
                print(f"[✓] Jumlah jadwal ditemukan dalam JSON: {len(schedules)}")
                
                for item in schedules:
                    t_str = item.get('time') or item.get('start_time')
                    title = item.get('title') or item.get('program_name') or item.get('name')
                    if t_str and title:
                        match = TIME_PATTERN_HM.search(str(t_str))
                        if match:
                            raw_list.append({"time": match.group(1).replace(".", ":").zfill(5)[:5], "title": clean_text_str(title)})
            except Exception as e:
                print(f"[!] Error saat parsing JSON Inertia: {e}")
        else:
            print("[!] Atribut 'data-page' TIDAK ditemukan. Mencoba DOM text parsing...")
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

        print(f"[✓] Total program berhasil diekstrak: {len(raw_list)}")
        if raw_list:
            print("\n--- 5 Jadwal Pertama ---")
            for p in raw_list[:5]:
                print(f"[{p['time']}] {p['title']}")
        else:
            print("[!] Daftar program kosong. Periksa struktur HTML atau pastikan worker meneruskan data dengan benar.")
            print(f"[Cuplikan HTML]: {res.text[:400]}")

    except Exception as e:
        print(f"[!] Terjadi Exception: {e}")

    print("=" * 60)

if __name__ == "__main__":
    test_single_channel("sctv")
