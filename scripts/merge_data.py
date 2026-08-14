import pandas as pd
import os

arduino_file = "data/raw/TREE_019.CSV"                
rtk_file = "data/raw/30174930.csv"            

df_arduino = pd.read_csv(arduino_file)
df_rtk = pd.read_csv(rtk_file)

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

arduino_name = os.path.splitext(os.path.basename(arduino_file))[0]
rtk_name = os.path.splitext(os.path.basename(rtk_file))[0]

parent_folder = os.path.basename(os.path.dirname(rtk_file))

if parent_folder.startswith("20"):
    year_month = parent_folder.replace("_", "")
else:

    year_month = "202608" 

day = rtk_name[:2]
time_str = rtk_name[2:]

final_name = f"{arduino_name}_{year_month}{day}_{time_str}.csv"

output_filename = f"data/processed/{final_name}"
df_merged.to_csv(output_filename, index=False, encoding='utf-8-sig')

print(f"✅ 合併成功！檔案已自動命名並儲存為：{output_filename}")