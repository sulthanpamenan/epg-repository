import json
import urllib.request
import urllib.error
from datetime import datetime

def test_fetch_tivie():
    # Menggunakan channel 'btv' atau 'antv' sesuai kebutuhan uji coba
    channel_id = 'btv' 
    today = datetime.now().strftime('%Y-%m-%d')
    url = f"https://tivie.id/api/channel?id={channel_id}&date={today}"

    print(f"Menjalankan uji coba fetch ke: {url}")

    # Menambahkan header lengkap seperti hasil inspeksi cURL
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'id,en-US;q=0.9,en;q=0.8',
            'Referer': f'https://tivie.id/channel/{channel_id}',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin'
        }
    )

    try:
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                print("Berhasil! Respon JSON API diterima:")
                print(json.dumps(data, indent=2))
            else:
                print(f"Gagal dengan status kode: {response.status}")
    except urllib.error.HTTPError as e:
        print(f"HTTP Error terjadi: {e.code} - {e.reason}")
    except Exception as e:
        print(f"Terjadi kesalahan: {e}")

if __name__ == "__main__":
    test_fetch_tivie()
