# 📺 Universal IPTV EPG Generator & Repository

Automated XMLTV Electronic Program Guide (`epg.xml`) generated from official television schedule sources. Refreshed automatically every 6 hours via GitHub Actions.

---

## 🔗 EPG Import Link

Use the link below in your IPTV player (TiviMate, OTT Navigator, VLC, IPTV Smarters, etc.):

* **XMLTV EPG URL**:
  `https://sulthanpamenan.github.io/epg-repository/epg.xml`

---

## 📺 M3U Playlist Integration

Add the `url-tvg` link to your M3U header and match the `tvg-id` with the corresponding EPG channel ID:

#EXTM3U url-tvg="https://sulthanpamenan.github.io/epg-repository/epg.xml"

#EXTINF:-1 tvg-id="ChannelID.country" tvg-name="Channel Name" tvg-logo="https://..." group-title="Category",Channel
https://example.com/stream.m3u8

---

## ⚡ Key Features

* **Automated 24/7 Updates**: Refreshes every **6 hours** via GitHub Actions.
* **Auto Timezone Alignment**: Configured with standard ISO 8601 UTC offsets (`+0700`, `+0800`, `+0000`) so your IPTV player automatically converts program times to your local device timezone.
* **Standard XMLTV Format**: Compatible with all major M3U/XMLTV-supported IPTV applications.

---

## 🛠️ Adding New Channels

To register a new channel schedule, add its target configuration to `EPG_TARGET_SOURCES` inside `generate_epg.py`:

    {
        "id": "ChannelID.country",
        "name": "Channel Name",
        "url": "https://website.com/schedule",
        "icon": "",
        "utc_offset": "+0700"
    }

---

## ☕ Support the Developer

If this project is helpful to you, consider supporting the developer to keep this repository maintained!

<div align="center">

### 🇮🇩 Local Donation (QRIS / E-Wallet / Mobile Banking)

<a href="https://saweria.co/sulthanpamenan" target="_blank">
  <img width="290" height="290" alt="Saweria QRIS" src="https://github.com/user-attachments/assets/f2846d1f-a391-4daf-9ce5-a48aadc992a0" />
</a>

<br>

*Scan the QRIS code above using GoPay, DANA, OVO, ShopeePay, LinkAja, or Mobile Banking.*

<br>

<a href="https://saweria.co/sulthanpamenan" target="_blank">
  <img src="https://img.shields.io/badge/Saweria-Support_Project-orange?style=for-the-badge&logo=coffee" alt="Support via Saweria">
</a>

---

### 🌐 International Donation

<a href="https://buymeacoffee.com/sulthanpamenan" target="_blank">
  <img src="https://img.shields.io/badge/Buy_Me_A_Coffee-Donate-yellow?style=for-the-badge&logo=buy-me-a-coffee" alt="Buy Me A Coffee">
</a>

</div>

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

## ⚠️ Disclaimer

This repository only generates metadata and electronic program guide (EPG) schedules. It does not host, stream, or broadcast any media content. All schedule data belongs to its respective copyright owners.
