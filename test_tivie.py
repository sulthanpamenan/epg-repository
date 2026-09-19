import json
import urllib.request
import urllib.error
from datetime import datetime

def get_tivie_channels():
    tivie_master_fallback = [
        {"id": "antv", "name": "ANTV"},
        {"id": "btv", "name": "BTV"},
        {"id": "cnnindonesia", "name": "CNN Indonesia"},
        {"id": "garudatv", "name": "Garuda TV"},
        {"id": "gtv", "name": "GTV"},
        {"id": "indosiar", "name": "Indosiar"},
        {"id": "inews", "name": "iNews"},
        {"id": "kompastv", "name": "Kompas TV"},
        {"id": "mdtv", "name": "MDTV"},
        {"id": "mentaritv", "name": "Mentari TV"},
        {"id": "metrotv", "name": "Metro TV"},
        {"id": "mnctv", "name": "MNC TV"},
        {"id": "moji", "name": "MOJI"},
        {"id": "nusantaratv", "name": "Nusantara TV"},
        {"id": "rcti", "name": "RCTI"},
        {"id": "rtv", "name": "RTV"},
        {"id": "sctv", "name": "SCTV"},
        {"id": "sinpotv", "name": "Sin Po TV"},
        {"id": "transtv", "name": "Trans TV"},
        {"id": "trans7", "name": "Trans 7"},
        {"id": "tvone", "name": "tvOne"},
        {"id": "tvri", "name": "TVRI"},
        {"id": "vtv", "name": "VTV"},
        {"id": "sindonews", "name": "Sindonews TV"},
    ]
    channels = []
    for ch in tivie_master_fallback:
        channels.append({"id": ch["id"], "raw_id": f"Tivie_{ch['id']}.id", "name": ch["name"]})
    return channels

def test_fetch_all_tivie():
    today = datetime.now().strftime('%Y-%m-%d')
    channels = get_tivie_channels()
    results = {}

    print(f"Memulai pengambilan jadwal Tivie.id untuk tanggal: {today}\n" + "-"*50)

    for ch in channels:
        channel_id = ch["id"]
        channel_name = ch["name"]
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
                        "name": channel_name,
                        "current_show": data.get("ttl"),
                        "image": data.get("image")
                    }
                    print(f"[OK] {channel_name} ({channel_id}): {data.get('ttl')}")
                else:
                    results[channel_id] = {"status": f"HTTP Error {response.status}"}
                    print(f"[FAIL] {channel_name}: Status {response.status}")
        except urllib.error.HTTPError as e:
            results[channel_id] = {"status": f"HTTPError {e.code}"}
            print(f"[FAIL] {channel_name}: HTTP Error {e.code}")
        except Exception as e:
            results[channel_id] = {"status": f"Error: {str(e)}"}
            print(f"[FAIL] {channel_name}: {e}")

    print("-" * 50)
    print(f"Total Berhasil Diambil: {sum(1 for k, v in results.items() if v.get('status') == 'SUCCESS')}/{len(channels)}")

if __name__ == "__main__":
    test_fetch_all_tivie()
