from datetime import datetime, timezone, timedelta
import requests

# 1. Konfigurasi Kredensial dan Endpoint Login
LOGIN_URL = "https://api.indonesianatv.app/v1/auth/login"
EMAIL = "akun002fix@gmail.com"
PASSWORD = "Akun002x"

CHANNEL_ID = "MMF"  # Contoh channel (bisa MMF atau MKU)


def test_indonesiana_epg():
  print(
      "[*] Langkah 1: Melakukan autentikasi / login otomatis ke Indonesiana TV..."
  )

  headers = {
      "accept": "application/json, text/plain, */*",
      "content-type": "application/json",
      "origin": "https://indonesiana.tv",
      "referer": "https://indonesiana.tv/",
      "user-agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
          " like Gecko) Chrome/122.0.0.0 Safari/537.36"
      ),
  }

  payload = {"email": EMAIL, "password": PASSWORD}

  try:
    login_res = requests.post(
        LOGIN_URL, json=payload, headers=headers, timeout=15
    )
    print(f"[✓] Status HTTP Login: {login_res.status_code}")

    if login_res.status_code != 200:
      print(f"[!] Login Gagal. Respon: {login_res.text}")
      return

    login_data = login_res.json()
    # Mengambil token dari respons API
    token = (
        login_data.get("token")
        or login_data.get("data", {}).get("token")
        or login_data.get("accessToken")
    )

    if not token:
      print(
          "[!] Login berhasil tetapi token tidak ditemukan dalam respons JSON."
      )
      print(f"Respon lengkap: {login_data}")
      return

    print("[✓] Login Berhasil! Token Bearer berhasil didapatkan.")

    # 2. Mengambil Jadwal Program Menggunakan Token
    wib_tz = timezone(timedelta(hours=7))
    now_wib = datetime.now(timezone.utc).astimezone(wib_tz)

    start_timestamp = int(
        now_wib.replace(
            hour=0, minute=0, second=0, microsecond=0
        ).timestamp()
    )
    end_timestamp = int(
        now_wib.replace(
            hour=23, minute=59, second=59, microsecond=0
        ).timestamp()
    )

    api_url = f"https://api.indonesianatv.app/v1/users/live-streams/{CHANNEL_ID}/programs"
    params = {
        "filters[startDate]": start_timestamp,
        "filters[endDate]": end_timestamp,
        "skip": 0,
        "limit": 100,
    }

    auth_headers = headers.copy()
    auth_headers["authorization"] = f"Bearer {token}"

    print(
        f"\n[*] Langkah 2: Mengambil jadwal untuk channel {CHANNEL_ID} hari"
        f" ini..."
    )
    res = requests.get(
        api_url, params=params, headers=auth_headers, timeout=15
    )
    print(f"[✓] Status HTTP Jadwal: {res.status_code}")

    if res.status_code == 200:
      data = res.json()
      if data.get("success"):
        items = data.get("data", {}).get("items", [])
        print(
            f"[✓] Berhasil memuat {len(items)} program siaran untuk"
            f" {CHANNEL_ID}:\n"
            + "=" * 50
        )

        for idx, item in enumerate(items[:10], 1):
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
        print(f"[!] API mengembalikan pesan: {data.get('message')}")
    else:
      print(f"[!] Gagal mengambil jadwal. Respon: {res.text[:200]}")

  except Exception as e:
    print(f"[!] Terjadi kesalahan pada skrip uji coba: {e}")


if __name__ == "__main__":
  test_indonesiana_epg()
