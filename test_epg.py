import os
import json
import requests
from datetime import datetime, timezone, timedelta

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
}

def test_api_login_step_by_step():
    print("=" * 60)
    print("[*] Memulai Uji Coba Autentikasi Bertahap Indonesiana TV")
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

    # 3. Jika belum ada, jalankan 2 Langkah Autentikasi API
    if not auth_token:
        print("[*] Token tidak ditemukan. Menjalankan autentikasi bertahap...")
        try:
            session = requests.Session()
            session.headers.update({
                "accept": "application/json, text/plain, */*",
                "accept-language": "id,en-US;q=0.9,en-US;q=0.8",
                "origin": "https://indonesiana.tv",
                "referer": "https://indonesiana.tv/",
                "user-agent": HEADERS["User-Agent"]
            })

            # Langkah A: Request token anonim
            anon_url = "https://api.indonesianatv.app/v1/users/anon/sessions"
            anon_headers = {
                "authorization": "Basic RjI5Q1c2NzY6dEZGNzJmNVNLN2lYbFFPTWNVYmFEVHpS",
                "content-type": "application/json"
            }
            print("[*] Mengirim request ke anon/sessions...")
            anon_res = session.post(anon_url, headers=anon_headers, json={}, timeout=15)
            print(f"[+] Status Code Anon Session: {anon_res.status_code}")
            
            if anon_res.status_code == 200:
                anon_data = anon_res.json()
                anon_token = anon_data.get("data", {}).get("session", {}).get("token")
                
                if anon_token:
                    print("[✓] Berhasil mendapatkan token anonim!")
                    
                    # Langkah B: Kirim email & password menggunakan token anonim
                    email_url = "https://api.indonesianatv.app/v1/users/sessions/email"
                    email_headers = {
                        "authorization": f"Bearer {anon_token}",
                        "content-type": "application/json"
                    }
                    email_payload = {
                        "notification": {"channel": 0, "token": ""},
                        "email": "akun002fix@gmail.com",
                        "password": "Akun002x"
                    }
                    
                    print("[*] Mengirim kredensial email ke sessions/email...")
                    email_res = session.post(email_url, headers=email_headers, json=email_payload, timeout=15)
                    print(f"[+] Status Code Email Login: {email_res.status_code}")
                    
                    if email_res.status_code == 200:
                        email_data = email_res.json()
                        if email_data.get("success"):
                            auth_token = email_data.get("data", {}).get("accessSession", {}).get("token")
                            print("[✓] Sukses mendapatkan Access Token Utama!")
                        else:
                            print(f"[!] Login API gagal merespon sukses: {email_res.text}")
                    else:
                        print(f"[!] Login Email Error: {email_res.text}")
                else:
                    print(f"[!] Token anonim tidak ditemukan di response: {anon_res.text}")
            else:
                print(f"[!] Gagal mengambil session anonim: {anon_res.text}")
        except Exception as e:
            print(f"[!] Exception pada proses autentikasi: {e}")

        # Simpan token baru jika berhasil
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

    # 4. Tes Fetch Data EPG
    print("[*] Menguji pengambilan data EPG menggunakan token baru...")
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
    test_api_login_step_by_step()
