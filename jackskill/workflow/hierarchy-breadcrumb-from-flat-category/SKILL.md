---
name: hierarchy-breadcrumb-from-flat-category
description: |
  WHEN: 需要從平坦 key（如 `"生技-西藥"`）反推層級、渲染麵包屑、同步 URL `?group=` state
  — 避免手工維護分類 parent-child mapping table，自動推導階層結構
when_to_use: |
  - 分類列表按 prefix 分組時，麵包屑少一層或層級關係不清楚
  - SummaryPage / ProductIndex 需要「回到上一分類」的父層連結
  - URL state（`?group=生技`）與選中分類要同步，但無法硬編碼層級
  - 多個分類系統重複出現同一個「flat key → breadcrumb」的轉換邏輯
version: 1.0.0
tags:
  - breadcrumb
  - hierarchy
  - category-navigation
  - url-state-sync
  - product-index
languages: all
---

## Overview

在資料結構使用「平坦 key + delimiter 隱含層級」的場景中（如 `"生技-西藥"`、`"電子-IC設計-晶片"`），需要動態推導層級樹狀結構，用來：

1. **自動生成麵包屑**：從 `"生技-西藥"` → `[生技] > [西藥]`
2. **URL 狀態同步**：點擊麵包屑後更新 `?group=生技` 或 `?group=生技&subgroup=西藥`
3. **避免硬編碼**：不需要維護 parent → child 的對應表，直接從 key 字串解析

這個 pattern 在 Session 3 的分類 UI、Session 2 的 SummaryPage 中重複出現，適用於任何使用「分隔符連接的分類名」的系統。

## 何時使用

### 場景 1：分類頁需要麵包屑
分類列表按 prefix 分組，點選子分類後顯示層級路徑：
```
生技 > 西藥 > [詳細商品列表]
```
需要點擊「生技」回到母層，點擊「西藥」回到當前層。

### 場景 2：多層分類與 URL 同步
ProductIndex 或儀表板同時展示：
- 選中的分類層級（`?level=1` → 生技 / `?level=2` → 西藥）
- 對應的商品或項目清單
- URL 後退/前進時麵包屑要跟著變

### 場景 3：SummaryPage 的「上一層」連結
列表頁頂部有「← 回 XX 分類」，需要自動推導出上層分類名稱，無法硬編碼。

## 執行步驟

### Step 1：定義 delimiter 與 key 結構

確認分類 key 的 delimiter。大多數情況使用 `-` 或 `/`：

```typescript
// 定義分隔符
const CATEGORY_DELIMITER = '-'

// 範例 keys
const flatKeys = [
  '生技-西藥',
  '生技-西藥-新藥開發',
  '電子-IC設計',
  '電子-IC設計-晶片',
  '電子-IC設計-晶片-AI加速器'
]
```

### Step 2：解析 key 為層級陣列

```typescript
function parseHierarchy(flatKey: string): string[] {
  return flatKey.split(CATEGORY_DELIMITER).filter(Boolean)
}

const example = parseHierarchy('生技-西藥-新藥開發')
// result: ['生技', '西藥', '新藥開發']
```

### Step 3：生成麵包屑物件陣列

麵包屑需要同時保存每層的「完整路徑 key」與「顯示名稱」，用於點擊導航：

```typescript
interface BreadcrumbItem {
  label: string        // 顯示文本，如 "西藥"
  pathKey: string      // 完整 key，如 "生技-西藥"（用於 URL 或篩選）
  level: number        // 層級編號
}

function generateBreadcrumbs(flatKey: string): BreadcrumbItem[] {
  const parts = parseHierarchy(flatKey)
  
  return parts.map((part, index) => ({
    label: part,
    pathKey: parts.slice(0, index + 1).join(CATEGORY_DELIMITER),
    level: index + 1
  }))
}

const crumbs = generateBreadcrumbs('生技-西藥')
// result:
// [
//   { label: '生技', pathKey: '生技', level: 1 },
//   { label: '西藥', pathKey: '生技-西藥', level: 2 }
// ]
```

### Step 4：與 URL query 同步

```typescript
// 從 URL 讀取當前選中層級
function getCurrentCategoryFromUrl(): string | null {
  const params = new URLSearchParams(window.location.search)
  return params.get('group')  // 或根據命名慣例改為 category / category-path
}

// 麵包屑點擊時更新 URL
function handleBreadcrumbClick(pathKey: string) {
  const url = new URL(window.location)
  url.searchParams.set('group', pathKey)
  window.history.pushState(null, '', url)
  
  // 觸發頁面重新渲染或篩選
  onCategoryChange(pathKey)
}

// React 範例：自動更新麵包屑
export function CategoryBreadcrumb() {
  const [categoryKey, setCategoryKey] = useState(() => 
    getCurrentCategoryFromUrl() || ''
  )
  
  const breadcrumbs = generateBreadcrumbs(categoryKey)
  
  return (
    <nav>
      {breadcrumbs.map((crumb, idx) => (
        <div key={crumb.pathKey}>
          <a href={`?group=${crumb.pathKey}`} onClick={(e) => {
            e.preventDefault()
            setCategoryKey(crumb.pathKey)
            window.history.pushState(null, '', `?group=${crumb.pathKey}`)
          }}>
            {crumb.label}
          </a>
          {idx < breadcrumbs.length - 1 && <span> > </span>}
        </div>
      ))}
    </nav>
  )
}
```

### Step 5：推導上層分類（父層）

如果需要「回上一層」的連結：

```typescript
function getParentCategory(flatKey: string): string | null {
  const parts = parseHierarchy(flatKey)
  
  if (parts.length <= 1) return null
  
  return parts.slice(0, -1).join(CATEGORY_DELIMITER)
}

const parent = getParentCategory('生技-西藥-新藥開發')
// result: '生技-西藥'

const parentOfParent = getParentCategory('生技-西藥')
// result: '生技'
```

### Step 6：在列表頁整合

```typescript
// SummaryPage.tsx
export function SummaryPage() {
  const categoryKey = new URLSearchParams(window.location.search).get('group')
  const breadcrumbs = generateBreadcrumbs(categoryKey || '')
  const parentKey = getParentCategory(categoryKey || '')
  
  return (
    <div>
      <Breadcrumb items={breadcrumbs} onNavigate={handleBreadcrumbClick} />
      
      {parentKey && (
        <button onClick={() => handleBreadcrumbClick(parentKey)}>
          ← 回 {parseHierarchy(parentKey).pop()} 分類
        </button>
      )}
      
      <ProductList filterBy={categoryKey} />
    </div>
  )
}
```

## 注意事項

### 1. Delimiter 約定要全域一致
所有地方都使用相同分隔符（如 `-`）。如果需要支援多個 delimiter，改用正規表達式：

```typescript
function parseHierarchy(flatKey: string): string[] {
  return flatKey.split(/[-–—/]/).filter(Boolean)  // 支援 - – — /
}
```

### 2. 層級深度不固定
不同分類可能有不同深度（有的 2 層，有的 4 層），breadcrumb 函數會自動處理，無需特殊邏輯。

### 3. 空層級處理
確保 split 後的陣列過濾掉空字串：

```typescript
flatKey.split(CATEGORY_DELIMITER).filter(Boolean)
```

避免 `"生技--西藥"` 這樣的不規範輸入產生空層級。

### 4. 名稱特殊字元
如果分類名稱本身包含 delimiter（如某分類叫 `"AI-ASIC"`），需要在資料層面規範化（如改用 `/` 或 `|`），或額外維護 escape 規則。

### 5. URL 編碼
若分類名稱包含中文或特殊字元，確保 URL 參數正確編碼：

```typescript
const url = new URL(window.location)
url.searchParams.set('group', encodeURIComponent(pathKey))
```

### 6. 歷史狀態（History API）
使用 `window.history.pushState()` 時，確保麵包屑點擊與後退按鈕行為一致。如果列表有篩選邏輯，考慮同時存儲篩選狀態到 URL。

## 整合檢查清單

- [ ] 確認分類 key 的 delimiter 與命名規範
- [ ] 在資料層定義 `CATEGORY_DELIMITER` 常數（或從 config 讀取）
- [ ] 實作 `parseHierarchy()` 與 `generateBreadcrumbs()` 函數
- [ ] 在麵包屑元件中呼叫這些函數，避免硬編碼 parent-child 關係
- [ ] 測試麵包屑點擊是否正確同步 URL 與列表篩選
- [ ] 測試瀏覽器後退/前進時麵包屑是否正確還原
- [ ] 如有多頁面使用此 pattern，將函數抽到共用 utility 檔案