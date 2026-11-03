"""
把「樹種辨識向量庫」的建立提交到 Azure ML（用法與 submit_job.py 相同，Azure 資訊沿用同一份）。
這個任務只做推論（去背 + CLIP 取向量），不訓練，用便宜的 CPU 機型就夠。

  py submit_species_job.py --species-zip "C:/路徑/樹種.zip" --yolo "C:/路徑/best.pt"
  py submit_species_job.py --resume 任務名稱      # 即時日誌中斷時，只等待並下載
"""
import argparse

from azure.ai.ml import Input, Output, command
from azure.ai.ml.constants import AssetTypes, InputOutputModes
from azure.ai.ml.entities import Environment, JobResourceConfiguration

from submit_job import download_result, get_client, wait_for_job


def build_job(args):
    env = Environment(
        name="yolo-clip-species-env",
        image="pytorch/pytorch:2.4.0-cuda12.1-cudnn9-runtime",
        description="PyTorch + ultralytics + CLIP（用 clip-anytorch，免裝 git）",
    )
    cmd = (
        "pip install -q ultralytics ftfy regex tqdm clip-anytorch "
        "&& pip uninstall -y -q opencv-python "
        "&& pip install -q opencv-python-headless "
        "&& python species_vectors.py "
        "--dataset ${{inputs.species}} --yolo ${{inputs.yolo}} "
        "--output ${{outputs.result}} --clip ${{inputs.clip}}"
    )
    return command(
        display_name="tree-species-vectors",
        experiment_name=args.experiment_name,
        code="./src_species",
        command=cmd,
        environment=env,
        inputs={
            "species": Input(type=AssetTypes.URI_FILE, path=args.species_zip, mode=InputOutputModes.DOWNLOAD),
            "yolo": Input(type=AssetTypes.URI_FILE, path=args.yolo, mode=InputOutputModes.DOWNLOAD),
            "clip": args.clip,
        },
        outputs={"result": Output(type=AssetTypes.URI_FOLDER)},
        resources=JobResourceConfiguration(instance_type=args.instance_type, instance_count=1),
        shm_size="4g",
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--species-zip", help="樹種照片 zip（每個樹種一個資料夾）")
    p.add_argument("--yolo", help="樹幹分割模型 best.pt")
    p.add_argument("--clip", default="ViT-B/32")
    p.add_argument("--instance-type", default="Standard_DS3_v2")
    p.add_argument("--experiment-name", default="tree-species-vectors")
    p.add_argument("--resume", metavar="RUN_NAME")
    p.add_argument("--no-wait", action="store_true")
    p.add_argument("--download-to", default="./results_species")
    args = p.parse_args()

    if not args.resume and not (args.species_zip and args.yolo):
        raise SystemExit("提交新任務需要 --species-zip 與 --yolo；只是等待既有任務請用 --resume 任務名稱")

    ml_client = get_client()
    if args.resume:
        name = args.resume
    else:
        job = ml_client.create_or_update(build_job(args))
        name = job.name
        print("已提交，Studio 連結：", job.studio_url)
        print("任務名稱：", name, "  ← 之後可用 --resume", name)
    if args.no_wait:
        return
    status = wait_for_job(ml_client, name)
    if status == "Completed":
        try:
            ml_client.jobs.download(name=name, download_path=args.download_to, output_name="result")
            print(f"完成，結果在 {args.download_to}（tree_vectors.pkl、report.json、samples/）")
        except Exception as e:
            print(f"[提示] 自動下載失敗：{type(e).__name__}: {str(e)[:200]}，請到 Studio 的輸出頁面手動下載 result 資料夾")
    else:
        print(f"任務結束，狀態：{status}。請到 Studio 看錯誤訊息。")


if __name__ == "__main__":
    main()
