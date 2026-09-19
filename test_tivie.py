import json
import re
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

TIME_PATTERN_HM = re.compile(r"(\b[0-2]?\d[:.][0-5]\d\b)")

def clean_text_str(val):
    if not val:
        return ""
    text = str(val).replace("\xa0", " ")
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", " ", text).strip()
    return re.sub(r"\s+", " ", text)

def format_xmltv_date(dt_obj, utc_offset="+0700"):
    return dt_obj.strftime(f"%Y%m%d%H%M%S {utc_offset}")

def test_fetch_full_schedule():
    # Menguji satu atau beberapa channel sampel (misal: antv dan btv)
    test_channels = [
        {"id": "antv", "name": "ANTV"},
        {"id": "btv", "name": "BTV"}
    ]
    
    wib_tz = timezone(timedelta(hours=7))
    today_wib_str = datetime.now(timezone.utc).astimezone(wib_tz).strftime('%Y-%m-%d')

    print(f"Memulai uji coba penarikan jadwal penuh tanggal: {today_wib_str}\n" + "-"*50)

    for ch in test_channels:
        real_id = ch["id"]
        ch_name = ch["name"]
        url = f"https://tivie.id/channel/{real_id}/{today_wib_str}"
        
        print(f"Mengakses: {url}")
        
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'id,en-US;q=0.9,en;q=0.8',
                'Referer': f'https://tivie.id/channel/{real_id}',
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                if response.status == 200:
                    html_content = response.read().decode('utf-8')
                    soup = BeautifulSoup(html_content, 'html.parser')
                    
                    raw_list = []
                    # Mencari elemen baris jadwal harian di HTML tivie.id
                    schedule_rows = soup.find_all(lambda tag: tag.name in ['div', 'li', 'tr'] and TIME_PATTERN_HM.search(tag.get_text()))
                    
                    for item in schedule_rows:
                        full_text = item.get_text(" ", strip=True)
                        time_match = TIME_PATTERN_HM.search(full_text)
                        if not time_match:
                            continue
                        
                        t_str = time_match.group(1).replace(".", ":").zfill(5)[:5]
                        cleaned_title = full_text.replace(time_match.group(0), "").replace("WIB", "").strip()
                        cleaned_title = re.sub(r"^[\s\-–:\.]+|[\s\-–:\.]+$", "", cleaned_title)
                        
                        if cleaned_title and len(cleaned_title) > 2:
                            if not any(p['time'] == t_str and p['title'] == cleaned_title for p in raw_list):
                                raw_list.append({
                                    "time": t_str,
                                    "title": cleaned_title
                                })

                    print(f"[OK] {ch_name}: Berhasil menemukan {len(raw_list)} program jadwal.")
                    # Cetak 5 jadwal pertama sebagai sampel
                    for idx, prog in enumerate(raw_list[:5]):
                        print(f"   -> [{prog['time']}] {prog['title']}")
                    print("-" * 30)
                else:
                    print(f"[FAIL] {ch_name}: Status HTTP {response.status}")
        except Exception as e:
            print(f"[FAIL] {ch_name}: Terjadi kesalahan -> {e}")

if __name__ == "__main__":
    test_fetch_full_schedule()
