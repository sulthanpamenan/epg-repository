import json
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
import requests
import cloudscraper


def fetch_tvri_epg():
  # URL dasar endpoint jadwal TVRI
  base_url = "https://tvri.go.id/jadwal"

  # Header wajib agar server merespons dengan data Inertia.js (JSON)
  headers = {
      "accept": "text/html, application/xhtml+xml, application/xml;q=0.9,*/*;q=0.8",
      "accept-language": "id,en-US;q=0.9,en;q=0.8",
      "user-agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
          " (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
      ),
      "x-inertia": "true",
      "x-inertia-version": "5385cb76728424d96083121454968ca2",
      "x-requested-with": "XMLHttpRequest",
      "referer": "https://tvri.go.id/jadwal",
  }

  # Anda bisa menyesuaikan jumlah channel (biasanya ID channel berupa angka: 1, 2, dst.)
  # Serta rentang hari (day=1 sampai day=7, tergantung ketersediaan di web)
  channels = [
      {"id": 1, "name": "TVRI Nasional"},
      # Tambahkan ID channel lain jika ada di TVRI (misal: 2, 3, dll.)
  ]

  days = [1, 2, 3, 4, 5, 6, 7]  

  all_channels_data = {}
  all_programs = []

  print("[*] Mengambil data EPG dari TVRI...")

  for ch in channels:
    ch_id = ch["id"]
    ch_name = ch["name"]

    if ch_id not in all_channels_data:
      all_channels_data[ch_id] = {"name": ch_name, "programs": []}

    for day in days:
      url = f"{base_url}?channel={ch_id}&day={day}"
      try:
        scraper = cloudscraper.create_scraper()
        response = scraper.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
          # Respon Inertia.js berupa JSON
          data = response.json()

          # Navigasi ke props proporsional di dalam struktur Inertia response
          # Biasanya terletak di data['props'] (sesuaikan dengan struktur JSON aktual TVRI)
          props = data.get("props", {})

          # Contoh struktur props jadwal (biasanya berisi daftar jadwal atau tanggal)
          # Mengambil data jadwal dari respons JSON
          schedules = props.get("schedules", []) or props.get("jadwal", [])

          print(f"[+] Berhasil mengambil Channel {ch_name} (Hari ke-{day})")

          # Parsing struktur jadwal ke list program
          # (Struktur disesuaikan dengan key JSON dari TVRI)
          for item in schedules:
            title = item.get("title") or item.get("nama_acara")
            description = item.get("description") or item.get("deskripsi", "")
            date_str = item.get("date")  # Format tanggal YYYY-MM-DD
            start_time = item.get("start")  # Format HH:MM
            end_time = item.get("end")  # Format HH:MM

            if title and date_str and start_time and end_time:
              start_dt = datetime.strptime(
                  f"{date_str} {start_time}", "%Y-%m-%d %H:%M"
              )
              end_dt = datetime.strptime(
                  f"{date_str} {end_time}", "%Y-%m-%d %H:%M"
              )

              # Menangani jika waktu 'end' lebih kecil dari 'start' (lewat tengah malam)
              if end_dt <= start_dt:
                end_dt += timedelta(days=1)

              all_programs.append({
                  "channel_id": f"tvri_{ch_id}",
                  "channel_name": ch_name,
                  "title": title,
                  "desc": description,
                  "start": start_dt,
                  "stop": end_dt,
              })
        else:
          print(
              f"[!] Gagal mengambil Channel {ch_id} Hari {day} (Status:"
              f" {response.status_code})"
          )
      except Exception as e:
        print(f"[!] Error pada channel {ch_id} hari {day}: {e}")

  # Generate XMLTV Format (epg.xml)
  print("[*] Membuat file epg.xml...")
  root = ET.Element("tv")

  # Tambahkan informasi channel
  for ch_id, info in all_channels_data.items():
    ch_elem = ET.SubElement(root, "channel", id=f"tvri_{ch_id}")
    display_name = ET.SubElement(ch_elem, "display-name")
    display_name.text = info["name"]

  # Tambahkan informasi program (acara)
  for prog in all_programs:
    prog_elem = ET.SubElement(
        root,
        "programme",
        start=prog["start"].strftime("%Y%m%d%H%M%S +0700"),
        stop=prog["stop"].strftime("%Y%m%d%H%M%S +0700"),
        channel=prog["channel_id"],
    )

    title_elem = ET.SubElement(prog_elem, "title", lang="id")
    title_elem.text = prog["title"]

    if prog["desc"]:
      desc_elem = ET.SubElement(prog_elem, "desc", lang="id")
      desc_elem.text = prog["desc"]

  # Simpan ke file epg.xml
  tree = ET.ElementTree(root)
  ET.indent(tree, space="  ", level=0)
  tree.write("epg.xml", encoding="utf-8", xml_declaration=True)
  print("[✓] File epg.xml berhasil dibuat!")


if __name__ == "__main__":
  fetchri_epg = fetch_tvri_epg()