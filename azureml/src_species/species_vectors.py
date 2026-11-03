"""
樹種辨識：用 YOLO 樹幹分割去背 -> CLIP 取向量 -> 每個樹種取平均向量，存成 tree_vectors.pkl。
流程與 Morris 的 TreeIdentification notebook 相同（pkl 格式也一樣：{樹種名: 512 維 numpy 向量}），
另外多做兩件事：
  1. 留一法（leave-one-out）自我檢查：每張照片拿掉自己後，用其他照片的平均向量去分類，算各樹種正確率。
  2. 每個樹種存 3 張去背預覽圖，方便肉眼確認去背有沒有切歪。

資料集 zip 的結構：每個樹種一個資料夾，裡面放照片，例如
  樹種/榕樹/001.jpg、樹種/鳳凰木/143.jpg ...
"""
import argparse
import json
import pickle
import shutil
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image

IMG_EXT = {".jpg", ".jpeg", ".png"}


def fix_name(name: str) -> str:
    """Windows 舊版壓縮工具沒標 UTF-8 的中文檔名，Python 會當成 cp437 解讀而變亂碼，這裡嘗試還原。"""
    if all(ord(c) < 128 for c in name):
        return name
    try:
        raw = name.encode("cp437")
    except UnicodeEncodeError:
        return name
    for enc in ("utf-8", "cp950"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return name


def extract_zip(zip_path: Path, dest: Path) -> None:
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            name = info.filename if info.flag_bits & 0x800 else fix_name(info.filename)
            if "__MACOSX" in name or name.endswith("/"):
                continue
            target = dest / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)


def find_species(root: Path) -> dict:
    """直接放有照片的資料夾，資料夾名稱就是樹種名。"""
    species = defaultdict(list)
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix.lower() in IMG_EXT and "__MACOSX" not in p.parts:
            species[p.parent.name].append(p)
    return species


def segment_trunk(img_bgr, yolo, conf):
    """與 notebook 的 segment_tree 相同：取面積最大的 mask，其餘塗黑。"""
    res = yolo.predict(img_bgr, conf=conf, verbose=False)[0]
    if res.masks is None:
        return None
    masks = res.masks.data.cpu().numpy()
    best = masks[int(np.argmax([m.sum() for m in masks]))]
    mask = cv2.resize(best, (img_bgr.shape[1], img_bgr.shape[0]))
    mask = (mask > 0.5).astype(np.uint8) * 255
    return cv2.bitwise_and(img_bgr, img_bgr, mask=mask)


def to_clip_vector(img_bgr, clip_model, preprocess, device):
    # notebook 是先存成 jpg 再讀回來，這裡在記憶體裡走同一遍編碼，結果才一致
    ok, buf = cv2.imencode(".jpg", img_bgr)
    img = cv2.cvtColor(cv2.imdecode(buf, cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
    x = preprocess(Image.fromarray(img)).unsqueeze(0).to(device)
    with torch.no_grad():
        v = clip_model.encode_image(x)
        v = v / v.norm(dim=-1, keepdim=True)
    return v.cpu().numpy()[0]


def unit(v):
    return v / np.linalg.norm(v)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", required=True, help="樹種照片 zip（每個樹種一個資料夾）或已解壓縮的資料夾")
    p.add_argument("--yolo", required=True, help="樹幹分割模型 best.pt")
    p.add_argument("--output", required=True)
    p.add_argument("--clip", default="ViT-B/32", help="要與你們網頁使用的 CLIP 版本一致")
    p.add_argument("--conf", type=float, default=0.3)
    args = p.parse_args()

    import clip
    from ultralytics import YOLO

    out = Path(args.output)
    (out / "samples").mkdir(parents=True, exist_ok=True)
    work = Path("work")
    ds = Path(args.dataset)
    if ds.is_file():
        work.mkdir(exist_ok=True)
        print(f"[資料] 解壓縮 {ds}")
        extract_zip(ds, work / "data")
        root = work / "data"
    else:
        root = ds

    species = find_species(root)
    if not species:
        sys.exit("[錯誤] 資料集裡找不到任何 jpg/png 照片")
    print("[資料]", {k: len(v) for k, v in species.items()})

    device = "cuda" if torch.cuda.is_available() else "cpu"
    yolo = YOLO(args.yolo)
    clip_model, preprocess = clip.load(args.clip, device=device)
    print(f"[模型] YOLO={args.yolo}  CLIP={args.clip}  device={device}")

    vecs, failed = {}, {}
    for name, files in species.items():
        vecs[name], failed[name] = [], []
        for i, f in enumerate(files):
            img = cv2.imdecode(np.fromfile(str(f), dtype=np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                failed[name].append(f.name)
                continue
            seg = segment_trunk(img, yolo, args.conf)
            if seg is None:
                failed[name].append(f.name)
                continue
            vecs[name].append(to_clip_vector(seg, clip_model, preprocess, device))
            if len(vecs[name]) <= 3:
                cv2.imwrite(str(out / "samples" / f"{name}_{len(vecs[name])}.jpg"), seg)
        print(f"[向量] {name}：成功 {len(vecs[name])} 張，失敗 {len(failed[name])} 張")

    vecs = {k: np.array(v) for k, v in vecs.items() if len(v) > 0}
    tree_db = {k: unit(v.mean(axis=0)) for k, v in vecs.items()}
    with open(out / "tree_vectors.pkl", "wb") as f:
        pickle.dump(tree_db, f)
    print(f"[完成] tree_vectors.pkl：{len(tree_db)} 種")

    # 留一法自我檢查
    names = list(tree_db)
    correct = {k: 0 for k in names}
    total = {k: 0 for k in names}
    confusion = {k: defaultdict(int) for k in names}
    for k in names:
        v = vecs[k]
        if len(v) < 2:
            continue
        for i in range(len(v)):
            others = unit(np.delete(v, i, axis=0).mean(axis=0))
            scores = {n: float(v[i] @ (others if n == k else tree_db[n])) for n in names}
            pred = max(scores, key=scores.get)
            total[k] += 1
            correct[k] += pred == k
            confusion[k][pred] += 1
    per = {k: {"張數": len(vecs[k]), "失敗": len(failed[k]),
               "留一法正確率": round(correct[k] / total[k], 3) if total[k] else None,
               "被誤判成": {n: c for n, c in confusion[k].items() if n != k}} for k in names}
    tot = sum(total.values())
    report = {"clip": args.clip, "yolo": args.yolo, "樹種數": len(names),
              "整體留一法正確率": round(sum(correct.values()) / tot, 3) if tot else None,
              "各樹種": per}
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[檢查] 整體留一法正確率：", report["整體留一法正確率"])
    for k in names:
        print(f"   {k}: {per[k]['留一法正確率']}  誤判 {per[k]['被誤判成']}")


if __name__ == "__main__":
    main()
