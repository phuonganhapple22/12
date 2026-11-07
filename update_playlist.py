#!/usr/bin/env python3
"""Tải playlist gốc, lọc kênh cần dùng, ghi ra tv360-12.m3u (token luôn mới)."""
import os, re, sys, time, urllib.request

SOURCE_URL = os.environ.get("SOURCE_URL", "").strip()      # link gốc có u= & p= (để trong GitHub Secret)
SOURCE_FILE = os.environ.get("SOURCE_FILE", "").strip()    # chỉ dùng để test offline
# File cấu hình: {"tên-file.m3u": ["regex tên kênh", ...], ...}
# Muốn thêm 1 file m3u mới chỉ cần thêm 1 dòng vào playlists.json.
CONFIG = os.environ.get("CONFIG", "playlists.json")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "out")

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
    import json
    config = json.load(open(CONFIG, encoding="utf-8"))
    channels = parse(text)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    written = 0
    for filename, patterns in config.items():
        if "/" in filename or not filename.endswith(".m3u"):
            print(f"Bỏ qua tên file không hợp lệ: {filename}")
            continue
        pats = [re.compile(p, re.I) for p in patterns]
        keep = [(n, l) for n, l in channels if any(p.search(n) for p in pats)]
        if not keep:
            print(f"{filename}: không có kênh khớp, giữ nguyên file cũ trên nhánh.")
            continue
        lines = ["#EXTM3U"]
        for _, l in keep:
            lines += l
        with open(os.path.join(OUTPUT_DIR, filename), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"{filename}: {len(keep)} kênh")
        written += 1
    if not written:
        sys.exit("Không ghi được file nào.")

if __name__ == "__main__":
    main()
