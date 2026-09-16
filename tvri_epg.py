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

  all_channels_data = {}
  all_programs = []

  print("[*] Mengambil data EPG dari TVRI menggunakan Playwright...")

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
        all_channels_data[ch_id] = {"name": ch_name, "programs": []}

      for day in days:
        url = f"{base_url}?channel={ch_id}&day={day}"
        try:
          print(
              f"[*] Membuka halaman Channel {ch_name} (Hari ke-{day})..."
          )
          # Menggunakan domcontentloaded agar lebih cepat dan stabil
          page.goto(url, timeout=45000, wait_until="domcontentloaded")

          # Menunggu elemen Inertia / kontainer jadwal termuat di DOM
          page.wait_for_timeout(3000)

          # Mengambil data halaman melalui evaluasi script halaman (Inertia Props)
          # Atau membaca elemen HTML jika data dirender langsung ke DOM
          schedules = page.evaluate("""() => {
                        // Coba ambil dari data Inertia jika tersimpan di atribut div utama
                        let appDiv = document.querySelector('div[data-page]');
                        if (appDiv) {
                            try {
                                let pageData = JSON.parse(appDiv.getAttribute('data-page'));
                                return pageData.props.schedules || pageData.props.jadwal || [];
                            } catch(e) {}
                        }
                        return [];
                    }""")

          # Fallback jika tidak tertangkap via data-page, parsing langsung dari elemen HTML jadwal di DOM
          if not schedules:
            schedules = page.evaluate("""() => {
                        let items = [];
                        // Menyesuaikan struktur card jadwal di website TVRI
                        let rows = document.querySelectorAll('.group.relative.flex'); 
                        rows.forEach(row => {
                            let titleEl = row.querySelector('h3');
                            let descEl = row.querySelector('p');
                            let timeEls = row.querySelectorAll('span.font-mono');
                            if (titleEl && timeEls.length >= 2) {
                                items.push({
                                    title: titleEl.innerText.trim(),
                                    description: descEl ? descEl.innerText.trim() : '',
                                    start: timeEls[0].innerText.trim(),
                                    end: timeEls[1].innerText.trim(),
                                    date: new Date().toISOString().split('T')[0] // Default hari ini jika tidak terbaca
                                });
                            }
                        });
                        return items;
                    }""")

          print(
              f"[+] Berhasil mengambil Channel {ch_name} (Hari ke-{day}), total"
              f" jadwal ditemukan: {len(schedules)}"
          )

          for item in schedules:
            title = item.get("title")
            description = item.get("description", "")
            date_str = item.get("date")
            start_time = item.get("start")
            end_time = item.get("end")

            if title and start_time and end_time:
              # Jika date_str tidak ada dari DOM langsung, buat tanggal berdasarkan offset hari ke-n
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
  print(
      "[✓] File epg.xml berhasil dibuat dengan jadwal TVRI yang sesungguhnya!"
  )


if __name__ == "__main__":
  fetch_tvri_epg()
