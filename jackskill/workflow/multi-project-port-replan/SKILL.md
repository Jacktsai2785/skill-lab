---
name: multi-project-port-replan
description: |
  對機器上所有本地專案進行一次性 port 盤點、衝突診斷、重新規劃，輸出並同步 SSOT（~/PORTS.md）至各專案配置。
  
  觸發 when: 使用者說「梳理目前專案的 port 佔用」「重新規劃 port」「port 全盤檢查」「PORTS.md 更新」「所有 dev server 一次重啟」
  
  when_to_use: 機器上累積多個專案、port 佔用情況不清、發現衝突、需要規範化分配、或執行全面基礎設施重啟前夕
version: 1.0.0
trigger_when:
  - 梳理目前專案的 port 佔用
  - 重新規劃 port
  - port 全盤檢查
  - PORTS.md 更新
  - 所有 dev server 一次重啟
tags:
  - infrastructure
  - port-management
  - multi-project
  - devops
languages: all
---

## Overview

`multi-project-port-replan` 是一個跨專案的 port 盤點與重規劃工作流。它執行以下工作：

1. **掃描清單** — 發現機器上所有本地專案（包括 ~/mops_dbs 下的資料庫服務、~/rivendell 的 skills、其他開發專案），並在每個專案中找出用到的 port（.env、Makefile、docker-compose.yml、vite.config、next.config 等）
2. **衝突診斷** — 識別 port 重複分配、超出範圍分配、或浪費的情況
3. **重新規劃** — 根據全域 CLAUDE.md 中的分段制（5432 PG / 8080–8089 mops / 8000–8009 app backend / 8500–8509 dashboard / 3000–3009 Next.js / 5170–5179 Vite）重新分配 port
4. **輸出 SSOT** — 生成或更新 ~/PORTS.md，作為單一真實來源（SSOT）
5. **同步更新** — 在各專案的配置檔（.env、Makefile、docker-compose.yml、vite.config）中更新 port，並保留舊值作為註解
6. **驗證與重啟** — 驗證沒有新衝突，並提示重啟相關服務

這個 skill 和 `dev-port-conflict-fix` 互補：`dev-port-conflict-fix` 用於修復單一衝突，而 `multi-project-port-replan` 則是全面的一次性盤點與規劃。

## 何時使用

### 觸發場景
- 機器上新增了若干個開發專案，需要為它們統一分配 port，確保沒有衝突
- 發現多個專案搶用同一個 port，引發衝突或無法同時啟動
- 定期審視：想確認當前 port 佔用情況是否合理、浪費或違反全域分段制
- 準備全面重啟所有 dev 服務，需要先梳理清楚依賴關係和 port 配置
- PORTS.md 過時或不存在，需要建立從零開始

### 預期輸出
執行完成後，你將擁有：
- 更新或新建的 `~/PORTS.md`，以表格形式列出所有 port 區間、用途、所屬專案、目前狀態
- 各專案的 .env、Makefile、docker-compose.yml、vite.config 等已同步更新，使用新分配的 port
- 清晰的衝突診斷報告，列出原始配置中的問題和修復方式
- 驗證清單，確認新配置無衝突且服務能正常啟動

## 執行步驟與模式

### Step 1：Inventory & Audit（盤點和審計）

掃描本機所有已知專案：

```bash
# 掃描 ~/mops_dbs 下的所有服務和 port
find ~/mops_dbs -type f \( -name ".env*" -o -name "Makefile" -o -name "docker-compose.yml" -o -name "*.config.*" \) | head -20

# 掃描 ~/rivendell 及其 subfolders
find ~/rivendell -type f \( -name ".env*" -o -name "Makefile" -o -name "docker-compose.yml" -o -name "*.config.*" \) | head -20

# 掃描其他主要開發目錄（根據使用者習慣調整）
find ~ -maxdepth 2 -type d -name "*project" -o -name "*app" -o -name "*service" | head -10

# 對每個檔案，grep 出 port 相關配置
grep -rn "port.*=" ~/mops_dbs --include=".env*" --include="Makefile" --include="docker-compose.yml" 2>/dev/null | grep -E ":[0-9]{4,5}"

grep -rn "port.*=" ~/rivendell --include=".env*" --include="Makefile" --include="docker-compose.yml" 2>/dev/null | grep -E ":[0-9]{4,5}"
```

建立一份臨時清單檔（例如 `/tmp/port-inventory.txt`），記錄：
```
project_name | service_name | current_port | config_file | port_range
mops_dbs     | postgres     | 5432         | .env        | 5432 (PG)
mops_dbs     | orchestrator | 8080         | .env        | 8080–8089 (mops)
rivendell    | dashboard-api| 8001         | .env        | 8000–8009 (app backend)
rivendell    | dashboard-web| 3000         | package.json| 3000–3009 (Next.js)
```

### Step 2：Conflict Detection（衝突診斷）

逐行檢查清單中的 port 和 range：

```bash
# 列出所有使用的 port（去重並排序）
grep -E "[0-9]{4,5}" /tmp/port-inventory.txt | awk '{print $NF}' | sort -u | sort -n

# 檢查是否有重複
awk '{print $NF}' /tmp/port-inventory.txt | sort | uniq -d

# 驗證是否超出分段範圍
# 預期分段：5432 PG, 8080–8089 mops, 8000–8009 app, 8500–8509 dashboard, 3000–3009 Next.js, 5170–5179 Vite
```

記錄衝突項：
```
Conflict: mops_jobs (8080) vs mops_orchestrator (8080)  → 重複使用
Conflict: rivendell_api (8001) 超出 dashboard range (8500–8509)  → 配置錯誤
Warning: legacy_app_1 (9000) 不在任何定義的 range 內  → 野生 port
```

### Step 3：Re-planning & Assignment（重新規劃和分配）

根據全域 CLAUDE.md 的分段制，為每個專案重新分配 port：

| Port Range | 用途 | 已分配專案 | 下一個可用 |
|-----------|------|---------|--------|
| 5432 | PostgreSQL | mops_dbs/postgres | — |
| 8080–8089 | MOPS cluster services | mops_dbs/{orchestrator, worker_1, worker_2} | 8083 |
| 8000–8009 | App backend | rivendell/api (8001), company_db/api (8002) | 8003 |
| 8500–8509 | Dashboard | rivendell/dashboard_api (8501), analytics_dashboard (8502) | 8503 |
| 3000–3009 | Next.js frontend | rivendell/web (3000), another_nextjs_app (3001) | 3002 |
| 5170–5179 | Vite dev server | rivendell/vite_app (5170) | 5171 |

重新分配時的原則：
- 同類服務優先使用各自的 range
- 保留常用 port（如 3000、5432、8000）不動（除非衝突）
- 為新增或未規劃的服務分配最小的可用 port
- 記錄舊值，便於追蹤和回滾

### Step 4：Generate SSOT（生成單一真實來源）

建立或更新 `~/PORTS.md`，格式如下：

```markdown
# Port Assignment — SSOT (Single Source of Truth)

Last updated: 2026-06-13
Machine: $(hostname)
Base path: ~/PORTS.md

## Port Ranges & Allocation

| Range | Purpose | Projects | Status |
|-------|---------|----------|--------|
| 5432 | PostgreSQL | mops_dbs (postgres) | ✅ Active |
| 8080–8089 | MOPS cluster services | mops_dbs (orchestrator, worker_1, worker_2) | ✅ Active |
| 8000–8009 | App backend services | rivendell (api:8001), company_db (api:8002) | ✅ Active |
| 8500–8509 | Dashboard services | rivendell (dashboard_api:8501), analytics (8502) | ✅ Active |
| 3000–3009 | Next.js frontends | rivendell (web:3000), another_app (3001) | ✅ Active |
| 5170–5179 | Vite dev servers | rivendell (vite_app:5170) | ⚠️ Partial |

## Project-level Details

### mops_dbs
- postgres: 5432
- orchestrator: 8080
- worker_1: 8081
- worker_2: 8082

### rivendell
- api (dashboard-next/api): 8001
- web (dashboard-next): 3000
- dashboard_api: 8501
- vite_app: 5170

### company_db
- api: 8002

## Conflict Resolution Log

| Date | Issue | Resolution | Status |
|------|-------|------------|--------|
| 2026-06-13 | mops_jobs & mops_orchestrator both on 8080 | Reassigned mops_jobs to 8081 | ✅ Fixed |
| 2026-06-13 | rivendell_api on 8001 (outside 8500–8509) | Kept 8001 as exception (documented) | ✅ Accepted |
```

### Step 5：Sync All Projects（同步所有專案配置）

對每個專案，逐個更新配置檔：

#### 更新 .env 檔

```bash
# 例：mops_dbs/.env
sed -i.bak 's/^ORCHESTRATOR_PORT=8080/# OLD: ORCHESTRATOR_PORT=8080\nORCHESTRATOR_PORT=8081/' ~/mops_dbs/.env

# 例：rivendell/.env 或 dashboard-next/.env
sed -i.bak 's/^API_PORT=8000/# OLD: API_PORT=8000\nAPI_PORT=8001/' ~/rivendell/.env
```

#### 更新 Makefile

```bash
# 例：mops_dbs/Makefile
sed -i.bak 's/PORT := 8080/# OLD: PORT := 8080\nPORT := 8081/' ~/mops_dbs/Makefile
```

#### 更新 docker-compose.yml

```bash
# 例：mops_dbs/docker-compose.yml
# 在 ports: 段落中更新映射，保留舊值作為註解
sed -i.bak 's/- "8080:8080"/# OLD: - "8080:8080"\n    - "8081:8080"/' ~/mops_dbs/docker-compose.yml
```

#### 更新 vite.config.ts / next.config.ts

```bash
# 例：rivendell/vite.config.ts
# 在 server: { port: 5170 } 的位置更新，保留舊值
```

使用 script 或手動編輯，確保每次更改都有備份（.bak）。

### Step 6：Verification（驗證）

驗證新配置無衝突：

```bash
# 列出所有已配置的 port
grep -rn "port.*=" ~/mops_dbs ~/rivendell ~/company_db 2>/dev/null | grep -oE "[0-9]{4,5}" | sort -n | uniq -c | grep -v "^[[:space:]]*1"

# 輸出應為空或僅包含預期的重複（如 9090:9090 的 docker 映射）
```

驗證 PORTS.md 的一致性：

```bash
# 手動檢查 PORTS.md 中記錄的 port 是否與實際配置檔相符
cat ~/PORTS.md | grep -E ":[0-9]{4,5}" | awk '{print $NF}' | sort -u

# 逐個專案確認
grep -rn "PORT\|port" ~/mops_dbs/.env | head -5
grep -rn "PORT\|port" ~/rivendell/.env | head -5
```

### Step 7：Restart Services（重啟服務）

按依賴順序重啟服務，確認新 port 配置生效：

```bash
# 停止所有相關服務
# mops_dbs
(cd ~/mops_dbs && docker-compose down) 2>/dev/null || true

# rivendell services
pkill -f "dashboard.*api" 2>/dev/null || true
pkill -f "npm run dev" 2>/dev/null || true
pkill -f "node.*server" 2>/dev/null || true

# 等待數秒
sleep 3

# 逐個啟動，驗證新 port 無衝突
(cd ~/mops_dbs && docker-compose up -d)
sleep 2 && curl -s http://localhost:5432 || echo "postgres on 5432: expected to fail (not http)"

(cd ~/rivendell && make dev) &  # 或其他啟動命令
sleep 3 && curl -s http://localhost:3000 | head -20

# 驗證日誌無 port 相關錯誤
docker-compose logs --tail=20 2>/dev/null | grep -i "port\|bind\|connection refused"
```

## 注意事項

### 已知限制與陷阱

1. **Hard-coded port** — 某些應用在原始碼中 hard-code 了 port（如 React 元件中的 `fetch('http://localhost:8000')`），不只在 .env 或配置檔中。執行前需搜索並標記這些位置。

2. **Docker 內外 port 映射** — docker-compose 中 `ports: "8080:8080"` 的第一個是主機 port，第二個是容器內 port。更新時務必只改主機 port（左邊）。

3. **互依服務** — 如果 service A 連接 service B（例如 web 連 api），需確保兩邊都更新。可在 PORTS.md 中額外記錄依賴關係。

4. **遠程機器和 CI/CD** — 如果 CI/CD pipeline 或遠程機器依賴這些 port（例如遠程測試 hit localhost:3000），需同步更新相關腳本或設定。

5. **備份與回滾** — 執行 sed 時自動生成 .bak 檔，若需回滾執行：
   ```bash
   for f in ~/mops_dbs/**/*.bak; do mv "$f" "${f%.bak}"; done
   ```

6. **文件所有權與權限** — 更新 .env 或 Makefile 前，確認當前使用者有寫入權限，特別是如果有 docker 或 sudo 執行的容器。

7. **PORTS.md 格式靈活** — 可根據專案需求調整表格，但必須保證「Port Range | Purpose | Projects | Status」四個主要欄位，以便後續查詢和審計。

8. **周期性更新** — 每當新增專案、改變 port、或發現衝突，立即更新 PORTS.md，避免 SSOT 過時。