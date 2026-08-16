# 負責人：蔡宗倫
# 開發日期：2026/08/16
# 用意：對齊並合併 Arduino 與 RTK 的 CSV 數據檔案，供動態上傳使用

import pandas as pd
import os

def merge_sensor_data(arduino_path, rtk_path, output_dir='data/processed'):
    # 執行對齊與合併邏輯，並包含錯誤處理以防後端崩潰
    try:
        # 檢查檔案是否真實存在
        if not os.path.exists(arduino_path):
            raise FileNotFoundError(f'找不到 Arduino 檔案，請確認路徑：{arduino_path}')
        if not os.path.exists(rtk_path):
            raise FileNotFoundError(f'找不到 RTK 檔案，請確認路徑：{rtk_path}')

        df_arduino = pd.read_csv(arduino_path)
        df_rtk = pd.read_csv(rtk_path)

        # 檢查必要欄位是否遺失
        if 'TIME' not in df_arduino.columns:
            raise KeyError('Arduino 檔案中找不到 TIME 欄位，請檢查檔案格式是否正確。')
        if 'TIME' not in df_rtk.columns or 'LATITUDE N/S' not in df_rtk.columns:
            raise KeyError('RTK 檔案中找不到 TIME 或經緯度欄位，請檢查檔案格式。')

        # 建立金鑰並合併 (Left Join)
        df_arduino['Time_Key'] = df_arduino['TIME'].astype(str).str.replace(':', '').astype(int)
        df_rtk['Time_Key'] = df_rtk['TIME'].astype(int)

        df_merged = pd.merge(df_arduino, 
                             df_rtk[['Time_Key', 'LATITUDE N/S', 'LONGITUDE E/W']], 
                             on='Time_Key', 
                             how='left')

        df_merged = df_merged.drop(columns=['Time_Key'])
        df_merged = df_merged.rename(columns={
            'LATITUDE N/S': 'LATITUDE', 
            'LONGITUDE E/W': 'LONGITUDE'
        })

        # 智慧命名與輸出
        arduino_name = os.path.splitext(os.path.basename(arduino_path))[0]
        rtk_name = os.path.splitext(os.path.basename(rtk_path))[0]
        
        parent_folder = os.path.basename(os.path.dirname(rtk_path))
        if parent_folder.startswith('20'):
            year_month = parent_folder.replace('_', '')
        else:
            year_month = '202608' 

        day = rtk_name[:2]
        time_str = rtk_name[2:]
        final_name = f'{arduino_name}_{year_month}{day}_{time_str}.csv'
        
        # 確保輸出資料夾存在，若無則自動建立
        os.makedirs(output_dir, exist_ok=True)
        output_filepath = os.path.join(output_dir, final_name)
        
        df_merged.to_csv(output_filepath, index=False, encoding='utf-8-sig')
        
        # 回傳成功狀態與檔案路徑給網頁後端
        return {'status': 'success', 'message': '檔案合併成功', 'file_path': output_filepath}

    except FileNotFoundError as e:
        return {'status': 'error', 'message': str(e)}
    except KeyError as e:
        return {'status': 'error', 'message': str(e)}
    except Exception as e:
        # 捕捉其他未知的系統錯誤
        return {'status': 'error', 'message': f'發生未知的系統錯誤：{str(e)}'}


# 本地端測試執行區塊 (供單機驗證使用)
if __name__ == '__main__':
    test_arduino = 'data/raw/TREE_019.CSV'
    test_rtk = 'data/raw/30174930.CSV'
    
    result = merge_sensor_data(test_arduino, test_rtk)
    if result['status'] == 'success':
        print(f"成功：{result['message']}！儲存於：{result['file_path']}")
    else:
        print(f"失敗：{result['message']}")