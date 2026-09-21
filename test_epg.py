import os
import json
import requests
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
}

def clean_text_str(val):
    if not val: return ""
    text = str(val).replace("\xa0", " ")
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", " ", text).strip()
    return re.sub(r"\s+", " ", text)

def test_fetch_indonesiana():
    print("=" * 60)
    print("[*] Memulai Uji Coba Independen Indonesiana TV")
    print("=" * 60)

    target = {"id": "Indonesiana_MMF.id", "name": "Indonesiana TV MMF", "code": "MMF", "utc_offset": "+0700"}
    channel_code = target["code"]
    auth_token = None
    
    cache_dir = "Cache"
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, "indonesiana_cache.json")

    gh_pat = os.environ.get("GH_PAT")
    gist_id = os.environ.get("GIST_ID")
    gist_filename = "indonesiana_token.json"

    # 1. Cek Gist
    if gh_pat and gist_id:
        try:
            print("[*] Mencoba mengambil token dari GitHub Gist...")
            gist_url = f"https://api.github.com/gists/{gist_id}"
            gist_headers = {"Authorization": f"Bearer {gh_pat}", "Accept": "application/vnd.github+json"}
            gist_res = requests.get(gist_url, headers=gist_headers, timeout=10)
            if gist_res.status_code == 200:
                files = gist_res.json().get("files", {})
                if gist_filename in files:
                    content = json.loads(files[gist_filename]["content"])
                    auth_token = content.get("token")
                    if auth_token:
                        print("[✓] Token berhasil didapatkan dari GitHub Gist!")
        except Exception as e:
            print(f"[!] Gist Error: {e}")

    # 2. Cek Cache Lokal
    if not auth_token and os.path.exists(cache_file):
        try:
            print("[*] Mencoba mengambil token dari cache lokal...")
            with open(cache_file, "r") as f:
                cache_data = json.load(f)
                auth_token = cache_data.get("token")
                if auth_token:
                    print("[✓] Token berhasil didapatkan dari cache lokal!")
        except Exception as e:
            print(f"[!] Cache Error: {e}")

    # 3. Fallback Playwright Lokal (Headless=False agar Anda bisa melihat prosesnya jika mau)
    if not auth_token:
        print("[*] Token tidak ditemukan. Menjalankan Playwright lokal...")
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
                context = browser.new_context(
                    user_agent=HEADERS["User-Agent"],
                    viewport={"width": 1280, "height": 800}
                )
                page = context.new_page()

                def handle_response(response):
                    nonlocal auth_token
                    if "/v1/users/sessions/email" in response.url and response.status == 200:
                        try:
                            res_json = response.json()
                            token = res_json.get("data", {}).get("accessSession", {}).get("token")
                            if token:
                                auth_token = token
                                print("[✓] Playwright sukses menangkap Access Token!")
                        except Exception as ex:
                            print(f"[!] Gagal parsing JSON response: {ex}")

                page.on("response", handle_response)
                page.goto("https://indonesiana.tv/auth/login", timeout=60000, wait_until="domcontentloaded")
                
                email_sel = 'input[placeholder="Masukkan alamat e-mail Anda"]'
                page.wait_for_selector(email_sel, timeout=30000, state="visible")
                
                page.fill(email_sel, "akun002fix@gmail.com")
                page.fill('input[placeholder="Masukkan password Anda"]', "Akun002x")
                page.get_by_role("button", name="Masuk", exact=True).click()
                
                page.wait_for_timeout(5000)
                browser.close()

            if auth_token:
                token_payload = {
                    "token": auth_token,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                with open(cache_file, "w") as f:
                    json.dump(token_payload, f)
                print("[✓] Token baru berhasil disimpan ke cache lokal.")
        except Exception as e:
            print(f"[!] Playwright Error: {e}")

    if not auth_token:
        print("[!] Gagal total mendapatkan token Indonesiana TV.")
        return

    # 4. Tes Fetch API EPG Indonesiana
    print("[*] Mengambil data jadwal siaran (EPG) dari API Indonesiana TV...")
    wib_tz = timezone(timedelta(hours=7))
    now_wib = datetime.now(timezone.utc).astimezone(wib_tz)

    start_timestamp = int(now_wib.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    end_timestamp = int((now_wib + timedelta(days=2)).replace(hour=23, minute=59, second=59, microsecond=0).timestamp())

    api_url = f"https://api.indonesianatv.app/v1/users/live-streams/{channel_code}/programs"
    params = {
        "filters[startDate]": start_timestamp,
        "filters[endDate]": end_timestamp,
        "skip": 0,
        "limit": 50 # Ambil 50 data awal untuk pengujian
    }
    headers = {
        "accept": "application/json, text/plain, */*",
        "authorization": f"Bearer {auth_token}",
        "origin": "https://indonesiana.tv",
        "referer": "https://indonesiana.tv/live",
        "user-agent": HEADERS["User-Agent"]
    }

    try:
        res = requests.get(api_url, params=params, headers=headers, timeout=15)
        print(f"[+] Status Code API: {res.status_code}")
        if res.status_code == 200:
            data = res.json()
            items = data.get("data", {}).get("items", [])
            print(f"[✓] Berhasil memuat {len(items)} program siaran!")
            for idx, item in enumerate(items[:5]): # Tampilkan 5 program pertama
                print(f"    - [{idx+1}] {item.get('name')} (Mulai: {item.get('startDate')})")
        else:
            print(f"[!] Respon API Error: {res.text}")
    except Exception as e:
        print(f"[!] Koneksi API Error: {e}")

    print("=" * 60)
    print("[*] Uji Coba Selesai")
    print("=" * 60)

if __name__ == "__main__":
    import re
    test_fetch_indonesiana()
