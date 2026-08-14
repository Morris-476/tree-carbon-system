#include <SPI.h>
#include <SD.h>
#include <Wire.h>
#include "RTClib.h"

// ==========================================
// 1. 硬體腳位與物件設定
// ==========================================
const int laserPin = 8;      
const int ledPin = 9;        
const int chipSelect = 53;   

RTC_DS3231 rtc; 

unsigned long lastLogTime = 0;
const int logInterval = 1000; // 1秒紀錄一次

// --- TF-Luna 1 (第一顆) 變數 ---
int distance1 = 0;
int strength1 = 0; // 保留強度變數供 LED 判斷使用，但不寫入 SD 卡
unsigned char tfData1[9];     

// --- TF-Luna 2 (第二顆) 變數 ---
int distance2 = 0;
int strength2 = 0; // 保留強度變數供 LED 判斷使用，但不寫入 SD 卡
unsigned char tfData2[9];     

char filename[] = "TREE_000.CSV";
String currentTreeID = "000"; 

void setup() {
  Serial.begin(9600);    
  Serial1.begin(115200); // 啟動第一顆 ToF (Pin 19, 18)
  Serial2.begin(115200); // 啟動第二顆 ToF (Pin 17, 16)

  pinMode(laserPin, OUTPUT);
  pinMode(ledPin, OUTPUT);

  // 開機自檢
  digitalWrite(laserPin, HIGH);
  digitalWrite(ledPin, HIGH);
  delay(1000);
  digitalWrite(laserPin, LOW);
  digitalWrite(ledPin, LOW);

  // ==========================================
  // 初始化 RTC 時鐘模組 (修正雙底線語法)
  // ==========================================
  if (!rtc.begin()) {
    Serial.println("Couldn't find RTC module!");
    Serial.flush();
  }
  
  if (rtc.lostPower()) {
    Serial.println("RTC lost power, lets set the time!");
    // 這裡的 _DATE_ 和 _TIME_ 前後必須是連續兩個底線
    rtc.adjust(DateTime(F(__DATE__), F(__TIME__)));
  }

  // ==========================================
  // 初始化 SD 卡與建立新檔案
  // ==========================================
  Serial.print("Initializing SD card...");
  if (!SD.begin(chipSelect)) {
    Serial.println("Card failed.");
  } else {
    Serial.println("Card initialized.");
    
    // 自動尋找最新的流水號檔案
    for (int i = 1; i <= 999; i++) {
      filename[5] = i / 100 + '0';
      filename[6] = (i / 10) % 10 + '0';
      filename[7] = i % 10 + '0';
      
      if (!SD.exists(filename)) {
        currentTreeID = String(i / 100) + String((i / 10) % 10) + String(i % 10);
        
        File dataFile = SD.open(filename, FILE_WRITE);
        if (dataFile) {
          // 寫入精簡版表頭
          dataFile.println("Tree_ID,DATE,TIME,Laser_Status,LED_Status,ToF_Dist1_cm,ToF_Dist2_cm");
          dataFile.close();
          Serial.print("Created new file: ");
          Serial.println(filename);
        }
        break; 
      }
    }
  }
}

void loop() {
  // ==========================================
  // 讀取第一顆 ToF (Serial1)
  // ==========================================
  if (Serial1.available() >= 9) {
    if (Serial1.read() == 0x59) {     
      if (Serial1.read() == 0x59) {   
        for (int i = 0; i < 7; i++) {
          tfData1[i] = Serial1.read();
        }
        distance1 = tfData1[0] + (tfData1[1] << 8);
        strength1 = tfData1[2] + (tfData1[3] << 8);
      }
    }
  }

  // ==========================================
  // 讀取第二顆 ToF (Serial2)
  // ==========================================
  if (Serial2.available() >= 9) {
    if (Serial2.read() == 0x59) {     
      if (Serial2.read() == 0x59) {   
        for (int i = 0; i < 7; i++) {
          tfData2[i] = Serial2.read();
        }
        distance2 = tfData2[0] + (tfData2[1] << 8);
        strength2 = tfData2[2] + (tfData2[3] << 8);
      }
    }
  }

  // ==========================================
  // 1秒紀錄與硬體狀態反饋
  // ==========================================
  unsigned long currentMillis = millis();
  
  if (currentMillis - lastLogTime >= logInterval) {
    lastLogTime = currentMillis;
    
    String laserStatus = "ON";
    String ledStatus = "OFF";   

    // 總體驗證：必須兩顆感測器強度都大於 100，LED 才會常亮
    if (strength1 > 100 && strength1 < 32000 && strength2 > 100 && strength2 < 32000) { 
      digitalWrite(laserPin, HIGH);
      digitalWrite(ledPin, HIGH); 
      ledStatus = "SUCCESS";
    } else {
      digitalWrite(laserPin, HIGH);
      ledStatus = "WARNING";
      // 其中一顆異常即快速閃爍警告
      for(int i=0; i<5; i++) {
        digitalWrite(ledPin, HIGH); delay(40);
        digitalWrite(ledPin, LOW);  delay(40);
      }
    }

    // 抓取並格式化時間
    DateTime now = rtc.now();
    char dateBuffer[12];
    char timeBuffer[10];
    sprintf(dateBuffer, "%04d/%02d/%02d", now.year(), now.month(), now.day());
    sprintf(timeBuffer, "%02d:%02d:%02d", now.hour(), now.minute(), now.second());

    // 寫入 SD 卡
    File dataFile = SD.open(filename, FILE_WRITE);
    if (dataFile) {
      dataFile.print(currentTreeID); dataFile.print(","); 
      dataFile.print(dateBuffer);    dataFile.print(","); // DATE
      dataFile.print(timeBuffer);    dataFile.print(","); // TIME
      dataFile.print(laserStatus);   dataFile.print(",");
      dataFile.print(ledStatus);     dataFile.print(","); 
      dataFile.print(distance1);     dataFile.print(","); // ToF_Dist1_cm
      dataFile.println(distance2);   // ToF_Dist2_cm (最後一欄使用 println 自動換行)
      dataFile.close();              
    }
    
    // Serial Monitor 檢視 (印出重點資訊)
    Serial.print("Tree:"); Serial.print(currentTreeID); Serial.print(" | ");
    Serial.print(timeBuffer); 
    Serial.print(" | LED:"); Serial.print(ledStatus); 
    Serial.print(" | D1:"); Serial.print(distance1); 
    Serial.print(" | D2:"); Serial.print(distance2); 
    Serial.println();
  }
}
