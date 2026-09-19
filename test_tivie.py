import json
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

def test_fetch_tivie_api_schedule():
    test_channels = [
        {"id": "antv", "name": "ANTV"},
        {"id": "btv", "name": "BTV"}
    ]
    
    wib_tz = timezone(timedelta(hours=7))
    today_wib_str = datetime.now(timezone.utc).astimezone(wib_tz).strftime('%Y-%m-%d')

    print(f"Memulai uji coba API jadwal tivie.id tanggal: {today_wib_str}\n" + "-"*50)

    for ch in test_channels:
        real_id = ch["id"]
        ch_name = ch["name"]
        
        # Menggunakan endpoint /api/channel dengan parameter id dan date
        url = f"https://tivie.id/api/channel?id={real_id}&date={today_wib_str}"
        print(f"Mengakses API: {url}")
        
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36',
                'Accept': '*/*',
                'Accept-Language': 'id,en-US;q=0.9,en;q=0.8',
                'Referer': f'https://tivie.id/channel/{real_id}',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin'
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    print(f"[OK] {ch_name}: Berhasil menerima respon JSON:")
                    print(json.dumps(data, indent=2))
                else:
                    print(f"[FAIL] {ch_name}: Status HTTP {response.status}")
        except urllib.error.HTTPError as e:
            print(f"[FAIL] {ch_name}: HTTP Error {e.code} - {e.reason}")
        except Exception as e:
            print(f"[FAIL] {ch_name}: Terjadi kesalahan -> {e}")
        print("-" * 30)

if __name__ == "__main__":
    test_fetch_tivie_api_schedule()
