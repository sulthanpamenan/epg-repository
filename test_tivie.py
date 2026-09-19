import urllib.request
import urllib.error

def test_homepage():
    url = "https://tivie.id/"
    print(f"Mengecek halaman utama: {url}")

    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36'
        }
    )

    try:
        with urllib.request.urlopen(req) as response:
            html_content = response.read().decode('utf-8')
            print(f"Berhasil akses! Panjang HTML: {len(html_content)} karakter")
            
            # Cek apakah ada kata 'antv' di dalam HTML
            if 'antv' in html_content.lower():
                print("Ditemukan kata 'antv' di dalam HTML halaman utama.")
            else:
                print("Kata 'antv' tidak ditemukan di HTML utama (kemungkinan dimuat secara dinamis via JavaScript/API terpisah).")
                
    except Exception as e:
        print(f"Gagal mengakses: {e}")

if __name__ == "__main__":
    test_homepage()
