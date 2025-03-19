# 賽博朋克詞典

一個具有賽博朋克風格的英漢/漢英詞典應用。

## 功能特點

- 英漢/漢英雙向翻譯
- 單字發音（英文）
- 例句展示
- 用戶註冊和登錄
- 單字收藏功能
- 學習進度追蹤
- 賽博朋克風格界面

## 技術棧

- 後端：Python Flask
- 前端：HTML, CSS, JavaScript
- 數據庫：SQLite
- 翻譯：translate
- 語音：gTTS

## 安裝和運行

1. 克隆倉庫：
```bash
git clone https://github.com/your-username/cyberpunk-dict.git
cd cyberpunk-dict
```

2. 安裝依賴：
```bash
pip install -r requirements.txt
```

3. 初始化數據庫：
```bash
flask init-db
```

4. 運行應用：
```bash
python app.py
```

5. 訪問應用：
打開瀏覽器，訪問 http://127.0.0.1:5000

## 使用說明

1. 註冊/登錄：首次使用需要註冊賬號
2. 查詢單字：在首頁輸入要查詢的英文或中文單字
3. 收藏單字：點擊「加入收藏夾」按鈕將單字添加到收藏夾
4. 查看收藏：點擊「查看收藏夾」按鈕查看已收藏的單字
5. 移除收藏：在收藏夾中點擊單字旁的「移除」按鈕

## 許可證

MIT License 