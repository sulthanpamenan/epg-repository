import json
import urllib.request
import urllib.error
from datetime import datetime

# Daftar sampel channel yang ingin diuji (Anda bisa menambahkannya sesuai daftar channel tivie.id)
CHANNELS = ['antv', 'btv', 'rcti', 'sctv', 'indosiar', 'transtv', 'trans7']

def test_fetch_all_channels():
    today = datetime.now().strftime('%Y-%m-%d')
    results = {}

    print(f"Memulai pengambilan jadwal untuk tanggal: {today}\n" + "-"*40)

    for channel_id in CHANNELS:
        url = f"https://tivie.id/api/channel?id={channel_id}&date={today}"
        
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
                    results[channel_id] = {
                        "status": "SUCCESS",
                        "current_show": data.get("ttl"),
                        "description": data.get("desc"),
                        "image": data.get("image")
                    }
                    print(f"[OK] Channel '{channel_id}': {data.get('ttl')}")
                else:
                    results[channel_id] = {"status": f"HTTP Error {response.status}"}
                    print(f"[FAIL] Channel '{channel_id}': Status {response.status}")
        except urllib.error.HTTPError as e:
            results[channel_id] = {"status": f"HTTPError {e.code}"}
            print(f"[FAIL] Channel '{channel_id}': HTTP Error {e.code}")
        except Exception as e:
            results[channel_id] = {"status": f"Error: {str(e)}"}
            print(f"[FAIL] Channel '{channel_id}': {e}")

    print("-" * 40)
    print("Ringkasan Hasil Pengambilan Data:")
    print(json.dumps(results, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    test_fetch_all_channels()
