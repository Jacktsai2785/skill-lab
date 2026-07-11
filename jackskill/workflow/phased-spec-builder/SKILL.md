---
name: phased-spec-builder
description: |
  TRIGGER when: 「我有 SPEC.md 定義了多個 phases，要逐階段建構完整 fullstack 應用」或「我要依序實作 Phase 0→N，邊建構邊驗證」
  PURPOSE: 讀取分階段 SPEC.md → TodoWrite 追蹤 phase 進度 → 逐層實作 React+Vite/Python+Node 前後端 → 最終輸出 DEPLOYMENT.md
  when_to_use: 需要按 SPEC 分階段建構全棧應用，有明確的 phase 分割與遞增式交付目標，每個 phase 結束前需驗證可運作
version: 1.0.0
tags:
  - fullstack
  - phased-development
  - spec-driven
  - vite
  - python
  - node
languages: all
---

## 概述

當你有一份結構化的 SPEC.md（定義 Phase 0, 1, 2... N），需要逐階段實作一個完整的全棧應用（React+Vite 前端 + Python/Node 後端）時，使用本 skill。

此 skill 強調的是**邊讀 SPEC 邊實作、遞增驗證**的工作流，而非執行已完成的計畫。每個 phase 必須能獨立驗證、逐層交付，最後產出可部署的應用與完整的 DEPLOYMENT.md。

## 何時使用

- 你有分階段定義的 SPEC.md（通常 Phase 0 = 初始化、Phase 1+ = 功能迭代）
- 需要前後端分別實作並在每個 phase 結束驗證可運作
- 最終交付物包含：運作中的應用、.env/.env.example 設定、DEPLOYMENT.md 部署文件
- 不用於零碎的 bug 修復或單點功能開發

## 執行步驟

### 1. 初始讀取與 Phase 規劃

先讀取 SPEC.md，確認：
- Phase 定義清晰（目標、前後端任務、驗證條件）
- 有明確的相依序列（Phase 0 → Phase 1 → ...）
- 識別前端框架（React+Vite）與後端技術棧（Python Flask/FastAPI 或 Node Express/Fastify）

### 2. 建立 TodoWrite Phase 追蹤表

在專案根目錄建立 `.claude/phased-build.md`，結構如下：

```
# Phase 進度追蹤

## Phase 0: 專案初始化
- [ ] 前端：建立 Vite React 專案結構
- [ ] 前端：配置 .env.example（前端環境變數）
- [ ] 後端：建立 API 伺服器框架 + health check endpoint
- [ ] 後端：配置 .env.example（後端環境變數）
- [ ] 驗證：本機啟動前後端，health check 通過

## Phase 1: [根據 SPEC 填入核心功能]
- [ ] 前端：[具體任務]
- [ ] 後端：[具體任務]
- [ ] 整合測試：[驗證方式]
- [ ] 驗證：[完成條件]
```

每個 phase 完成後**更新此表的 checkbox**，作為進度信號。

### 3. 逐 Phase 實作前端

**Phase 0 初始化：**
```bash
cd <project-root>
npm create vite@latest frontend -- --template react
cd frontend
npm install
```

建立 `frontend/.env.example`（列出所有環境變數，如 `VITE_API_URL=http://localhost:8000`）

**Phase N+ 功能實作：**
- 根據 SPEC 在 `frontend/src` 中建立元件、頁面、API 層
- 每個 phase 結束前，確保開發伺服器啟動無誤：`npm run dev`
- 在瀏覽器驗證該 phase 的 UI 功能

### 4. 逐 Phase 實作後端

**Phase 0 初始化（Python 範例）：**
```bash
cd <project-root>
python -m venv backend_venv
source backend_venv/bin/activate
pip install flask python-dotenv
```

建立 `backend/app.py`：
```python
from flask import Flask, jsonify
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'}), 200

@app.route('/api/v1/...', methods=['GET', 'POST'])
def api_endpoint():
    # Phase N 功能實作
    pass

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('API_PORT', 8000)), debug=True)
```

建立 `backend/.env.example`：
```
API_PORT=8000
DATABASE_URL=postgresql://...
DEBUG=True
```

**Phase N+ 功能實作：**
- 在 `backend/app.py` 或模組化結構（`backend/routes/`, `backend/models/` 等）增加 endpoint
- 每個 phase 結束前驗證 API：`curl http://localhost:8000/health`

### 5. 每 Phase 結束的驗證步驟

使用 Bash 驗證該 phase 的交付物（寫成可重複執行的指令集）：

```bash
#!/bin/bash
# verify-phase-0.sh
set -e

echo "=== 驗證 Phase 0 ==="

# 前端驗證
echo "檢查前端構建..."
cd frontend && npm run build && cd ..
[ -d "frontend/dist" ] && echo "✓ 前端構建成功" || exit 1

# 後端驗證
echo "啟動後端並檢查 health..."
cd backend
timeout 5s python app.py > /dev/null 2>&1 & 
BACKEND_PID=$!
sleep 2
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)
kill $BACKEND_PID 2>/dev/null || true
[ "$HTTP_CODE" = "200" ] && echo "✓ 後端 health check 通過" || exit 1

echo "✓ Phase 0 驗證完成"
```

每個 phase 建立一個 `verify-phase-N.sh`，phase 完成時執行並確保通過。

### 6. 環境變數與設定管理

- **前後端各有 `.env.example`**，記錄所有必要環境變數及其預設值
- 本機開發：複製 `.env.example` → `.env`，填入實際值
- `.env` 永遠 `.gitignore`（不提交敏感資訊）
- `.env.example` 須提交（作為文件化的設定模板）

### 7. 最終交付：DEPLOYMENT.md

Phase N 完成後，產出 `DEPLOYMENT.md`，結構如下：

```markdown
# DEPLOYMENT.md

## 系統需求
- Node.js 18+
- Python 3.9+
- PostgreSQL 14+（如有）

## 本機開發設定

### 前端
\`\`\`bash
cd frontend
cp .env.example .env
npm install
npm run dev  # 啟動 Vite 開發伺服器，通常 http://localhost:5173
\`\`\`

### 後端
\`\`\`bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py  # 或 uvicorn app:app --reload
\`\`\`

## 環境變數說明

### 前端 (frontend/.env)
- `VITE_API_URL`: 後端 API 基址，預設 `http://localhost:8000`

### 後端 (backend/.env)
- `API_PORT`: API 監聽埠，預設 8000
- `DATABASE_URL`: 資料庫連線，預設 `postgresql://localhost/myapp`
- `DEBUG`: 除錯模式，預設 `True`

## 驗證應用運作

1. 分別啟動前端和後端（見上述設定步驟）
2. 開啟瀏覽器訪問 `http://localhost:5173`
3. 執行關鍵工作流程（如登入、提交表單等）
4. 檢查開發者工具無誤（無 console 錯誤）

## 生產部署

### 前端
\`\`\`bash
cd frontend
npm run build  # 產生 dist/ 靜態檔案
# 部署 dist/ 到 CDN 或靜態伺服器
\`\`\`

### 後端
\`\`\`bash
cd backend
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 app:app
\`\`\`

## 常見問題排查

- CORS 錯誤：檢查後端 `VITE_API_URL` 與實際 API 址不符
- 環境變數缺失：確保 `.env` 覆蓋所有 `.env.example` 中的鍵
```

## 注意事項

- **Phase 定義的清晰度至關重要**：若 SPEC.md 的 phase 邊界模糊，會導致多次回溯修改。事前與使用者確認 phase 分割
- **環境隔離**：前端開發伺服器（通常 5173）與後端 API（通常 8000）應運行於不同埠，避免衝突。參考 `~/PORTS.md` 確認埠可用性
- **漸進驗證**：不要累積多個 phase 再驗證，每個 phase 結束立即執行 verify 指令碼，及早發現相依問題
- **.env 管理**：`.env.example` 是交付物，`.env` 是本機機密檔案。開發時務必 `.env` git-ignored
- **後端技術選擇**：若 SPEC 未明確指定，Python（Flask/FastAPI）適合快速原型，Node（Express/Fastify）適合前端整合開發