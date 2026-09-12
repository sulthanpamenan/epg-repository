import requests
from bs4 import BeautifulSoup
import json

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
}

def diagnose_tivie():
    session = requests.Session()
    session.headers.update(HEADERS)
    
    print("=" * 60)
    print("[*] DIAGNOSTIK KONEKSI TIVIE.ID")
    print("=" * 60)
    
    # 1. Cek Homepage & Tangkap Token Inertia
    home_url = "https://tivie.id/"
    try:
        print(f"[*] Mengakses Homepage: {home_url}")
        res = session.get(home_url, timeout=15)
        print(f"[>] Status Code : {res.status_code}")
        print(f"[>] Content-Type: {res.headers.get('Content-Type')}")
        print(f"[>] Server      : {res.headers.get('Server', 'Tidak diketahui')}")
        
        if res.status_code == 403:
            print("[!] TERDETEKSI BLOKIR CLOUDFLARE (403 Forbidden pada Homepage)!")
            print("[>] Potensi penyebab: IP GitHub Actions masuk dalam blacklist reputasi Cloudflare.")
            return
        
        soup = BeautifulSoup(res.text, 'html.parser')
        app_div = soup.find('div', id='app')
        
        if app_div and app_div.get('data-page'):
            page_data = json.loads(app_div['data-page'])
            version = page_data.get('version', 'Tidak ditemukan')
            print(f"[✓] Token Inertia 'version' berhasil didapat: {version}")
        else:
            print("[!] Elemen 'div#app' atau atribut 'data-page' tidak ditemukan di HTML.")
            print(f"[Snippet HTML]: {res.text[:300]}...")
            
    except Exception as e:
        print(f"[!] Gagal terhubung ke Homepage: {e}")
        return

    print("-" * 60)

    # 2. Cek Akses ke Endpoint Channel Spesifik (Contoh: SCTV)
    channel_url = "https://tivie.id/channel/sctv"
    try:
        print(f"[*] Mengakses Halaman Channel: {channel_url}")
        res_ch = session.get(channel_url, timeout=15)
        print(f"[>] Status Code : {res_ch.status_code}")
        print(f"[>] Content-Type: {res_ch.headers.get('Content-Type')}")
        
        if "application/json" in res_ch.headers.get("Content-Type", "") or res_ch.headers.get("X-Inertia"):
            print("[✓] Server merespon sebagai Inertia JSON.")
        else:
            print("[*] Server merespon sebagai HTML biasa.")
            soup_ch = BeautifulSoup(res_ch.text, 'html.parser')
            # Cek apakah ada teks jadwal atau terhalang halaman lain
            text_snippet = soup_ch.get_text(" ", strip=True)[:200]
            print(f"[>] Cuplikan Teks Halaman: {text_snippet}")
            
    except Exception as e:
        print(f"[!] Gagal mengakses halaman channel: {e}")

    print("=" * 60)

if __name__ == "__main__":
    diagnose_tivie()
