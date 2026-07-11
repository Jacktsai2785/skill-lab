---

name: dev-port-conflict-fix
description: 當多個本地 web 服務 Port 衝突時，快速定位衝突根因、調整服務 Port、更新前端 API client 設定。TRIGGER when: 「Port already in use」「EADDRINUSE」「連不到後端」「Vite HMR failed」「改 port」。
version: 1.0.0
tags:
  - debugging
  - dev-setup
  - port-management
  - local-dev
  - automation
languages: all
when_to_use: |
  本地開發時多個 web 服務啟動，遇到 Port 衝突導致服務無法綁定、前端無法連線後端、或 Vite HMR 熱更新失敗。適用於 Node.js / Next.js / Vite / Python Flask 等混合技術棧的本地環境。

---

## 概述

當本地開發環境中多個服務搶占同一 Port 時，傳統的做法是手動搜尋 `ps aux` 、重啟服務、逐一改 config。這個 skill 自動化整個流程：

1. **定位衝突**：用 `lsof -i :PORT` 和 `ps aux` 秒速找到佔用的進程
2. **識別衝突方**：判斷是前端開發伺服器（Vite/Next.js）還是後端服務（Python/Node）
3. **調整 Port**：根據 ~/PORTS.md 的分配策略，修改衝突方的設定檔或環境變數
4. **更新 API client**：自動修正前端 `api/client.ts` 或 `.env.local` 的 `baseURL`
5. **驗證重連**：確認 Vite HMR、API 連線恢復正常

這特別重要因為：
- **Vite HMR 重連是常被遺漏的細節**：改完 port 後，瀏覽器需要重新建立 WebSocket；遺漏這步會導致檔案改變但頁面不更新
- **Port 分配有全局 SSOT**：~/PORTS.md 是唯一來源，改 port 時必須同步更新，否則下次起服務又衝突
- **dashboard API 真實案例**：曾因 8000↔8001 的 port 分配混亂，造成連報 3 週假 outage + retry storm 燒爆用量

---

## 何時使用

### 立即觸發信號
- 啟動 dev server 時看到：`error listen EADDRINUSE: address already in use :::8080`
- 前端頁面顯示連線失敗：`GET http://localhost:8000/api/... 503`、`fetch failed`
- Vite 終端提示：`ws://localhost:5173/ WebSocket connection failed`
- 一個服務起來，另一個服務卡著不動或無法連線後端
- 修改了 .env 或 config port，但瀏覽器還在連舊的 port

### 判斷步驟（3 秒決策樹）

```bash
# 1. 檢查是否真的 port 衝突
lsof -i :8080  # 有輸出 → 衝突確認

# 2. 判斷衝突方（是前端還是後端）
ps aux | grep node      # Node.js 進程清單
ps aux | grep python    # Python 進程清單
ps aux | grep vite      # Vite 進程清單
ps aux | grep next      # Next.js 進程清單

# 3. 檢查 ~/PORTS.md 中該服務的預期 port
cat ~/PORTS.md | grep -A 2 "8080 range"
```

---

## 執行步驟

### 第 1 步：定位衝突並識別進程

```bash
# 檢查目標 port（假設是 8080）
lsof -i :8080

# 典型輸出示例：
# COMMAND     PID     USER   FD   TYPE DEVICE SIZE/OFF NODE NAME
# node      12345   jackts   45   IPv4  0x1234      0t0  TCP localhost:8080 (LISTEN)

# 記下 PID（12345）和 COMMAND（node），進一步檢查
ps aux | grep 12345
# 或直接列所有 node 進程判斷
ps aux | grep -E "node|vite|next|python"
```

### 第 2 步：在 ~/PORTS.md 中查找 port 的預期歸屬

開啟 ~/PORTS.md，尋找目標 port 所在的分段：

```
5432              PostgreSQL
8080–8089         mops cluster services
8000–8009         app backend (Flask/Python)
8500–8509         dashboard (Next.js API)
3000–3009         Next.js frontend
5170–5179         Vite dev server
```

假設 8080 衝突，這個 port 預期用於 mops cluster。檢查是否有服務誤佔了不該用的 port。

### 第 3 步：根據服務類型調整 port

#### 場景 A：前端 Vite dev server 佔了後端 port（常見）

通常 Vite 預設 5173，但有時被配置為 8080。

修改 vite.config.ts 或 vite.config.js：

```typescript
// vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5170,  // 改為 ~/PORTS.md 中 Vite 預期的 port
    hmr: {
      host: 'localhost',
      port: 5170,
    },
  },
})
```

或修改 Next.js `.env.local`：

```
PORT=3000
API_PORT=8001
```

#### 場景 B：後端服務（Python Flask / Node.js）佔了 Vite 的 port

修改後端的 `.env` 或啟動參數：

Python Flask：

```bash
# 方式 1：.env 檔
PORT=8001
FLASK_ENV=development

# 方式 2：啟動指令
python api/server.py --port 8001

# 方式 3：在 start-api.sh 中改
PORT=8001 python api/server.py
```

Node.js / Express：

```bash
# .env
PORT=8001

# 或在啟動指令
PORT=8001 npm run dev
```

### 第 4 步：更新前端 API client 的 baseURL

這是**最容易遺漏**的一步。前端需要知道後端新的 port。

修改 `src/api/client.ts` 或類似的 API 配置檔：

```typescript
// src/api/client.ts
export const API_BASE_URL = 
  process.env.NEXT_PUBLIC_API_BASE_URL || 
  `http://localhost:${process.env.NEXT_PUBLIC_API_PORT || '8001'}`

export const apiClient = {
  fetch: async (endpoint: string, options: RequestInit = {}) => {
    const url = `${API_BASE_URL}${endpoint}`
    console.log(`[API] ${options.method || 'GET'} ${url}`)
    const response = await fetch(url, {
      credentials: 'include',
      ...options,
    })
    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`)
    }
    return response.json()
  },
}
```

或修改 `.env.local`：

```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8001
NEXT_PUBLIC_API_PORT=8001
```

### 第 5 步：重啟服務並驗證連線

```bash
# 1. 殺死舊進程
kill -9 12345  # 用 lsof 找到的 PID

# 或直接用 pkill
pkill -f "vite.*8080"
pkill -f "python.*api/server.py"

# 2. 重啟後端
cd dashboard-next
./start-api.sh  # 確認內部用了新的 port (8001)

# 3. 重啟前端（另一個終端）
npm run dev
```

### 第 6 步：驗證 Vite HMR 重連（最關鍵）

打開瀏覽器開發者工具的 Console，檢查：

```javascript
// 成功情況下會看到：
// [Vite] connected.
```

或檢查 Network 標籤：
- 開啟 WS (WebSocket) 篩選
- 應該看到 `ws://localhost:5170/` 或對應的 dev server port 連線已建立，狀態為 101 (Switching Protocols)

若 HMR 未重連：

```bash
# 清除 node_modules 的 cache
rm -rf node_modules/.vite

# 硬刷瀏覽器
# Ctrl+Shift+R (Windows/Linux)
# Cmd+Shift+R (macOS)
```

### 第 7 步：驗證 API 連線

在前端任意頁面的 Console 執行：

```javascript
// 測試後端連線
fetch('http://localhost:8001/health')
  .then(r => r.json())
  .then(data => console.log('Backend OK:', data))
  .catch(e => console.error('Backend error:', e))
```

或用 curl：

```bash
curl http://localhost:8001/health
```

預期成功（200 OK）。

### 第 8 步：更新 ~/PORTS.md 並提交

確保 PORTS.md 的記錄與實際部署一致。修改任何服務的 port 時，必須**同時更新 ~/PORTS.md**。

提交變更：

```bash
git add -A
git commit -m "fix: port 衝突修復 — dashboard API 改用 8001，Vite 保持 5173"
```

---

## 完整流程速記（5 分鐘內解決）

```bash
# 1. 找出衝突
lsof -i :8080

# 2. 看是誰佔的
ps aux | grep <PID>

# 3. 查 PORTS.md 預期分配
cat ~/PORTS.md

# 4. 根據服務類型改 config 或 .env
# （Vite → vite.config.ts，backend → .env）

# 5. 改前端 API baseURL
# （src/api/client.ts 或 .env.local）

# 6. 殺舊進程，重啟服務
pkill -f "old_process_pattern"
./start-api.sh &
npm run dev

# 7. 驗證 HMR（Console 看 [Vite] connected）
# 驗證 API（fetch('http://localhost:8001/health')）

# 8. 更新 PORTS.md，提交 commit
git add -A && git commit -m "fix: port 衝突 — ..."
```

---

## 注意事項與陷阱

### 🚨 Vite HMR 重連遺漏

**陷阱**：改完 port 後，瀏覽器還在用舊 port 連 HMR，檔案改變但頁面不更新。

**預防**：
1. 修改 `vite.config.ts` 的 `hmr.port` 與 `server.port` 保持一致
2. 重啟時執行硬刷（Ctrl+Shift+R）
3. 檢查 Console 有 `[Vite] connected` 信息
4. 若 HMR 持續失敗，清除 `node_modules/.vite` 並重啟開發伺服器

### 🚨 API baseURL 未同步

**陷阱**：改了後端 port（如 8000→8001），但前端還連舊 port，所有 API 呼叫都 404 或超時。

**預防**：
1. `src/api/client.ts` 中使用環境變數，不要硬寫 port
2. 修改後端 port 時，**同步修改** `.env.local` 或 `NEXT_PUBLIC_API_PORT`
3. 重啟前端後測試一個簡單 API 呼叫（如 `/health`）

### 🚨 PORTS.md 與實際不同步

**陷阱**：PORTS.md 說 dashboard 用 8001，但本地啟動時用了 8000，導致下次冷啟動時又衝突。

**預防**：
1. 修改任何服務的 port 時，必須**同時更新 ~/PORTS.md**
2. 每週核對一次 PORTS.md，確保與 `ps aux` 實際一致
3. 若本地長期偏離，改 config 使其符合 PORTS.md（而非反過來改 PORTS.md 遷就本地混亂）

### 🚨 舊進程未完全殺死

**陷阱**：`kill PID` 後 port 仍被佔用，因為進程未徹底終止。

**預防**：
1. 用 `kill -9 <PID>` 強制殺死（而非 `kill -15`）
2. 若 `kill -9` 後 port 仍被佔，等待 30–60 秒讓作業系統釋放 socket
3. 或檢查是否有 parent process：`ps -ef | grep <PID>`

### ℹ️ 多重衝突場景

**情況**：同時多個 port 衝突（Vite 和 backend 都衝突）。

**做法**：
1. 優先處理 **backend port**（優先級高）
2. 再改 **frontend dev server port**（優先級次之）
3. 確保二者不重疊，都符合 PORTS.md 分配

### ℹ️ 容器化環境差異

本 skill 假設**本地裸機開發**。若使用 Docker / Docker Compose：
- 容器內 port 和主機 port 是分開的，需在 docker-compose.yml 中設定 port mapping
- `lsof -i` 看到的是主機 port，容器內部的設定在 Dockerfile / .env 中
- 改 port 時需同時修改 docker-compose 的 `ports` 欄位

### ℹ️ 跨平台差異

- **macOS/Linux**：`lsof -i :PORT` 穩定可用
- **Windows (WSL2)**：`lsof` 可用，但 `netstat -ano | findstr :PORT` 也能用（若 lsof 不可用）
- 本 skill 優先使用 `lsof`，因其輸出格式一致

---

## 相關資源

- **Port 分配 SSOT**：~/PORTS.md
- **Dashboard 已知案例**：dashboard API port 從 8000 改為 8001，曾因混亂導致 3 週 outage
- **Vite 官方文件**：https://vitejs.dev/config/server-options.html#server-hmr
- **Next.js dev server port**：https://nextjs.org/docs/api-reference/cli#development

---

## 快速檢查清單

- [ ] 執行 `lsof -i :PORT` 確認衝突進程及 PID
- [ ] 在 ~/PORTS.md 中查詢該 port 的預期歸屬
- [ ] 修改衝突服務的 config（vite.config.ts / .env / start-*.sh）
- [ ] 修改前端 API client 的 `baseURL` / `NEXT_PUBLIC_API_PORT`
- [ ] 殺舊進程、重啟服務
- [ ] 驗證 Vite HMR（Console 看 `[Vite] connected`）
- [ ] 驗證 API 連線（`fetch('http://localhost:8001/health')`）
- [ ] 更新 ~/PORTS.md
- [ ] 提交 commit