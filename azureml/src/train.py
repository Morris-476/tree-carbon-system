"""
在 Azure ML 上訓練 YOLO 樹幹分割模型（資料集：Roboflow Tree-Trunk-Train v2）。

這支程式由 submit_job.py 提交到 Azure ML 後在雲端執行，流程：
  1. 解壓縮 Roboflow 匯出的 zip
  2. 把 data.yaml 的相對路徑（../train/images）改成絕對路徑
  3. 用 Ultralytics 訓練
  4. 在 test 集上評估
  5. 把 best.pt、訓練曲線、評估結果寫到 --output 資料夾（Azure ML 會自動收走）

也可以在本機直接測試：
  python train.py --dataset Tree-Trunk-Train.v2i.yolov11.zip --output ./out --epochs 1
"""
import argparse
import json
import shutil
import sys
import zipfile
from pathlib import Path

import yaml


def prepare_dataset(dataset: Path, work_dir: Path) -> Path:
    """解壓縮資料集（若是 zip），回傳修正過路徑的 data.yaml。"""
    dataset = Path(dataset)
    if dataset.is_file() and dataset.suffix.lower() == ".zip":
        extract_dir = work_dir / "dataset"
        extract_dir.mkdir(parents=True, exist_ok=True)
        print(f"[資料] 解壓縮 {dataset} -> {extract_dir}")
        with zipfile.ZipFile(dataset) as zf:
            zf.extractall(extract_dir)
    elif dataset.is_dir():
        extract_dir = dataset
    else:
        sys.exit(f"[錯誤] 找不到資料集：{dataset}")

    yamls = sorted(extract_dir.rglob("data.yaml"), key=lambda p: len(p.parts))
    if not yamls:
        sys.exit("[錯誤] 資料集裡找不到 data.yaml")
    root = yamls[0].parent
    cfg = yaml.safe_load(yamls[0].read_text(encoding="utf-8"))

    train_dir, val_dir, test_dir = (root / "train/images", root / "valid/images", root / "test/images")
    for d in (train_dir, val_dir):
        if not d.is_dir():
            sys.exit(f"[錯誤] 找不到資料夾：{d}")

    fixed = {
        "path": root.resolve().as_posix(),
        "train": "train/images",
        "val": "valid/images",
        "names": cfg["names"],
    }
    if test_dir.is_dir():
        fixed["test"] = "test/images"

    for name, d in (("train", train_dir), ("valid", val_dir), ("test", test_dir)):
        if d.is_dir():
            n = sum(1 for p in d.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
            print(f"[資料] {name}: {n} 張")

    out = root / "data_fixed.yaml"
    out.write_text(yaml.safe_dump(fixed, allow_unicode=True), encoding="utf-8")
    print(f"[資料] 已產生 {out}")
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", required=True, help="Roboflow 匯出的 zip 檔，或已解壓縮的資料夾")
    p.add_argument("--output", required=True, help="輸出資料夾（模型與結果放這裡）")
    p.add_argument("--model", default="yolo11n-seg.pt", help="基底模型，請對照 Colab 上用的")
    p.add_argument("--epochs", type=int, default=100)
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--batch", type=int, default=16)
    p.add_argument("--patience", type=int, default=100)  # 與 Ultralytics 預設一致，100 epochs 內不會提早停止
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    work_dir = Path("work")
    work_dir.mkdir(exist_ok=True)

    data_yaml = prepare_dataset(Path(args.dataset), work_dir)

    from ultralytics import YOLO  # 延後 import，資料準備階段不需要它

    model = YOLO(args.model)
    model.train(
        data=str(data_yaml),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        patience=args.patience,
        workers=args.workers,
        seed=args.seed,
        project=str((work_dir / "runs").resolve()),
        name="trunk",
        exist_ok=True,
    )

    save_dir = Path(model.trainer.save_dir)
    best = save_dir / "weights" / "best.pt"
    if not best.exists():
        sys.exit(f"[錯誤] 訓練結束但找不到 {best}")

    # 訓練結束後 model 已載入 best.pt，這裡在 test 集（沒有的話用 val）評估
    split = "test" if "test" in yaml.safe_load(data_yaml.read_text(encoding="utf-8")) else "val"
    metrics = {"split": split}
    try:
        m = model.val(data=str(data_yaml), split=split, imgsz=args.imgsz)
        for key, obj, attr in (
            ("box_map50", m.box, "map50"),
            ("box_map50_95", m.box, "map"),
            ("seg_map50", m.seg, "map50"),
            ("seg_map50_95", m.seg, "map"),
        ):
            metrics[key] = float(getattr(obj, attr))
    except Exception as e:  # 評估失敗不應該讓整個訓練白費
        metrics["eval_error"] = str(e)
    print("[評估]", json.dumps(metrics, ensure_ascii=False))

    shutil.copy2(best, out_dir / "best.pt")
    shutil.copytree(save_dir, out_dir / "run", dirs_exist_ok=True)
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[完成] 模型已存到 {out_dir / 'best.pt'}")


if __name__ == "__main__":
    main()
