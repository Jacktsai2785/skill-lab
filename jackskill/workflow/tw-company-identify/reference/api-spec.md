# API Spec — Taiwan Company Data Sources

本 skill 用到的台灣公司資料來源，欄位、查詢方式、特殊注意事項。

## 1. ronnywang g0v 公司搜尋（主要）

| 用途 | URL |
|------|-----|
| 名稱搜尋 | `https://company.g0v.ronny.tw/api/search?q={name}` |
| 統編查詢 | `https://company.g0v.ronny.tw/api/id/{tax_id}` |

**回應重點欄位（來自 `data` 物件 / `data` 陣列）：**

| 欄位 | 說明 |
|------|------|
| `公司名稱` | 官方登記名 |
| `統一編號` | 8 碼數字 |
| `代表人姓名` | 負責人 |
| `公司所在地` | 登記地址 |
| `實收資本額(元)` | 實際繳足資本 (字串含 `,`) |
| `每股金額(元)` | 票面金額 |
| `已發行股份總數(股)` | 流通股數 |
| `董監事名單` | 物件陣列：`姓名`/`職稱`/`所代表法人`/`出資額` |

**特殊注意：**

- `所代表法人` 為 `[統編, 公司名稱]` 二元陣列，或空字串。
- 出資比例用 `出資額 / 已發行股份總數` 計算（精度建議 6 位小數）。
- 名稱搜尋可能多筆命中；優先取 `公司名稱` 完全相符者，否則第一筆。
- API 偶爾 503，必須有 fallback。
- 無 rate limit 文件；建議 timeout 15 秒、總體 20 秒。

## 2. GCIS 商工登記公開 API（fallback）

OData 介面，僅 by 統編查詢可靠。

| 用途 | URL |
|------|-----|
| 公司基本資料 (App1) | `https://data.gcis.nat.gov.tw/od/data/api/5F64D864-61CB-4D0D-8AD9-492047CC1EA6` |
| 董監事 | `https://data.gcis.nat.gov.tw/od/data/api/6BBA2268-1367-4B42-9CCA-BC17499EBE8C` |

**查詢範例：**

```
?$format=json&$filter=Business_Accounting_NO eq '22099131'&$skip=0&$top=1
```

**App1 回應重點欄位：**

| 欄位 | 說明 |
|------|------|
| `Company_Name` | 官方登記名 |
| `Business_Accounting_NO` | 統編 |
| `Responsible_Name` | 負責人 |
| `Paid_In_Capital_Amount` | 實收資本額 |
| `Capital_Stock_Amount` | 章程資本額 (authorized capital) |
| `Company_Location` | 公司地址 |

**特殊注意：**

- g0v 沒有 `authorized_capital`（章程資本），需從 GCIS 補齊。
- GCIS 不含董監事於 App1，須另呼叫董監事 API。
- 大型整批查詢請降頻，避免被拒絕服務。

## 3. 上市/上櫃/興櫃狀態（TWSE / TPEX）

每日更新的公開 JSON dataset，本 skill 24h 一次全量載入後比對。

| 板別 | URL | 識別欄位 |
|------|-----|---------|
| 上市 | `https://openapi.twse.com.tw/v1/opendata/t187ap03_L` | `營利事業統一編號` / `公司名稱` |
| 上櫃 | `https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O` | `UnifiedBusinessNo.` / `CompanyName` |
| 興櫃 | `https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_R` | `UnifiedBusinessNo.` / `CompanyName` |

**比對策略：**
1. 統編完全相符
2. 公司名稱完全相符
3. （創新板）剝除「股份有限公司」/「有限公司」後的簡稱比對

未命中 → `非公發`。

## 4. 創新板 GISA（TPEX）

| 用途 | URL |
|------|-----|
| 創新板公司清單 | `https://www.tpex.org.tw/openapi/v1/tpex_gisa_company` |

**特殊注意：**

- 此 API 必須帶 `Accept: application/json` header，否則回傳 HTML。
- 只給「簡稱」(`CompanyName`)，無統編；比對需先剝除公司結尾後再對。
- **創櫃板**目前 TPEX 無公開 JSON API，無法自動辨識，會被歸為「非公發」。

## 5. Cache 策略

| 資料 | TTL | 理由 |
|------|-----|------|
| 上市狀態（TWSE/TPEX/GISA 全量） | 24 小時 | 公司上市/下市異動低頻 |
| g0v / GCIS 個別查詢 | 不快取 | 即時資料；呼叫端自行決定是否快取 |

實作於 `scripts/identify.py` 的 `ensure_listing_cache()`，process 內 in-memory；重啟即重新載入（首次約 5–10 秒）。
