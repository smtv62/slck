import requests, re, os, sys, warnings
warnings.filterwarnings("ignore")

"""
selcuk.py - slck (smtv62/slck) için M3U guncelleyici.

Yapısal değişimler (player 2.x -> 3.x):
  - onceki baseStreamUrl yolu baska bir yapıya geçti.
  - Şu anki akış: ana sayfa -> uxsyplayer domain -> index.php -> player.js -> dinamik source.

  Bu sürümde:
  1) Ana sayfadan player domain'i bulunur.
  2) index.php sayfasını açar (player container).
  3) player.js dosyasını çeker; source URL'leri doğrudan çıkarılamıyorsa
     mevcut 5.m3u onbelleğinin içini korur (dosya değişmez).
  4) Hicbir calisani kanalsa dosya yazmaz ve sys.exit(1) cikis yapar
     (eski liste korunur).
"""

HOME_URL = "https://www.selcuksportshdfe44b96fcb.xyz/"
PLAYER_BASE = "https://main.uxsyplayer6859599e6c.click"
OUTPUT_FILE = "5.m3u"
GROUP = "SLCK"


def fetch_home():
    r = requests.get(HOME_URL, headers={"User-Agent": "Mozilla/5.0", "Referer": HOME_URL}, timeout=25)
    r.raise_for_status()
    return r.text


def find_player_domain(html):
    """Sayfada geçen uxsyplayer domain'ini bul."""
    for m in re.finditer(r'https?://[a-z0-9.\-]+[a-z0-9.]*(?:uxsy[a-z0-9.]*)?', html, re.I):
        u = m.group(0)
        if 'uxsy' in u.lower():
            return u
    return None


def fetch_player_index(referer):
    """player index.php sayfasını aç."""
    # player domain'i yoksa ana sayfadaki varsayılanı kullan
    domain = find_player_domain(fetch_home()) or PLAYER_BASE
    try:
        r = requests.get(f"{domain}/index.php", headers={"User-Agent": "Mozilla/5.0", "Referer": referer}, timeout=20)
        return r.text, domain
    except Exception as e:
        return None, None


def extract_m3u_from_player(page_html):
    """player sayfasından direkt m3u8 URL çıkarimi (şu an desteklenmiyor)."""
    # player JS içinde baseUrl, source vs arıyoruz ama yapı değişken olduğu için
    # doğrudan m3u8 bulamıyoruz. Bulunursa döndür.
    for m in re.finditer(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', page_html, re.I):
        return m.group(0)
    return None


def update_m3u_referer(m3u_path, new_referer):
    """Mevcut 5.m3u'deki EXTVLCOPT referer'leri güncelle."""
    if not os.path.exists(m3u_path):
        return False
    with open(m3u_path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    new_lines = []
    i = 0
    changed = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("#EXTVLCOPT:http-referrer"):
            # sonraki satiri da URL olarak kabul et
            if i + 1 < len(lines) and lines[i + 1].startswith("http"):
                new_lines.append(f"#EXTVLCOPT:http-referrer= {new_referer}")
                new_lines.append(lines[i + 1])
                i += 2
                changed += 1
                continue
        new_lines.append(line)
        i += 1

    if changed > 0:
        with open(m3u_path, "w", encoding="utf-8") as f:
            f.write("\n".join(new_lines))
        return True
    return False


def main():
    print("--- 🏟  SLCK (selcuk) taraniyor ---")
    try:
        home = fetch_home()
    except Exception as e:
        print(f"❌ Ana sayfa erisilemiyor: {e}")
        print("   Mevcut 5.m3u onbellegi korunuyor.")
        sys.exit(1)

    # player domain'i ara
    player_domain = find_player_domain(home)
    if not player_domain:
        print("⚠️ Player domain sayfada bulunamadi; varsayilan kullaniliyor.")
        player_domain = PLAYER_BASE

    print(f"✅ Player domain: {player_domain}")

    # index.php sayfası
    page_html, _ = fetch_player_index(HOME_URL)
    if not page_html:
        print("⚠️ Player index.php sayfasi erisilemiyor.")
        print("   Mevcut 5.m3u onbellegi korunuyor.")
        sys.exit(1)

    # player.js'yi çek
    scripts = re.findall(r'<script[^>]+src="([^"]+)"', page_html, re.I)
    player_js_url = None
    for s in scripts:
        if "player" in s.lower() and ".js" in s.lower():
            # URL temizle: ./ ve ../ kaldir
            clean = s.replace("./", "").replace("../", "")
            player_js_url = clean if clean.startswith("http") else HOME_URL.rstrip("/") + "/" + clean.lstrip("/")
            break

    if not player_js_url:
        print("⚠️ player.js URL bulunamadi.")
        print("   Mevcut 5.m3u onbellegi korunuyor.")
        sys.exit(1)

    print(f"✅ player.js: {player_js_url}")
    try:
        rj = requests.get(player_js_url, headers={"User-Agent": "Mozilla/5.0", "Referer": page_html}, timeout=30)
    except Exception as e:
        print(f"⚠️ player.js indirilemiyor: {e}")
        print("   Mevcut 5.m3u onbellegi korunuyor.")
        sys.exit(1)

    # player.js'ten m3u8 çıkarımı dene
    extracted = extract_m3u_from_player(rj.text)
    if extracted:
        print(f"✅ player.js'den m3u8 bulunandi: {extracted}")
        # Yeni m3u dosyası yaz (basit yapida)
        m3u_content = "#EXTM3U\n#EXTINF:-1 group-title=\"SLCK\", Yeni Yayin\n" + extracted + "\n"
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(m3u_content)
        print(f"✅ {OUTPUT_FILE} yenileildi ({len(m3u_content)} bayt)")
    else:
        print("⚠️ player.js'den m3u8 cikarilamadi.")
        print("   Mevcut 5.m3u onbellegi korunuyor (dosya degistirilmemesi).")
        # Mevcut dosyayı koru - yazma yapma, exit 1 ile liste korunur
        if os.path.exists(OUTPUT_FILE):
            print(f"   Mevcut {OUTPUT_FILE} ({os.path.getsize(OUTPUT_FILE)} bayt) korunuyor.")
        else:
            print("   5.m3u dosyasi yok, yeni olusturulamaz.")
        sys.exit(1)


if __name__ == "__main__":
    main()