from datetime import datetime, timedelta
import json
import xml.etree.ElementTree as ET
from playwright.sync_api import sync_playwright


def fetch_tvri_epg():
  base_url = "https://tvri.go.id/jadwal"
  channels = [
      {"id": 1, "name": "TVRI Nasional"},
  ]
  days = [1, 2, 3, 4, 5, 6, 7]

  all_channels_data = {1: {"name": "TVRI Nasional", "programs": []}}
  all_programs = []

  print(
      "[*] Mengambil data EPG dari TVRI menggunakan Playwright (Network"
      " Interception)..."
  )

  with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
        ],
    )
    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 720},
    )
    page = context.new_page()

    for ch in channels:
      ch_id = ch["id"]
      ch_name = ch["name"]

      for day in days:
        url = f"{base_url}?channel={ch_id}&day={day}"
        captured_data = []

        # Menangkap respons JSON dari request XHR/Inertia
        def handle_response(response):
          if "tvri.go.id/jadwal" in response.url and response.status == 200:
            try:
              # Cek apakah respons berupa JSON (Inertia request)
              if "application/json" in response.headers.get(
                  "content-type", ""
              ) or "text/json" in response.headers.get("content-type", ""):
                json_data = response.json()
                captured_data.append(json_data)
            except Exception:
              pass

        page.on("response", handle_response)

        try:
          print(
              f"[*] Membuka halaman Channel {ch_name} (Hari ke-{day})..."
          )
          # Mengirim header x-inertia agar server membalas dengan JSON
          page.set_extra_http_headers({
              "x-inertia": "true",
              "x-requested-with": "XMLHttpRequest",
          })
          page.goto(url, timeout=45000, wait_until="networkidle")

          schedules = []
          # Cari data jadwal dari payload Inertia yang tertangkap
          for data in captured_data:
            props = data.get("props", {})
            # Cek berbagai kemungkinan nama key jadwal
            raw_schedules = (
                props.get("schedules")
                or props.get("jadwal")
                or props.get("schedule", [])
            )
            if raw_schedules:
              schedules = raw_schedules
              break

          # Fallback jika tidak tertangkap di network, ambil dari tag div[data-page]
          if not schedules:
            page_content_json = page.evaluate("""() => {
                            let appDiv = document.querySelector('div[data-page]');
                            if (appDiv) {
                                try {
                                    return JSON.parse(appDiv.getAttribute('data-page'));
                                } catch(e) {}
                            }
                            return null;
                        }""")
            if page_content_json:
              props = page_content_json.get("props", {})
              schedules = (
                  props.get("schedules")
                  or props.get("jadwal")
                  or props.get("schedule", [])
              )

          print(
              f"[+] Berhasil memproses Channel {ch_name} (Hari ke-{day}), total"
              f" jadwal ditemukan: {len(schedules)}"
          )

          for item in schedules:
            title = (
                item.get("title")
                or item.get("nama_acara")
                or item.get("program_title")
            )
            description = (
                item.get("description")
                or item.get("deskripsi")
                or item.get("synopsis", "")
            )
            date_str = item.get("date") or item.get("tanggal")
            start_time = (
                item.get("start")
                or item.get("jam_mulai")
                or item.get("start_time")
            )
            end_time = (
                item.get("end")
                or item.get("jam_selesai")
                or item.get("end_time")
            )

            if title and start_time and end_time:
              if not date_str:
                target_date = datetime.now() + timedelta(days=(day - 1))
                date_str = target_date.strftime("%Y-%m-%d")

              try:
                start_dt = datetime.strptime(
                    f"{date_str} {start_time}", "%Y-%m-%d %H:%M"
                )
                end_dt = datetime.strptime(
                    f"{date_str} {end_time}", "%Y-%m-%d %H:%M"
                )

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
              except Exception:
                continue

        except Exception as e:
          print(f"[!] Error pada channel {ch_id} hari {day}: {e}")

    browser.close()

  # Generate XMLTV Format (epg.xml)
  print("[*] Membuat file epg.xml...")
  root = ET.Element("tv")

  for ch_id, info in all_channels_data.items():
    ch_elem = ET.SubElement(root, "channel", id=f"tvri_{ch_id}")
    display_name = ET.SubElement(ch_elem, "display-name")
    display_name.text = info["name"]

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

  tree = ET.ElementTree(root)
  ET.indent(tree, space="  ", level=0)
  tree.write("epg.xml", encoding="utf-8", xml_declaration=True)
  print("[✓] File epg.xml berhasil dibuat dengan jadwal lengkap TVRI!")


if __name__ == "__main__":
  fetch_tvri_epg()
