"""
把樹幹分割模型的訓練任務提交到 Azure Machine Learning（serverless 運算，不用先建叢集）。

用法（在你自己的電腦上執行）：
  pip install azure-ai-ml azure-identity
  az login                      # 沒有 Azure CLI 的話，程式會改開瀏覽器登入
  python submit_job.py --dataset-zip "C:/Users/你/Downloads/Tree-Trunk-Train.v2i.yolov11.zip"
  python submit_job.py --resume 任務名稱      # 即時日誌中斷時，不重新提交，只等待並下載

先把下面三個 Azure 資訊填好（Azure 入口網站 -> 你的 Machine Learning 工作區 -> 概觀）。
"""
import argparse
import os
import time

from azure.ai.ml import Input, MLClient, Output, command
from azure.ai.ml.constants import AssetTypes, InputOutputModes
from azure.ai.ml.entities import Environment, JobResourceConfiguration
from azure.identity import DefaultAzureCredential, InteractiveBrowserCredential

# ======== 請填入你的 Azure 資訊（也可以用同名環境變數）========
SUBSCRIPTION_ID = os.environ.get("AZURE_SUBSCRIPTION_ID", "9d01ebd4-a737-41d3-8644-6aed3edc92c5")
RESOURCE_GROUP = os.environ.get("AZURE_RESOURCE_GROUP", "tree-trunk")
WORKSPACE_NAME = os.environ.get("AZURE_ML_WORKSPACE", "tku-tree-trunk")
# ==============================================================


def get_client() -> MLClient:
    try:
        credential = DefaultAzureCredential()
        credential.get_token("https://management.azure.com/.default")
    except Exception:
        credential = InteractiveBrowserCredential()
    return MLClient(credential, SUBSCRIPTION_ID, RESOURCE_GROUP, WORKSPACE_NAME)


def build_job(args):
    # 用 Docker Hub 的 PyTorch+CUDA 映像檔，開機後再裝 ultralytics。
    # 換成 opencv-python-headless 是因為雲端容器通常沒有 libGL，裝一般版的 opencv 會 import 失敗。
    env = Environment(
        name="yolo-trunk-train-env",
        image="pytorch/pytorch:2.4.0-cuda12.1-cudnn9-runtime",
        description="PyTorch 2.4 + CUDA 12.1，ultralytics 在 job 啟動時安裝",
    )

    cmd = (
        "pip install -q ultralytics "
        "&& pip uninstall -y -q opencv-python "
        "&& pip install -q opencv-python-headless "
        "&& python train.py "
        "--dataset ${{inputs.dataset}} "
        "--output ${{outputs.model_output}} "
        "--model ${{inputs.model}} "
        "--epochs ${{inputs.epochs}} "
        "--imgsz ${{inputs.imgsz}} "
        "--batch ${{inputs.batch}}"
    )

    return command(
        display_name="trunk-seg-train-v2",
        experiment_name=args.experiment_name,
        code="./src",  # 只上傳 src 資料夾（裡面只有 train.py），不要把 844MB 的 zip 一起包進去
        command=cmd,
        environment=env,
        inputs={
            # 本機路徑會在提交時自動上傳到工作區的預設儲存空間
            "dataset": Input(type=AssetTypes.URI_FILE, path=args.dataset_zip, mode=InputOutputModes.DOWNLOAD),
            "model": args.model,
            "epochs": args.epochs,
            "imgsz": args.imgsz,
            "batch": args.batch,
        },
        outputs={"model_output": Output(type=AssetTypes.URI_FOLDER)},
        # 不指定 compute = 使用 serverless；這裡指定 GPU 機型
        resources=JobResourceConfiguration(instance_type=args.instance_type, instance_count=1),
        shm_size="8g",  # YOLO 的 dataloader 需要較大的共用記憶體，預設值太小會當掉
    )


TERMINAL_STATES = {"Completed", "Failed", "Canceled", "NotResponding"}


def wait_for_job(ml_client, name, poll_seconds=30):
    """先試著即時顯示雲端日誌；失敗的話（不影響雲端任務）就改成定時查狀態，回傳最後狀態。"""
    try:
        ml_client.jobs.stream(name)
    except Exception as e:  # 日誌串流失敗或任務失敗都會到這裡，狀態以下面查到的為準
        print(f"[提示] 即時日誌中斷：{type(e).__name__}: {str(e)[:200]}")
        print(f"[提示] 雲端任務不受影響，改成每 {poll_seconds} 秒查一次狀態（Ctrl+C 可停止等待）")
    last = None
    while True:
        status = ml_client.jobs.get(name).status
        if status != last:
            print(time.strftime("%H:%M:%S"), "任務狀態：", status)
            last = status
        if status in TERMINAL_STATES:
            return status
        time.sleep(poll_seconds)


def download_result(ml_client, name, download_to):
    try:
        ml_client.jobs.download(name=name, download_path=download_to, output_name="model_output")
        print(f"完成，模型在 {download_to}（best.pt 與 metrics.json）")
    except Exception as e:
        print(f"[提示] 自動下載失敗：{type(e).__name__}: {str(e)[:200]}")
        print("可以到 Studio 的任務頁面 -> 輸出 + 記錄（Outputs + logs）-> 下載 model_output 資料夾")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dataset-zip", help="Roboflow 匯出的 zip 檔路徑（提交新任務時必填）")
    p.add_argument("--instance-type", default="Standard_NC4as_T4_v3", help="GPU 機型，需要有對應的配額")
    p.add_argument("--model", default="yolo11n-seg.pt", help="基底模型，請對照 Colab 上用的")
    p.add_argument("--epochs", type=int, default=100)
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--batch", type=int, default=16)
    p.add_argument("--experiment-name", default="tree-trunk-train")
    p.add_argument("--resume", metavar="RUN_NAME", help="不重新提交，只等待並下載既有任務（例如 careful_energy_xxx）")
    p.add_argument("--no-wait", action="store_true", help="提交後不等結果，直接結束")
    p.add_argument("--download-to", default="./results", help="訓練完成後把模型下載到這個資料夾")
    args = p.parse_args()

    if "<" in SUBSCRIPTION_ID + RESOURCE_GROUP + WORKSPACE_NAME:
        raise SystemExit("請先在 submit_job.py 上方填入 SUBSCRIPTION_ID / RESOURCE_GROUP / WORKSPACE_NAME")

    if not args.resume and not args.dataset_zip:
        raise SystemExit("提交新任務需要 --dataset-zip；若只是等待既有任務，請用 --resume 任務名稱")

    ml_client = get_client()
    if args.resume:
        job_name = args.resume
        print("沿用既有任務，Studio 連結：", ml_client.jobs.get(job_name).studio_url)
    else:
        job = ml_client.create_or_update(build_job(args))
        job_name = job.name
        print("已提交，Studio 連結：", job.studio_url)
        print("任務名稱（Run ID）：", job_name, "  ← 之後可用 --resume", job_name, "重新等待與下載")

    if args.no_wait:
        return
    status = wait_for_job(ml_client, job_name)
    if status == "Completed":
        download_result(ml_client, job_name, args.download_to)
    else:
        print(f"任務結束，狀態：{status}。請到 Studio 的任務頁面查看錯誤訊息。")

if __name__ == "__main__":
    main()
