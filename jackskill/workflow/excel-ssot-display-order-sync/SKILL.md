---
name: excel-ssot-display-order-sync
description: Excel 當 SSOT 同步 display_order 到 DB，並 audit 三層一致性（DB → API → frontend）。TRIGGER when: 「順序怪怪的」「Excel 改了但網頁沒動」「前端不要自己 sort」
when_to_use: |
  - 資料順序應以 Excel 為準，但 DB/API/前端各層出現不同排序
  - 前端不確定是否該用 sort() 或信任後端順序
  - display_order 欄位存在但未被正確同步或使用
  - 懷疑前端自作聰明排序蓋掉了後端邏輯
version: 1.0.0
tags: [data-sync, ssot, order-consistency, database, audit]
languages: all
---

## Overview

當資料順序由 Excel 驅動時，三層都容易出問題：
- **Excel → DB**：display_order 欄位可能未同步或同步邏輯錯誤
- **DB → API**：API response 可能沒有按 display_order 排序
- **API → frontend**：前端用 sort() 自行排序，蓋掉後端秩序

這支 skill 透過系統性審計和同步，確保三層一致性，並消除前端自主排序的陷阱。

## 何時使用

### 現象 1：順序怪怪的
前端頁面上的資料順序與 Excel 不符，或每次重新整理順序都不一樣。
**步驟**：確認 Excel SSOT、檢查 display_order 值、驗證 API 排序。

### 現象 2：Excel 改了但網頁沒動
在 Excel 中調整了 display_order（或拖拖拉拉改了列序），頁面卻沒反映。
**步驟**：確認是否有自動同步機制、手動觸發同步、清快取。

### 現象 3：display_order 從哪來
新加欄位或新表，不確定 display_order 的來源和維護責任。
**步驟**：定義 Excel 為 SSOT、建立同步流程、禁用前端自動排序。

### 現象 4：前端不要自己 sort
審查前端程式碼發現多個 .sort() 呼叫，造成順序混亂。
**步驟**：移除前端 sort()、用 API 排序、驗證三層一致。

## 執行步驟

### 第 1 步：確認 Excel 為 SSOT
1. 定位資料來源 Excel 檔（通常在 data/、sheet/ 或 config/ 資料夾）
2. 確認是否有 `display_order` 欄位，或需要新增
3. 檢查 Excel 中的列序（上到下）是否正確反映期望的顯示順序
4. 記錄欄位名稱、資料類型（通常是整數或 0-based index）

**例**：
```
| id | name      | display_order |
|----|-----------|---------------|
| 1  | Item A    | 1             |
| 2  | Item B    | 2             |
| 3  | Item C    | 3             |
```

### 第 2 步：檢查 DB 層同步
1. 查看是否有 migration 或 seeding 邏輯將 Excel 資料載入 DB
2. 確認 display_order 欄位在 table schema 中存在（否則新增）
3. 驗證資料已載入且值正確
   ```sql
   SELECT id, name, display_order FROM your_table ORDER BY id;
   ```
4. 如果發現 display_order 為 NULL 或全為 0，表示同步未完成

### 第 3 步：驗證 API 排序邏輯
1. 檢查 API endpoint 程式碼（通常在 routes/ 或 controllers/ 中）
2. 確認回傳資料時有按 display_order 排序：
   ```python
   # 例：Python/Flask
   items = Item.query.order_by(Item.display_order).all()
   ```
3. 測試 API 呼叫，確認回傳順序正確
   ```bash
   curl http://localhost:8000/api/items | jq '.[].display_order'
   ```

### 第 4 步：審計前端程式碼
1. 搜尋前端中所有 `.sort()` 呼叫：
   ```bash
   grep -rn "\.sort(" src/
   ```
2. 檢查是否有人為排序（而非信任 API）
3. 移除不必要的 sort()，改為信任 API response 順序
   ```javascript
   // ❌ 不要這樣
   const items = await fetch('/api/items').then(r => r.json());
   items.sort((a, b) => a.name.localeCompare(b.name));

   // ✅ 這樣
   const items = await fetch('/api/items').then(r => r.json());
   // items 已按 display_order 排序，直接用
   ```

### 第 5 步：建立同步流程（選擇一種）

#### 方案 A：批量匯入 Excel（一次性或定期）
```python
import openpyxl
from sqlalchemy import update

wb = openpyxl.load_workbook('data/items.xlsx')
ws = wb.active

for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=1):
    item_id, name, display_order = row
    stmt = update(Item).where(Item.id == item_id).values(display_order=row_idx)
    session.execute(stmt)

session.commit()
print(f"Synced {row_idx} rows from Excel")
```

#### 方案 B：手動同步 endpoint
```python
@app.post('/admin/sync-display-order')
def sync_display_order():
    items = Item.query.all()
    for idx, item in enumerate(items, start=1):
        item.display_order = idx
    db.session.commit()
    return {'status': 'synced', 'count': len(items)}
```

#### 方案 C：資料庫觸發器（實時一致）
```sql
CREATE TRIGGER update_display_order
BEFORE UPDATE ON items
FOR EACH ROW
BEGIN
  IF NEW.display_order IS NULL THEN
    SET NEW.display_order = (SELECT COALESCE(MAX(display_order), 0) + 1 FROM items);
  END IF;
END;
```

### 第 6 步：驗證三層一致性
1. **Excel → DB**：匯入後查詢 DB 確認值正確
2. **DB → API**：呼叫 API 確認順序未亂序
3. **API → frontend**：在前端 devtools 檢查網路請求的 JSON 順序

```javascript
const items = await fetch('/api/items').then(r => r.json());
const orders = items.map(i => i.display_order);
console.log('Display orders from API:', orders);
// 應該遞增：[1, 2, 3, ...]
```

## 注意事項

### 1. 多重排序源頭問題
即使 API 正確排序，前端可能在表格本身套用列排序、搜尋篩選後重新排序，或在 state 管理層自動排序。移除這些才能確保一致性。

### 2. 舊資料的 display_order 為空
如果 display_order 欄位新增時已有資料，需要一次性回填：
```sql
UPDATE items SET display_order = ROW_NUMBER() OVER (ORDER BY id) WHERE display_order IS NULL;
```

### 3. 插入新資料時的順序
新增資料時，display_order 必須遵循規則（遞增或由 Excel 指定）。不要讓應用層猜測，應在 migration 或 API 層強制設定。

### 4. 快取問題
- 如果 API 有 HTTP 快取（ETags, Cache-Control），更新後需清快取
- 前端也可能有 Service Worker 快取，需清 storage

### 5. Excel 檔案編碼
確保 Excel 檔使用 UTF-8 或支援中文編碼，讀取時指定編碼，避免亂碼。

### 6. 與其他 SSOT 的區別
本 skill 專注 **Excel → DB → API → frontend** 的順序同步。若需要其他欄位（名稱、描述等）的同步，參考 `markdown-file-ssot`。兩者可搭配使用，但責任邊界需清楚。

### 7. 效能考量
大表時 `.order_by(display_order)` 應建立索引。頻繁 Excel 匯入時考慮批量操作，避免逐筆 INSERT：
```sql
CREATE INDEX idx_items_display_order ON items(display_order);