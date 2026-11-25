#!/usr/bin/env python3
"""Tải playlist gốc, lọc kênh cần dùng, ghi ra tv360-12.m3u và chèn kênh dự phòng vào playlist tổng truyenhinh.m3u (token luôn mới)."""
import os, re, sys, time, unicodedata, urllib.request

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
    """Trả về list (tên, [các dòng của kênh]). Dòng URL luôn được đặt cuối khối,
    nên nguồn để #KODIPROP/#EXTVLCOPT sau URL vẫn đọc đủ."""
    blocks, cur = [], None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF"):
            cur = [line, [], []]            # extinf, các dòng #, các dòng url
            blocks.append(cur)
        elif cur is not None:
            (cur[1] if line.startswith("#") else cur[2]).append(line)
    out = []
    for ext, opts, urls in blocks:
        if not urls:
            continue
        name = re.sub(r"\s+", " ", ext.rsplit(",", 1)[-1]).strip()
        name = re.sub(r"\s*Update:.*$", "", name).strip()
        out.append((name, [ext] + opts + urls))
    return out

def norm(t):
    """Chuẩn hóa unicode (NFC) để regex tiếng Việt khớp dù nguồn gõ dấu kiểu nào."""
    return unicodedata.normalize("NFC", t)

def rename_entry(lines, new_name):
    """Đổi tên hiển thị của 1 kênh (dòng #EXTINF), giữ nguyên các dòng còn lại."""
    out = list(lines)
    head = out[0].rsplit(",", 1)[0]
    head = re.sub(r'tvg-name="[^"]*"', f'tvg-name="{new_name}"', head)
    out[0] = head + "," + new_name
    return out

def set_group(lines, group):
    """Đặt group-title cho kênh (thêm mới nếu dòng #EXTINF chưa có)."""
    out = list(lines)
    head, name = out[0].rsplit(",", 1)
    if re.search(r'group-title="[^"]*"', head):
        head = re.sub(r'group-title="[^"]*"', f'group-title="{group}"', head)
    else:
        head += f' group-title="{group}"'
    out[0] = head + "," + name
    return out

def merge(base_path, specs, channels):
    """Lấy playlist tổng (base_path), chèn kênh mới từ nguồn vào. Trả về list (tên, dòng) hoặc None.

    Mỗi spec trong "channels":
      match   : regex tên kênh
      match_group : regex group-title gốc của nguồn (kênh khớp match HOẶC match_group đều được lấy)
      exclude : regex loại bớt (tùy chọn)
      all     : true = lấy TẤT CẢ kênh khớp (mặc định chỉ lấy kênh đầu tiên)
      group   : đặt group-title cho các kênh lấy được (tùy chọn)
      rename  : đổi tên (chỉ dùng khi không có "all")
      after   : chèn sau kênh có tên này, không có thì chèn cuối danh sách
    """
    base = parse(open(base_path, encoding="utf-8").read())
    added = 0
    for sp in specs:
        pat = re.compile(norm(sp["match"]), re.I) if sp.get("match") else None
        gpat = re.compile(norm(sp["match_group"]), re.I) if sp.get("match_group") else None
        exc = re.compile(norm(sp["exclude"]), re.I) if sp.get("exclude") else None
        def ok(n, l):
            gm = re.search(r'group-title="([^"]*)"', l[0])
            g = norm(gm.group(1)) if gm else ""
            return bool((pat and pat.search(norm(n))) or (gpat and gpat.search(g)))
        hits = [(n, l) for n, l in channels
                if ok(n, l) and not (exc and exc.search(norm(n)))]
        if not hits:
            print(f"  Không thấy kênh khớp {sp.get('match') or sp.get('match_group')} trong nguồn, bỏ qua.")
            continue
        if not sp.get("all"):
            hits = hits[:1]
        pos_name = sp.get("after")
        for n, l in hits:
            name = (sp.get("rename") if not sp.get("all") else None) or n
            lines = rename_entry(l, name) if name != n else list(l)
            if sp.get("group"):
                lines = set_group(lines, sp["group"])
            base = [(bn, bl) for bn, bl in base if bn != name]   # xóa bản cũ (nếu có) trước khi chèn
            pos = next((i for i, (bn, _) in enumerate(base) if bn == pos_name), None)
            base.insert(len(base) if pos is None else pos + 1, (name, lines))
            pos_name = name            # kênh sau nằm ngay sau kênh vừa chèn -> giữ đúng thứ tự nguồn
            added += 1
        if sp.get("group"):
            print(f"  [{sp['group']}] +{len(hits)} kênh: " + ", ".join(n for n, _ in hits))
    return base if added else None

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
    if os.environ.get("LIST_NAMES"):
        print("Các kênh trong nguồn:", " | ".join(n for n, _ in channels))
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    written = 0
    for filename, patterns in config.items():
        if "/" in filename or not filename.endswith(".m3u"):
            print(f"Bỏ qua tên file không hợp lệ: {filename}")
            continue
        if isinstance(patterns, dict):      # kiểu gộp vào playlist tổng: {"base": "...", "channels": [...]}
            keep = merge(patterns["base"], patterns["channels"], channels)
            if keep is None:
                print(f"{filename}: nguồn không có kênh cần chèn, giữ nguyên file cũ trên nhánh.")
                continue
        else:                               # kiểu cũ: chỉ lọc kênh theo regex
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
