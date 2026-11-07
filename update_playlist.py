#!/usr/bin/env python3
"""Tải playlist gốc, lọc kênh cần dùng, ghi ra tv360-12.m3u (token luôn mới)."""
import os, re, sys, time, urllib.request

SOURCE_URL = os.environ.get("SOURCE_URL", "").strip()      # link gốc có u= & p= (để trong GitHub Secret)
SOURCE_FILE = os.environ.get("SOURCE_FILE", "").strip()    # chỉ dùng để test offline
# Danh sách regex tên kênh cần giữ, mỗi dòng 1 mẫu. Mặc định: đúng kênh TV360+12
CHANNELS = [p for p in os.environ.get("CHANNELS", r"^TV360\+12$").splitlines() if p.strip()]
OUTPUT = os.environ.get("OUTPUT", "tv360-12.m3u")

USER_AGENTS = ["Dalvik/2.1.0", "VLC/3.0.20 LibVLC/3.0.20",
               "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"]

def download():
    last = None
    for ua in USER_AGENTS:
        for _ in range(2):
            try:
                req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": ua, "Accept": "*/*"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    return r.read().decode("utf-8", "replace")
            except Exception as e:
                last = e
                time.sleep(3)
    sys.exit(f"Không tải được playlist gốc: {last}")

def parse(text):
    """Trả về list (tên, [các dòng của kênh])."""
    out, cur = [], None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF"):
            name = re.sub(r"\s+", " ", line.rsplit(",", 1)[-1]).strip()
            name = re.sub(r"\s*Update:.*$", "", name).strip()
            cur = (name, [line])
            out.append(cur)
        elif cur and line.startswith("#"):
            cur[1].append(line)
        elif cur:
            cur[1].append(line)
            cur = None
    return out

def main():
    if SOURCE_FILE:
        text = open(SOURCE_FILE, encoding="utf-8").read()
    elif SOURCE_URL:
        text = download()
    else:
        sys.exit("Thiếu SOURCE_URL")
    if "#EXTINF" not in text:
        sys.exit("Nội dung tải về không phải m3u. 300 ký tự đầu:\n" + text[:300])
    pats = [re.compile(p, re.I) for p in CHANNELS]
    keep = [(n, l) for n, l in parse(text) if any(p.search(n) for p in pats)]
    if not keep:
        sys.exit("Không tìm thấy kênh nào khớp, giữ nguyên file cũ.")
    lines = ["#EXTM3U"]
    for _, l in keep:
        lines += l
    open(OUTPUT, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print(f"Đã ghi {len(keep)} kênh vào {OUTPUT}")

if __name__ == "__main__":
    main()
