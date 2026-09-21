import os
import json
import requests
from datetime import datetime, timezone, timedelta

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
}

def test_api_login():
    print("=" * 60)
    print("[*] Memulai Uji Coba API Login Indonesiana TV")
    print("=" * 60)

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

    # 3. Jika belum ada, lakukan Login API POST murni
    if not auth_token:
        print("[*] Token tidak ditemukan. Melakukan login otomatis via API POST...")
        try:
            login_url = "https://api.indonesianatv.app/v1/users/sessions/email"
            login_headers = {
                "accept": "application/json, text/plain, */*",
                "content-type": "application/json",
                "origin": "https://indonesiana.tv",
                "referer": "https://indonesiana.tv/",
                "user-agent": HEADERS["User-Agent"]
            }
            login_payload = {
                "notification": {"channel": 0, "token": ""},
                "email": "akun002fix@gmail.com",
                "password": "Akun002x"
            }
            
            res = requests.post(login_url, headers=login_headers, json=login_payload, timeout=15)
            print(f"[+] Status Code Login API: {res.status_code}")
            if res.status_code == 200:
                res_json = res.json()
                if res_json.get("success"):
                    auth_token = res_json.get("data", {}).get("accessSession", {}).get("token")
                    print("[✓] Login API berhasil mendapatkan token baru!")
            else:
                print(f"[!] Login API Gagal: {res.text}")
        except Exception as e:
            print(f"[!] API Login Exception: {e}")

        if auth_token:
            token_payload = {
                "token": auth_token,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            with open(cache_file, "w") as f:
                json.dump(token_payload, f)

            if gh_pat and gist_id:
                update_payload = {
                    "files": {
                        gist_filename: {
                            "content": json.dumps(token_payload, indent=2)
                        }
                    }
                }
                try:
                    requests.patch(f"https://api.github.com/gists/{gist_id}", headers={"Authorization": f"Bearer {gh_pat}"}, json=update_payload, timeout=10)
                    print("[✓] Token baru berhasil diperbarui otomatis ke GitHub Gist!")
                except Exception as e:
                    print(f"[!] Gist Update Error: {e}")

    if not auth_token:
        print("[!] Gagal total mendapatkan token.")
        return

    # 4. Tes Fetch EPG API
    print("[*] Menguji pengambilan data EPG menggunakan token...")
    channel_code = "MMF"
    wib_tz = timezone(timedelta(hours=7))
    now_wib = datetime.now(timezone.utc).astimezone(wib_tz)

    start_timestamp = int(now_wib.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    end_timestamp = int((now_wib + timedelta(days=2)).replace(hour=23, minute=59, second=59, microsecond=0).timestamp())

    api_url = f"https://api.indonesianatv.app/v1/users/live-streams/{channel_code}/programs"
    params = {
        "filters[startDate]": start_timestamp,
        "filters[endDate]": end_timestamp,
        "skip": 0,
        "limit": 10
    }
    headers = {
        "accept": "application/json, text/plain, */*",
        "authorization": f"Bearer {auth_token}",
        "origin": "https://indonesiana.tv",
        "referer": "https://indonesiana.tv/live",
        "user-agent": HEADERS["User-Agent"]
    }

    try:
        prog_res = requests.get(api_url, params=params, headers=headers, timeout=15)
        print(f"[+] Status Code EPG API: {prog_res.status_code}")
        if prog_res.status_code == 200:
            prog_data = prog_res.json()
            if prog_data.get("success"):
                items = prog_data.get("data", {}).get("items", [])
                print(f"[✓] Berhasil memuat {len(items)} program siaran pertama!")
                for idx, item in enumerate(items[:3]):
                    print(f"    - [{idx+1}] {item.get('name')}")
        else:
            print(f"[!] Gagal mengambil EPG: {prog_res.text}")
    except Exception as e:
        print(f"[!] EPG Fetch Exception: {e}")

    print("=" * 60)
    print("[*] Uji Coba Selesai")
    print("=" * 60)

if __name__ == "__main__":
    test_api_login()
