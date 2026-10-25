"""
scripts/fix_missing_species_carbon.py
用途：修正 Species_Ref 樹種固碳參數（allo_param_a / allo_param_b /
carbon_fraction）不完整，導致 Measurements.biomass / carbon_absorpation
算不出來、卻又被 admin_update_measurement() 標成 Approved 的問題。

同時處理兩種不同性質的情況，兩者絕對不能混為一談：

1.「species_name = '未知'」——舊版下拉選單留下的殘留資料，本身沒有任何
   辨識意義。這批的 Trees 會被改成指向 FALLBACK_SPECIES_NAME（通用平均值
   fallback，用於「辨識失敗」的情況），再用 fallback 的參數重算固碳量。
   FALLBACK_SPECIES_NAME 必須已存在於 Species_Ref，本腳本不會自動建立，
   避免字串拼錯又生出一筆空白樹種。

2. 其他「參數不完整但樹種名稱不是未知」的情況（例如已辨識為某個真實
   樹種、只是還沒補上異速生長參數）——這些樹**已經有辨識結果**，不是
   「辨識失敗」，所以不會被改成 fallback、也不會套用通用平均值，只會
   在報告裡列出來提醒需要人工補上真正的 allo_param_a / allo_param_b。

預設是 dry-run，只印出會影響哪些 Tree_ID / Measurements，不會寫入資料庫；
要真的更新並 commit 請加 --apply。
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from services.core.db import get_db_connection
from services.core.carbon import calculate_carbon

# 辨識失敗時的通用平均值 fallback，字串需與 static/js/admin.js 的
# speciesOptions 完全一致，才會被 _get_or_create_species() 對到同一筆
FALLBACK_SPECIES_NAME = '未辨識樹種'
# 舊版下拉選單殘留、本身沒有辨識意義的資料
LEFTOVER_SPECIES_NAME = '未知'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true',
                         help='實際寫入資料庫並 commit；不加則只 dry-run 印出計畫，不動資料庫')
    args = parser.parse_args()

    conn = get_db_connection()
    if conn is None:
        print('資料庫連線失敗')
        sys.exit(1)

    try:
        cursor = conn.cursor()

        # 1) fallback 樹種必須已存在且參數完整，否則直接中止，不亂猜
        cursor.execute(
            'SELECT species_id, allo_param_a, allo_param_b, carbon_fraction '
            'FROM Species_Ref WHERE species_name = ?', FALLBACK_SPECIES_NAME
        )
        fallback_row = cursor.fetchone()
        if fallback_row is None:
            print(f'找不到 fallback 樹種「{FALLBACK_SPECIES_NAME}」，請先確認 Species_Ref 是否有這筆資料')
            sys.exit(1)
        fallback_id, fb_a, fb_b, fb_cf = fallback_row
        if fb_a is None or fb_b is None or fb_cf is None:
            print(f'fallback 樹種「{FALLBACK_SPECIES_NAME}」(id={fallback_id}) 本身參數不完整，無法用來重算固碳量')
            sys.exit(1)

        # 2) 找「未知」殘留樹種，以及目前指向它的 Trees
        cursor.execute(
            'SELECT species_id FROM Species_Ref WHERE species_name = ?', LEFTOVER_SPECIES_NAME
        )
        leftover_ids = [r[0] for r in cursor.fetchall()]

        reassign_tree_ids = []
        if leftover_ids:
            cursor.execute(
                f"SELECT Tree_ID FROM Trees WHERE species_id IN ({','.join('?' * len(leftover_ids))})",
                leftover_ids
            )
            reassign_tree_ids = [r[0] for r in cursor.fetchall()]

        print(f'[情況1：辨識失敗殘留「{LEFTOVER_SPECIES_NAME}」] species_id={leftover_ids}')
        print(f'  將改指向 fallback「{FALLBACK_SPECIES_NAME}」(id={fallback_id})，影響 Tree_ID: {reassign_tree_ids}')

        if args.apply and reassign_tree_ids:
            cursor.execute(
                f"UPDATE Trees SET species_id = ? WHERE Tree_ID IN ({','.join('?' * len(reassign_tree_ids))})",
                [fallback_id] + reassign_tree_ids
            )

        # 3) 掃過所有樹，重算「剛改成 fallback 的」與「參數本來就不完整的」
        cursor.execute('''
            SELECT t.Tree_ID, t.species_id, s.species_name,
                   s.allo_param_a, s.allo_param_b, s.carbon_fraction
            FROM Trees t
            JOIN Species_Ref s ON s.species_id = t.species_id
        ''')
        all_trees = cursor.fetchall()

        updated_measurements = 0
        reassigned_log = []      # 情況1：辨識失敗 -> 套用通用平均值
        unidentified_log = []    # 情況2：已辨識但缺真實參數，不動、不套 fallback

        for tree_id, species_id, species_name, a, b, cf in all_trees:
            was_reassigned = tree_id in reassign_tree_ids
            params_incomplete = a is None or b is None or cf is None

            if not was_reassigned and not params_incomplete:
                continue  # 參數完整、也不是剛改的，不用重算

            if not was_reassigned and params_incomplete:
                # 情況2：已辨識為真實樹種，只是缺校正參數 —— 絕對不套用
                # 通用平均值，只記錄提醒，等人工補上真正的 allo_param
                unidentified_log.append((tree_id, species_name))
                continue

            # 情況1：剛改成 fallback 的樹，用 fallback 參數重算
            use_a, use_b, use_cf = fb_a, fb_b, fb_cf

            cursor.execute('SELECT record_id, dbh FROM Measurements WHERE Tree_ID = ?', tree_id)
            for record_id, dbh in cursor.fetchall():
                if dbh is None or dbh <= 0:
                    continue
                result = calculate_carbon(
                    dbh=float(dbh),
                    allo_param_a=float(use_a),
                    allo_param_b=float(use_b),
                    carbon_fraction=float(use_cf),
                )
                if result.error is not None:
                    print(f'  [略過] Tree_ID={tree_id} record_id={record_id}: {result.error}')
                    continue
                reassigned_log.append((tree_id, record_id, result.biomass_kg, result.carbon_kg))
                print(f'  Tree_ID={tree_id} record_id={record_id}: biomass={result.biomass_kg:.4f}kg carbon={result.carbon_kg:.4f}kg')
                if args.apply:
                    cursor.execute(
                        'UPDATE Measurements SET biomass = ?, carbon_absorpation = ? WHERE record_id = ?',
                        result.biomass_kg, result.carbon_kg, record_id
                    )
                    updated_measurements += 1

        if unidentified_log:
            print(f'\n[情況2：已辨識為真實樹種但缺 allo_param，非「未知」/「{FALLBACK_SPECIES_NAME}」，'
                  f'不會套用通用平均值，需要之後補上真實的異速生長參數才能處理]')
            for tree_id, species_name in unidentified_log:
                print(f'  Tree_ID={tree_id} 樹種={species_name}：缺 allo_param_a/allo_param_b，維持原樹種不動，暫不重算固碳量')

        if args.apply:
            conn.commit()
            print(f'\n已 commit：{len(reassign_tree_ids)} 棵樹改指向「{FALLBACK_SPECIES_NAME}」，'
                  f'{updated_measurements} 筆 Measurements 更新固碳量')
        else:
            conn.rollback()
            print('\n[dry-run] 尚未寫入資料庫，加 --apply 才會真正更新並 commit')
    except Exception as e:
        conn.rollback()
        print(f'執行失敗: {e}')
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    main()
