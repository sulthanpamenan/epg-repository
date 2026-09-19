from datetime import datetime, timezone, timedelta
import requests

# Konfigurasi target channel (misal: MMF atau MKU)
CHANNEL_ID = "MMF"

# Menghitung timestamp awal hari (00:00:00) dan akhir hari (23:59:59) untuk hari ini (WIB / UTC+7)
wib_tz = timezone(timedelta(hours=7))
now_wib = datetime.now(timezone.utc).astimezone(wib_tz)

start_of_day = now_wib.replace(hour=0, minute=0, second=0, microsecond=0)
end_of_day = now_wib.replace(hour=23, minute=59, second=59, microsecond=0)

start_timestamp = int(start_of_day.timestamp())
end_timestamp = int(end_of_day.timestamp())

url = f"https://api.indonesianatv.app/v1/users/live-streams/{CHANNEL_ID}/programs"
params = {
    "filters[startDate]": start_timestamp,
    "filters[endDate]": end_timestamp,
    "skip": 0,
    "limit": 1000,
}

headers = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "origin": "https://indonesiana.tv",
    "referer": "https://indonesiana.tv/",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
}


def test_fetch_indonesiana():
  print(f"[*] Mengambil jadwal untuk channel: {CHANNEL_ID}")
  print(
      f"[*] Tanggal: {start_of_day.strftime('%Y-%m-%d')} (Timestamp:"
      f" {start_timestamp} s.d {end_timestamp})"
  )
  print(f"[*] URL: {url}\n")

  try:
    response = requests.get(url, params=params, headers=headers, timeout=15)
    print(f"[✓] Status HTTP: {response.status_code}")

    if response.status_code == 200:
      data = response.json()
      if data.get("success"):
        items = data.get("data", {}).get("items", [])
        print(
            f"[✓] Berhasil mengambil {len(items)} program siaran:\n"
            + "=" * 50
        )

        for idx, item in enumerate(items[:10], 1):  # Tampilkan 10 program awal
          s_time = datetime.fromtimestamp(
              int(item["startDate"]), wib_tz
          ).strftime("%H:%M")
          e_time = datetime.fromtimestamp(int(item["endDate"]), wib_tz).strftime(
              "%H:%M"
          )
          print(
              f"{idx}. [{s_time} - {e_time}] {item.get('name')} (XID:"
              f" {item.get('xid')})"
          )

        if len(items) > 10:
          print(f"... dan {len(items) - 10} program lainnya.")
      else:
        print(
            "[!] API mengembalikan success=false:"
            f" {data.get('message', 'Unknown')}"
        )
    else:
      print(f"[!] Gagal terhubung. Response teks: {response.text[:300]}")

  except Exception as e:
    print(f"[!] Terjadi error saat melakukan request: {e}")


if __name__ == "__main__":
  test_fetch_indonesiana()
