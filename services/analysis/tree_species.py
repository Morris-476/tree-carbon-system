# 負責人：Morris
# 開發日期：2026/09/12
# 用途：樹種辨識批次腳本，跟 tree_coordinate.py 同一種模式——離線執行，不是
#      /api/upload 即時流程的一部分。讀取還沒判定樹種、但有截圖可用的樹，
#      跑 YOLO 去背 + CLIP 比對（services/species_classifier.py），把結果
#      寫回 Trees.species_id。信心度不足時跳過，species_id 維持 NULL，
#      後台畫面會照既有邏輯自動顯示「未知」，不需要另外處理。
#
# 建議執行順序：先跑 tree_analysis.py、tree_coordinate.py 把 Tree_ID 對好，
# 再跑這支——這支只處理「已經有正確 Tree_ID」的樹，Tree_ID 還沒接上的
# 這裡不會處理到。
import os

if __name__ == '__main__':
    # config.py 在 import 當下就會用 os.environ.get() 讀取 DB_SERVER 等連線設定，
    # 所以 load_dotenv() 一定要在 import services.db（進而 import config）之前執行，
    # 不然會讀到空字串，拼出無效的連線字串。
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

import cv2
import numpy as np
from ultralytics import YOLO

import config
from services import db as db_service
from services import species_classifier


def classify_pending_trees() -> dict:
    """對所有還沒判定樹種、且有截圖的樹跑辨識。
    回傳 {'classified': int, 'uncertain': int, 'failed': int}。"""
    yolo_model = YOLO(config.MODEL_PATH)
    trees = db_service.get_trees_needing_species()

    classified, uncertain, failed = 0, 0, 0

    for row in trees:
        tree_id = row['Tree_ID']
        image_array = np.frombuffer(row['image_data'], dtype=np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

        if image is None:
            print(f'⚠ Tree_ID={tree_id} 截圖解碼失敗，略過')
            failed += 1
            continue

        result = species_classifier.identify_species(image, yolo_model)

        if result.species is None:
            print(f'- Tree_ID={tree_id}：{result.error}')
            uncertain += 1
            continue

        species_id = db_service.get_or_create_species_id(result.species)
        db_service.update_tree_species(tree_id, species_id)
        print(f'✓ Tree_ID={tree_id} → {result.species}（信心度 {result.confidence:.2f}）')
        classified += 1

    print(f'\n共判定 {classified} 棵，信心度不足 {uncertain} 棵，截圖解碼失敗 {failed} 棵')
    return {'classified': classified, 'uncertain': uncertain, 'failed': failed}


if __name__ == '__main__':
    classify_pending_trees()
