"""SLCK (SelcukSportsHD) spor kaynagi botu.

Akis:
  1) Ana sayfadaki ``index.php?id=<kanal>`` baglantilarindan kanal ID'leri okunur.
  2) Her kanal icin ``<stream_domain>/live/<id>/playlist.m3u8`` GET ile dogrulanir.
     (Stream referer gerektirmez; player da ayni URL'yi referersiz ceker.)
  3) Domain, player.js'te saklanmadigi icin (WASM/protobuf sifreli /api/config)
     bilinen calisan domain + yedekler sirayla denenir.
  4) Hic calisan yayin yoksa DOSYA YAZILMAZ ve cikis 1 olur (eski liste korunur).
"""

import re
import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import urllib3
import warnings

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore")

HOME_URL = "https://www.selcuksportshdfe44b96fcb.xyz/"
OUTPUT_FILENAME = "5.m3u"
GROUP = "SLCK"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
    ),
    "Referer": HOME_URL,
}

# Stream domain'leri. Player bu domaini /api/config (WASM sifreli) icinden alir;
# bot dogrudan bilinen calisan domain(ler) ile denem yapar. Domain degisirse
# stream dogrulamasi basarisiz olur ve eski liste korunur.
STREAM_DOMAINS = [
    "https://dga1op10s1u3lea.9e694e1c2ce7ac.click",
    "https://dga1op10s1u3leo.77b6de8e471484.click",
]

# Ana sayfadaki selcuk* ID'leri icin gorunen adlar.
PRETTY_NAMES = {
    "selcukbeinsports1": "beIN Sports 1",
    "selcukbeinsports2": "beIN Sports 2",
    "selcukbeinsports3": "beIN Sports 3",
    "selcukbeinsports4": "beIN Sports 4",
    "selcukbeinsports5": "beIN Sports 5",
    "selcukbeinsportsmax1": "beIN Sports Max 1",
    "selcukbeinsportsmax2": "beIN Sports Max 2",
    "selcukbeinsportshaber": "beIN Sports Haber",
    "selcukbeinconnect1": "beIN Connect 1",
    "selcukssport": "S Sport",
    "selcukssport2": "S Sport 2",
    "selcukssplus1": "S Sport Plus 1",
    "selcukssplus2": "S Sport Plus 2",
    "selcukssplus3": "S Sport Plus 3",
    "selcukssplus4": "S Sport Plus 4",
    "selcukssplus5": "S Sport Plus 5",
    "selcukssplus6": "S Sport Plus 6",
    "selcukssplus7": "S Sport Plus 7",
    "selcukssplus8": "S Sport Plus 8",
    "selcukssplus9": "S Sport Plus 9",
    "selcukssplus10": "S Sport Plus 10",
    "selcuksmartspor": "Smart Spor",
    "selcuksmartspor2": "Smart Spor 2",
    "selcuktivibuspor": "Tivibu Spor",
    "selcuktivibuspor1": "Tivibu Spor 1",
    "selcuktivibuspor2": "Tivibu Spor 2",
    "selcuktivibuspor3": "Tivibu Spor 3",
    "selcuktivibuspor4": "Tivibu Spor 4",
    "selcukaspor": "A Spor",
    "selcukhtspor": "HT Spor",
    "selcuktrt1": "TRT 1",
    "selcuktrtavaz": "TRT Avaz",
    "selcuktrtspor": "TRT Spor",
    "selcuktrtspor2": "TRT Spor 2",
    "selcuktabiispor": "Tabii Spor",
    "selcuktabiispor1": "Tabii Spor 1",
    "selcuktabiispor2": "Tabii Spor 2",
    "selcuktabiispor3": "Tabii Spor 3",
    "selcuktabiispor4": "Tabii Spor 4",
    "selcuktabiispor5": "Tabii Spor 5",
    "selcuktabiispor6": "Tabii Spor 6",
    "selcuktabiispor7": "Tabii Spor 7",
}


def pretty(cid: str) -> str:
    return PRETTY_NAMES.get(cid.strip().lower(), cid.replace("selcuk", "").title())


def fetch_home():
    r = requests.get(HOME_URL, headers=HEADERS, timeout=25)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    return r.text


def parse_channel_ids(html):
    """Ana sayfadaki index.php?id=<kanal> baglantilarindan benzersiz selcuk* ID'leri."""
    ids = re.findall(r"index\.php\?id=([A-Za-z0-9_\-]+)", html)
    out, seen = [], set()
    for cid in ids:
        if not cid.lower().startswith("selcuk"):
            continue
        if cid in seen:
            continue
        seen.add(cid)
        out.append(cid)
    return out


def probe(domain, cid):
    """Stream dogrular; calisiyorsa tam URL dondurur."""
    url = f"{domain}/live/{cid}/playlist.m3u8"
    try:
        r = requests.get(url, headers=HEADERS, timeout=12, stream=True)
        if r.status_code != 200:
            return None
        chunk = next(r.iter_content(256), b"")
        if chunk.decode("utf-8", "replace").lstrip().startswith("#EXTM3U"):
            return url
    except Exception:
        return None
    return None


def resolve(cid):
    """Ilk calisan domain uzerinden URL bulur."""
    for domain in STREAM_DOMAINS:
        url = probe(domain, cid)
        if url:
            return cid, url
    return cid, None


def main():
    print("--- 🏟  SLCK (SelcukSportsHD) taraniyor ---")
    try:
        html = fetch_home()
    except Exception as e:
        print(f"❌ Ana sayfa erisilemiyor: {e}")
        print("❌ 5.m3u DEGISTIRILMIYOR")
        sys.exit(1)

    ids = parse_channel_ids(html)
    print(f"✅ {len(ids)} spor kanali bulundu")
    if not ids:
        print("❌ HIC KANAL YOK - 5.m3u DEGISTIRILMIYOR")
        sys.exit(1)

    entries = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(resolve, cid): cid for cid in ids}
        for fut in as_completed(futures):
            cid, url = fut.result()
            if url:
                entries.append((pretty(cid), url))
                print(f"  ✅ {pretty(cid)}")
            else:
                print(f"  ❌ {pretty(cid)} ({cid}): erisilemedi")

    if not entries:
        print("\n❌ HIC CALISAN YAYIN YOK - 5.m3u DEGISTIRILMIYOR")
        sys.exit(1)

    # Sirali ve okunabilir
    entries.sort(key=lambda x: x[0].lower())
    with open(OUTPUT_FILENAME, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for name, url in entries:
            f.write(f'#EXTINF:-1 group-title="{GROUP}", {name}\n{url}\n')

    print(f"\n✅ ISLEM TAMAMLANDI!  {len(entries)} yayin  ->  {os.path.abspath(OUTPUT_FILENAME)}")


if __name__ == "__main__":
    main()
