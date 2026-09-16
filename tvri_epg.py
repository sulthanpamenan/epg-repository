from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
from playwright.sync_api import sync_playwright


def fetch_tvri_epg():
  base_url = "https://tvri.go.id/jadwal"

  # Daftar channel TVRI (Nasional, Sport, dan Daerah seperti Riau dengan ID 33)
  channels = [
      {"id": 1, "name": "TVRI Nasional"},
      {"id": 2, "name": "TVRI DKI Jakarta"},
      {"id": 3, "name": "TVRI Sport HD"},
      {"id": 33, "name": "TVRI Riau"},  # Contoh channel daerah
      # Anda bisa menambahkan ID channel lain sesuai kebutuhan
  ]

  # Hari di web TVRI menggunakan skala 0 (Minggu) sampai 6 (Sabtu)
  days = [0, 1, 2, 3, 4, 5, 6]

  all_channels_data = {}
  all_programs = []

  print(
      "[*] Memulai pengambilan data EPG TVRI melalui ekstraksi DOM Playwright..."
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

      if ch_id not in all_channels_data:
        all_channels_data[ch_id] = {"name": ch_name}

      for day in days:
        url = f"{base_url}?channel={ch_id}&day={day}"
        try:
          print(
              f"[*] Mengakses {ch_name} (Channel ID: {ch_id}, Day Index: {day})..."
          )
          page.goto(url, timeout=45000, wait_until="domcontentloaded")
          page.wait_for_timeout(3000)  # Waktu tunggu render DOM Vue.js

          # Ekstraksi elemen jadwal dari DOM HTML situs TVRI
          schedules = page.evaluate("""() => {
                        let items = [];
                        let rows = document.querySelectorAll('div.group.relative.flex');
                        
                        rows.forEach(row => {
                            let titleEl = row.querySelector('h3');
                            let descEl = row.querySelector('p');
                            let timeContainer = row.querySelectorAll('span.font-mono');
                            let timeTexts = [];
                            
                            timeContainer.forEach(span => {
                                timeTexts.push(span.innerText.trim());
                            });

                            if (timeTexts.length < 2) {
                                let allSpans = row.querySelectorAll('span');
                                allSpans.forEach(span => {
                                    let txt = span.innerText.trim();
                                    if (/^\\d{2}:\\d{2}$/.test(txt)) {
                                        timeTexts.push(txt);
                                    }
                                });
                            }

                            if (titleEl && timeTexts.length >= 2) {
                                items.push({
                                    title: titleEl.innerText.trim(),
                                    description: descEl ? descEl.innerText.trim() : '',
                                    start: timeTexts[0],
                                    end: timeTexts[1]
                                });
                            }
                        });
                        return items;
                    }""")

          print(
              f"[+] Ditemukan {len(schedules)} jadwal untuk {ch_name} (Day:"
              f" {day})"
          )

          for item in schedules:
            title = item.get("title")
            description = item.get("description", "")
            start_time = item.get("start")
            end_time = item.get("end")

            if title and start_time and end_time:
              # Penyesuaian tanggal berdasarkan indeks hari (0 = Minggu)
              today = datetime.now()
              current_weekday = (today.weekday() + 1) % 7
              days_diff = (day - current_weekday) % 7
              target_date = today + timedelta(days=days_diff)
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
          print(f"[!] Gagal pada channel {ch_id} day {day}: {e}")

    browser.close()

  # Pembuatan format file XMLTV (epg.xml)
  print("[*] Menyusun file epg.xml...")
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
  print(
      "[✓] File epg.xml berhasil dibuat dengan data lengkap dari seluruh"
      " channel TVRI!"
  )


if __name__ == "__main__":
  fetch_tvri_epg()
