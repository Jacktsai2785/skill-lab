---
name: scraping-frontdoor-vs-backdoor
description: |
  決策樹式爬蟲戰略：何時用公開 API / JSON / 靜態檔案 / OData / RSS，何時降速度、加 user-agent、session cookie，如何用 audit_log.py + dry_run 安全測試。
  TRIGGER when: 要爬新網站但擔心被封 IP、現有爬蟲被限速、想降低偵測率、不確定該走前台還是後台
version: 1.0.0
tags:
  - scraping
  - api-strategy
  - rate-limiting
  - mops
  - backend
  - portal-scraping
languages: all
---

## Overview

大多數現有 skills（`mops-rev-scraper`、`mops-financial-scraper`）只講「怎麼爬 MOPS 這個特定站」，未曾抽象出通用啟發式。本 skill 整理爬蟲的決策框架：

**核心原則**：先走前台公開資源（JSON endpoint、靜態檔案、OData、RSS），只在無可奈何時才爬 HTML 後台；爬後台時必須模擬人類行為（降速、User-Agent、session 狀態）並在 dry_run 模式測試。

此框架適用於任何受保護的 portal（MOPS、政府公開資訊、工商管理系統等），不是 MOPS 專用，但 MOPS 是最佳示範案例。

## 何時使用

### 明確觸發場景

1. **接手陌生網站爬蟲** — 不知道該爬哪層、怕被封 IP
2. **現有爬蟲被限速** — HTTP 429、403、連線斷開
3. **要降低偵測風險** — 法規/倫理考量，或網站主動防禦
4. **爬蟲效能受限** — 一天要跑 10 萬次查詢但頻率限制 1 req/sec
5. **需要維護長期穩定性** — 不想被封 IP，要能 retry 而不被永久封禁

### 不需要此 skill 的情況

- 目標網站提供公開 API 且無頻率限制
- 所有資料都在公開 HTML 頁面上（無需登入、無 JavaScript）
- 已有明確的爬蟲許可

## 執行步驟與模式

### 第一步：決策樹 — 找最輕量級的資源層

按優先級從上到下檢查：

#### 1. 公開 API 或 JSON endpoint（最優先）

檢查步驟：
- 打開瀏覽器開發者工具，Network 標籤，執行一次查詢
- 看有無 `/api/` 或 `.json` 結尾的 XHR/Fetch 請求
- 檢查 Response 是否是結構化 JSON（表示前端直接調用 API）
- 複製 curl 命令重放，確認無需登入或 session

**MOPS 案例**：
```bash
# MOPS 月營收 API（無需登入，公開 JSON）
curl "https://mops.twse.com.tw/mops/web_api/v1/publicCompanyMonthlyRevenue?co_id=2303&month=202605"
# → 直接返回 JSON，無 rate limit

# 即使需要 session，先檢查：
curl -s "https://mops.twse.com.tw/..." \
  -H "User-Agent: Mozilla/5.0" \
  -H "Referer: https://mops.twse.com.tw" \
  -b "JSESSIONID=..." 
```

**優點**：最穩定、最快、最少爬蟲風險
**缺點**：需要 API 文件（通常沒有）或 reverse-engineering

#### 2. 靜態檔案下載（.csv、.xlsx、.json）

檢查步驟：
- 網站上有無「下載」或「匯出」按鈕
- 檢查 Network 標籤，看下載對象是直接檔案還是動態生成
- 嘗試直接 GET 該 URL，看有無 auth 障礙

**MOPS 案例**：
```bash
# 個股每月營收下載（CSV）— 無需爬，直接下載
curl -s "https://mops.twse.com.tw/mops/web_api/v1/publicCompanyMonthlyRevenue?co_id=2303&month=202605&output=csv" \
  -o revenue.csv

# 或財務報表「另存為」功能
# 大多數無需登入，部分需要 User-Agent 模擬
```

**優點**：格式標準、解析簡單、絕無 bot 偵測
**缺點**：只適合低頻率下載、且需要手動找到下載 URL

#### 3. OData 或 RSS Feed

檢查步驟：
- 搜尋網站是否提供 `/odata/` 或 `/feed.xml` 或 `/rss` 路徑
- 嘗試 `site:mops.twse.com.tw filetype:xml` 搜尋

**MOPS 案例**：
```bash
# 部分政府機構（含 MOPS 的財報揭露）提供 RSS
curl -s "https://mops.twse.com.tw/mops/web_api/v1/publicCompanyAnnouncements" 
# → 雖然主要是 JSON，但查詢入口支援多種格式
```

**優點**：標準協議、無需複雜認證、易於訂閱和增量更新
**缺點**：不常見、通常延遲更新（RSS 常有 1-2 小時 lag）

#### 4. iframe 內嵌資源

檢查步驟：
- 看頁面源代碼（Ctrl+U）有無 `<iframe src="...">` 
- iframe 指向的 URL 是否可直接訪問（不需雙層認證）

**MOPS 案例**：
```html
<!-- MOPS 某些報表頁面用 iframe 嵌入實際查詢結果 -->
<iframe src="https://mops.twse.com.tw/mops/core_trading/..."></iframe>
<!-- 嘗試直接爬 iframe 的 src，可能無需登入主頁面 -->
```

**優點**：繞過前台複雜 JS，直接命中資料層
**缺點**：仍需解析 HTML、無法確保長期穩定

#### 5. 爬 HTML 後台（最後手段）

如果上述 1-4 都不可行，才進行 HTML 爬蟲。此時進入第二步。

---

### 第二步：後台爬蟲時的隱藏與節流技巧

如果必須爬後台 HTML，遵循以下模式避免被封：

#### 基礎隱藏層（缺一不可）

```python
import requests
import time
from datetime import datetime
from pathlib import Path

class PortalScraper:
    def __init__(self, session_log_path="audit_log.jsonl"):
        self.session = requests.Session()
        # 合理的 User-Agent（非 bot）
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/120.0.0.0 Safari/537.36"
        })
        self.session_log_path = Path(session_log_path)
        self.delay_seconds = 2  # 預設 2 秒，可調整
        self.last_request_time = 0
        
    def log_request(self, method, url, status_code, error=None, dry_run=False):
        """記錄每個請求到 audit_log.jsonl（用於調試與合規審計）"""
        import json
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "method": method,
            "url": url,
            "status_code": status_code,
            "error": error,
            "dry_run": dry_run
        }
        with open(self.session_log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    
    def request_with_throttle(self, method, url, dry_run=False, **kwargs):
        """加入節流與錯誤處理"""
        # 強制執行最小延遲
        elapsed = time.time() - self.last_request_time
        if elapsed < self.delay_seconds:
            time.sleep(self.delay_seconds - elapsed)
        
        try:
            if method.upper() == "GET":
                resp = self.session.get(url, timeout=10, **kwargs)
            elif method.upper() == "POST":
                resp = self.session.post(url, timeout=10, **kwargs)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            self.last_request_time = time.time()
            self.log_request(method, url, resp.status_code, dry_run=dry_run)
            
            # 監控頻率限制信號
            if resp.status_code == 429:
                print(f"⚠️  Rate limited (429). Backing off...")
                time.sleep(30)  # 被限速時退避
            elif resp.status_code == 403:
                print(f"⚠️  Forbidden (403). Check User-Agent & session cookie.")
            
            return resp
        
        except Exception as e:
            self.log_request(method, url, None, error=str(e), dry_run=dry_run)
            raise

# MOPS 專用實裝
class MOPSScraper(PortalScraper):
    def __init__(self):
        super().__init__()
        self.base_url = "https://mops.twse.com.tw/mops/web/t05st01"
        # MOPS 需要 viewState 和 eventValidation（session 狀態），在 dry_run 測試時特別重要
        self.view_state = None
        self.event_validation = None
    
    def fetch_query_form(self):
        """首次訪問時取得 __VIEWSTATE 和 __EVENTVALIDATION"""
        resp = self.request_with_throttle("GET", self.base_url)
        # 用 BeautifulSoup 或 regex 解析
        # self.view_state = extract_viewstate(resp.text)
        # self.event_validation = extract_eventvalidation(resp.text)
        pass
    
    def query_monthly_revenue(self, co_id, month, dry_run=False):
        """
        查詢個股月營收（會用到後台表單）
        
        dry_run=True 時：只執行請求但不存檔，用於測試參數正確性
        """
        data = {
            "encodeURIComponent": co_id,
            "months": month,
            # MOPS 需要的 hidden form fields
            "__VIEWSTATE": self.view_state,
            "__EVENTVALIDATION": self.event_validation,
        }
        
        resp = self.request_with_throttle(
            "POST",
            self.base_url,
            data=data,
            dry_run=dry_run
        )
        
        if dry_run:
            print(f"[DRY RUN] POST to {self.base_url} with co_id={co_id}, month={month}")
            print(f"[DRY RUN] Response status: {resp.status_code}")
            return None  # dry_run 不返回實際資料
        
        # 實際爬蟲時再處理 response
        return resp
```

#### 具體的 MOPS 案例調整

```python
# MOPS 月營收頁面的典型流程
scraper = MOPSScraper()
scraper.delay_seconds = 2.5  # MOPS 不太嚴格，2-3 秒為安全值

# 第一步：dry_run 測試，確保參數正確
print("Testing with dry_run=True...")
scraper.fetch_query_form()
scraper.query_monthly_revenue("2303", "202605", dry_run=True)

# 審計日誌應輸出
# {"timestamp": "2026-06-13T...", "method": "POST", "url": "...", "status_code": 200, "dry_run": true}

# 如無異常，改為實際爬蟲
print("Running actual scrape...")
scraper.delay_seconds = 3
resp = scraper.query_monthly_revenue("2303", "202605", dry_run=False)
```

#### Session Cookie 與持久化

```python
# 某些網站需要先登入、維持 session
import pickle

class AuthenticatedPortalScraper(PortalScraper):
    def __init__(self, cookie_file="cookies.pkl"):
        super().__init__()
        self.cookie_file = cookie_file
        self.load_cookies()
    
    def load_cookies(self):
        """從檔案恢復舊 session，避免每次重新登入"""
        import os
        if os.path.exists(self.cookie_file):
            with open(self.cookie_file, "rb") as f:
                self.session.cookies.update(pickle.load(f))
    
    def save_cookies(self):
        """登入後存檔，下次復用"""
        with open(self.cookie_file, "wb") as f:
            pickle.dump(self.session.cookies, f)
    
    def login(self, username, password):
        """執行登入並持久化 session"""
        resp = self.request_with_throttle(
            "POST",
            "https://example.com/login",
            data={"user": username, "pass": password}
        )
        if resp.status_code == 200:
            self.save_cookies()
            print("✅ Logged in and cookies saved")
        return resp
```

---

### 第三步：Dry Run 與審計日誌工作流

此工作流確保生產前不會被封 IP：

```bash
# 1. 設置 audit_log.py 來監控所有請求
python -c "
import json
from pathlib import Path

log_file = Path('audit_log.jsonl')

# 統計請求數與錯誤
entries = [json.loads(line) for line in log_file.read_text().strip().split('\n') if line]
total = len(entries)
errors = [e for e in entries if e.get('error')]
rate_limited = [e for e in entries if e.get('status_code') == 429]
forbidden = [e for e in entries if e.get('status_code') == 403]

print(f'Total requests: {total}')
print(f'Errors: {len(errors)}')
print(f'Rate limited (429): {len(rate_limited)}')
print(f'Forbidden (403): {len(forbidden)}')

if errors:
    print('\nFirst 3 errors:')
    for e in errors[:3]:
        print(f'  {e}')
"

# 2. dry_run 測試流程
python -c "
from scraper import MOPSScraper

scraper = MOPSScraper()
# 測試 10 個查詢參數，確認都返回 200，無 429/403
test_params = [
    ('2303', '202605'),
    ('2330', '202605'),
    ('2308', '202605'),
]

for co_id, month in test_params:
    scraper.query_monthly_revenue(co_id, month, dry_run=True)
    print(f'✓ {co_id}/{month} passed')

print('\nDry run complete. Check audit_log.jsonl for details.')
"

# 3. 檢查日誌無異常後，改為實際爬蟲（移除 dry_run=True）
# git diff audit_log.jsonl → 確認只有 dry_run=true 的記錄
# 上述測試全通過後，才執行生產爬蟲

# 4. 生產爬蟲時持續監控
tail -f audit_log.jsonl | grep -E '"(429|403|error)"'
# 如有 429/403，立即停止爬蟲並調整 delay_seconds
```

---

### 第四步：適應不同網站的決策樹應用

#### 案例 A：MOPS 月營收

優先級應用：

1. **先試公開 API**（第一優先）
   ```bash
   curl "https://mops.twse.com.tw/mops/web_api/v1/publicCompanyMonthlyRevenue?co_id=2303&month=202605"
   ```
   ✅ 成功 → 用此方案，無需爬蟲

2. **再試靜態 CSV 下載**（第二優先）
   ```bash
   curl "https://mops.twse.com.tw/mops/export/..." -o monthly.csv
   ```
   ✅ 成功 → 改用下載，月 1 次全量抓取

3. **才爬 HTML 後台**（第三優先）
   ```python
   scraper = MOPSScraper()
   scraper.delay_seconds = 2.5
   resp = scraper.query_monthly_revenue("2303", "202605", dry_run=True)  # 測試
   # 日誌確認無誤後才改 dry_run=False
   ```

#### 案例 B：政府標案查詢系統

類似優先級應用（以標案中心為例）：

1. **檢查公開 API**
   ```bash
   # 部分政府機構提供 API，如 tenders API
   curl "https://api.example.gov.tw/tenders?year=2026"
   ```

2. **檢查 OData feed**
   ```bash
   curl "https://example.gov.tw/odata/Tenders?$filter=year eq 2026"
   ```

3. **爬表單頁面**（需用表單參數 + session）
   ```python
   scraper = AuthenticatedPortalScraper()
   scraper.login(username, password)
   # 然後爬標案清單
   ```

---

## 注意事項

### MOPS 特定限制

- **查詢歷史有頻率限制**：月營收查詢日超過 100 次會被暫時限速
  - 對策：合併查詢（一次提交多個公司代號）或改用公開 API
  
- **session 有效期短**：約 20 分鐘內無活動會自動登出
  - 對策：使用 `AuthenticatedPortalScraper` 持久化 cookie，並在 403 後自動重登

- **__VIEWSTATE 與 __EVENTVALIDATION 必須成對**：每次頁面重載都會改變
  - 對策：見 `fetch_query_form()` 方法，每個 session 開始時刷新一次

- **大批量查詢（>1000 條 / 天）應改走 CSV 下載或 API**
  - 對策：月營收用 API，公告用 RSS，都不需要爬

### 法規與倫理考量

- **檢查網站 `robots.txt`**
  ```bash
  curl "https://mops.twse.com.tw/robots.txt"
  # MOPS disallow 較少，但財報頁面可能有限制
  ```

- **查詢服務條款（ToS）**：確認爬蟲許可
  - 大多數政府網站允許機器訪問（用於研究），但商業使用需確認

- **不要爬有「著作權」或「禁止轉載」標籤的內容**

### 監控與應急

- **設置告警**：audit_log 中連續 3 個 429 或 1 個 403 時立即停止爬蟲
  ```python
  if forbidden_count >= 1 or rate_limited_count >= 3:
      print("❌ Scraper blocked. Exiting.")
      exit(1)
  ```

- **常見被封原因與對策**
  | 症狀 | 原因 | 對策 |
  |------|------|------|
  | HTTP 429 | 請求過快 | 增加 `delay_seconds` |
  | HTTP 403 | User-Agent 不合理或無效 session | 更新 User-Agent、重登入 |
  | 連線斷開 | 網站主動重置 | 加入 retry 邏輯 + exponential backoff |
  | IP 被永久封禁 | 觸發 WAF | 改用代理 IP（如有許可） |

- **長期穩定性檢查清單**
  - [ ] 每個爬蟲都有 audit_log 記錄
  - [ ] dry_run 測試通過後才改生產
  - [ ] delay_seconds ≥ 網站估計負載 × 1.5
  - [ ] 有 retry 邏輯與 exponential backoff
  - [ ] 監控 audit_log 中的 429/403 趨勢
  - [ ] 定期（月 1 次）驗證公開 API / CSV 是否變動

---

## 延伸資源

- **既有 MOPS skills**：`mops-rev-scraper`、`mops-financial-scraper` 提供具體爬蟲實裝，可參考 session 管理與表單提交細節
- **audit_log.py 參考實裝**：查看專案的 `lib/audit_log.py`（如有）
- **Browser DevTools 教學**：Network 標籤用於發現公開 API 與靜態資源層