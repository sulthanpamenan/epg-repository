from datetime import datetime, timezone, timedelta
from playwright.sync_api import sync_playwright
import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom

def clean_text_str(text):
    if not text:
        return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")

def format_xmltv_date(dt, tz_str="+0700"):
    return dt.strftime(f"%Y%m%d%H%M%S {tz_str}")

def fetch_epg_indonesiana(target):
    epg_id, channel_code = target["id"], target["code"]
    channels = [{"id": epg_id, "name": target["name"]}]
    programmes = []

    auth_token = None
    print(f"[*] Indonesiana TV [{target['name']}]: Mengambil token via Playwright...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()

        def handle_response(response):
            nonlocal auth_token
            if "/v1/users/sessions/email" in response.url and response.status == 200:
                try:
                    res_json = response.json()
                    token = res_json.get("data", {}).get("accessSession", {}).get("token")
                    if token:
                        auth_token = token
                except Exception:
                    pass

        page.on("response", handle_response)

        try:
            page.goto("https://indonesiana.tv/auth/login", timeout=60000)
            page.wait_for_selector('input[type="email"]', timeout=15000)
            
            page.fill('input[type="email"]', "akun002fix@gmail.com")
            page.fill('input[type="password"]', "Akun002x")
            page.get_by_role("button", name="Masuk", exact=True).click()
            
            page.wait_for_timeout(6000)
            page.goto("https://indonesiana.tv/live", timeout=30000)
            page.wait_for_load_state("networkidle")
        except Exception as e:
            print(f"[!] Browser Error [{target['name']}]: {e}")
        finally:
            browser.close()

    if not auth_token:
        print(f"[!] Gagal mendapatkan token untuk {target['name']}.")
        return channels, programmes

    wib_tz = timezone(timedelta(hours=7))
    now_wib = datetime.now(timezone.utc).astimezone(wib_tz)

    start_timestamp = int(now_wib.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    end_timestamp = int(now_wib.replace(hour=23, minute=59, second=59, microsecond=0).timestamp())

    api_url = f"https://api.indonesianatv.app/v1/users/live-streams/{channel_code}/programs"
    params = {
        "filters[startDate]": start_timestamp,
        "filters[endDate]": end_timestamp,
        "skip": 0,
        "limit": 1000
    }

    headers = {
        "accept": "application/json, text/plain, */*",
        "authorization": f"Bearer {auth_token}",
        "origin": "https://indonesiana.tv",
        "referer": "https://indonesiana.tv/live",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    try:
        prog_res = requests.get(api_url, params=params, headers=headers, timeout=15)
        if prog_res.status_code == 200:
            prog_data = prog_res.json()
            if prog_data.get("success"):
                items = prog_data.get("data", {}).get("items", [])
                for item in items:
                    title = item.get("name")
                    start_str = item.get("startDate")
                    end_str = item.get("endDate")

                    if start_str and end_str and title:
                        start_dt = datetime.fromtimestamp(int(start_str), wib_tz)
                        stop_dt = datetime.fromtimestamp(int(end_str), wib_tz)

                        programmes.append({
                            "channel": epg_id,
                            "start": format_xmltv_date(start_dt, "+0700"),
                            "stop": format_xmltv_date(stop_dt, "+0700"),
                            "title": clean_text_str(title),
                            "desc": "",
                            "lang": "id"
                        })
                print(f"[✓] Berhasil memuat {len(programmes)} program untuk {target['name']}.")
    except Exception as e:
        print(f"[!] Error saat mengambil program: {e}")

    return channels, programmes

def generate_xml_file():
    targets = [
        {"id": "Indonesiana_MMF.id", "name": "Indonesiana MMF", "code": "MMF"},
        {"id": "Indonesiana_MKU.id", "name": "Indonesiana MKU", "code": "MKU"}
    ]

    all_channels = []
    all_programmes = []

    for t in targets:
        ch, pr = fetch_epg_indonesiana(t)
        all_channels.extend(ch)
        all_programmes.extend(pr)

    # Membangun struktur XMLTV
    root = ET.Element("tv")
    root.set("generator-info-name", "Indonesiana EPG Generator Local Test")

    for ch in all_channels:
        channel_elem = ET.SubElement(root, "channel", id=ch["id"])
        display_name = ET.SubElement(channel_elem, "display-name")
        display_name.text = ch["name"]

    for pr in all_programmes:
        prog_elem = ET.SubElement(root, "programme", start=pr["start"], stop=pr["stop"], channel=pr["channel"])
        title_elem = ET.SubElement(prog_elem, "title", lang=pr["lang"])
        title_elem.text = pr["title"]
        desc_elem = ET.SubElement(prog_elem, "desc", lang=pr["lang"])
        desc_elem.text = pr["desc"]

    # Pretty-print XML agar mudah dibaca
    rough_string = ET.tostring(root, encoding="utf-8")
    parsed = minidom.parseString(rough_string)
    pretty_xml = parsed.toprettyxml(indent="  ")

    output_filename = "epg_test.xml"
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(pretty_xml)

    print(f"\n[✓] Berhasil! File XML lokal tersimpan sebagai '{output_filename}'.")

if __name__ == "__main__":
    generate_xml_file()
