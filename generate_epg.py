import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timedelta

# Daftar ID dan Nama Channel Red Bull TV
channels = [
    ("RedBullTV.global", "Red Bull TV: World of Red Bull"),
    ("RedBullPadel.global", "Red Bull TV: Padel"),
    ("RedBullBike.global", "Red Bull TV: Bike"),
    ("RedBullAdventure.global", "Red Bull TV: Adventure"),
    ("RedBullMotorsports.global", "Red Bull TV: Motorsports"),
    ("RedBullSurfing.global", "Red Bull TV: Surfing"),
    ("RedBullSkateboarding.global", "Red Bull TV: Skateboarding"),
    ("RedBullWinter.global", "Red Bull TV: Winter"),
    ("RedBullActionReel.global", "Red Bull TV: Action Reel")
]

# Inisialisasi Root Element XML
tv = ET.Element("tv", {"generator-info-name": "Python EPG Generator"})

# 1. Generate Tag <channel>
for ch_id, ch_name in channels:
    channel_elem = ET.SubElement(tv, "channel", id=ch_id)
    display_elem = ET.SubElement(channel_elem, "display-name", lang="en")
    display_elem.text = ch_name

# 2. Generate Tag <programme> Otomatis (Contoh Jadwal 7 Hari Ke Depan)
now = datetime.utcnow()
for days in range(7):
    current_day = now + timedelta(days=days)
    start_str = current_day.strftime("%Y%m%d000000 +0000")
    stop_str = current_day.strftime("%Y%m%d235959 +0000")

    for ch_id, ch_name in channels:
        prog_elem = ET.SubElement(tv, "programme", {
            "start": start_str,
            "stop": stop_str,
            "channel": ch_id
        })
        title_elem = ET.SubElement(prog_elem, "title", lang="en")
        title_elem.text = f"{ch_name} Live Stream"
        
        desc_elem = ET.SubElement(prog_elem, "desc", lang="en")
        desc_elem.text = f"Non-stop streaming content for {ch_name}."

# Format Output agar Rapi (Pretty Print XML)
xml_str = minidom.parseString(ET.tostring(tv, 'utf-8')).toprettyxml(indent="  ")

# Simpan ke File XML
with open("redbull_epg.xml", "w", encoding="utf-8") as f:
    f.write(xml_str)

print("File redbull_epg.xml berhasil dibuat!")
