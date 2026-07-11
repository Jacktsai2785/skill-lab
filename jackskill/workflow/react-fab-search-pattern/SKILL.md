---
name: react-fab-search-pattern
description: "一鍵生成 typed search endpoint + debounced FAB + keyboard nav（↑↓ Enter ESC）+ route 跳轉全套。TRIGGER when: 「加浮動搜尋」「FAB 搜公司/ticker 跳頁」「全域快速搜尋」「command palette 雛形」"
when_to_use: 需要在 React/Next.js app 中快速加入全域或模組級的浮動搜尋組件，支援 keyboard navigation 和自動導航
version: 1.0.0
tags:
  - frontend
  - react
  - search
  - faq
  - pattern
languages: all
---

## Overview

react-fab-search-pattern 封裝了「浮動搜尋框 (FAB)」的完整實現路徑：

- **Typed Backend Endpoint**：schema 定義 → 後端搜尋邏輯 → TypeScript client 生成
- **Debounced Frontend Component**：防止過度查詢、smooth UX、自動清除舊結果
- **Keyboard Navigation**：↑↓ 上下選項、Enter 執行、ESC 關閉（command palette 模式）
- **Auto-Route Navigation**：選中結果自動跳頁（如搜公司 → 跳到公司詳頁）

該 pattern 源自 ~80+ 訊息的 Session 2 經驗，已驗證可複用於「公司搜尋」、「ticker 搜尋」、「通用全域搜尋」等場景。避免每次從 0 寫起 schema → endpoint → typed client → debounced UI → route 的 5 步重複。

## 何時使用

**明確觸發徵兆：**
- 使用者說「加一個浮動搜尋」或「在 header 加搜尋框」
- 需要「FAB 搜公司跳詳頁」、「搜 ticker 跳交易頁」等導航搜尋
- 要建 「command palette 雛形」或全域快速搜尋
- 設計上強調「快速定位」(as-you-type search)

**不適用場景：**
- 靜態篩選（無動態搜尋邏輯）
- 簡單 input + submit 的傳統搜尋表單
- 搜尋結果頁面（vs. 浮動選單式結果）

## 執行步驟

### 1. 定義 Search Endpoint Schema

在後端 API schema 定義搜尋入參與出參。以公司搜尋為例，在 schema/search.ts 或 api/schema.ts：

入參：
- query (string)：搜尋關鍵字，最少 2 個字元
- limit (number, optional)：結果上限，預設 10

出參 (CompanySearchResult)：
- id (string)：主鍵
- name (string)：顯示名稱
- ticker (string, optional)：股票代號或識別碼
- category (string, optional)：分類或標籤
- route (string)：跳轉路徑，**必須**，如 /company/${id}

### 2. 實作後端 Search Endpoint

建立 API route (api/search/company.ts 或 pages/api/search/[entity].ts)：

export async function GET(req: Request) {
  const { query, limit = 10 } = req.nextUrl.searchParams
  
  if (!query || query.length < 2) {
    return Response.json({ results: [] })
  }
  
  // 呼叫搜尋邏輯（DB query、API call 等）
  const results = await searchCompanyByName(query, limit)
  
  // 轉換為統一格式（含 route）
  return Response.json({
    results: results.map(r => ({
      id: r.id,
      name: r.name,
      ticker: r.ticker,
      category: r.category,
      route: `/company/${r.id}`,
    }))
  })
}

### 3. 生成 Typed Client

在 lib/api/search-client.ts 建立 typed fetch wrapper：

export async function searchCompany(query: string, limit?: number) {
  const params = new URLSearchParams({ query, ...(limit && { limit: limit.toString() }) })
  const res = await fetch(`/api/search/company?${params}`)
  return res.json() as Promise<{ results: CompanySearchResult[] }>
}

### 4. 實作 Debounced FAB Component

在 components/CompanySearchFAB.tsx 建立完整 FAB：

'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { searchCompany } from '@/lib/api/search-client'

interface SearchResult {
  id: string
  name: string
  route: string
  category?: string
}

export function CompanySearchFAB() {
  const [isOpen, setIsOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [isLoading, setIsLoading] = useState(false)
  
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()
  const router = useRouter()
  
  // Debounced search
  const handleQueryChange = useCallback((q: string) => {
    setQuery(q)
    setSelectedIndex(0)
    
    clearTimeout(debounceRef.current)
    if (!q.trim()) {
      setResults([])
      return
    }
    
    debounceRef.current = setTimeout(async () => {
      setIsLoading(true)
      try {
        const { results } = await searchCompany(q, 10)
        setResults(results)
      } catch (err) {
        console.error('Search failed:', err)
        setResults([])
      } finally {
        setIsLoading(false)
      }
    }, 300) // 300ms debounce
  }, [])
  
  // Keyboard navigation
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (!isOpen) return
    
    switch (e.key) {
      case 'ArrowUp':
        e.preventDefault()
        setSelectedIndex(i => Math.max(0, i - 1))
        break
      case 'ArrowDown':
        e.preventDefault()
        setSelectedIndex(i => Math.min(results.length - 1, i + 1))
        break
      case 'Enter':
        e.preventDefault()
        if (results[selectedIndex]) {
          router.push(results[selectedIndex].route)
          setIsOpen(false)
          setQuery('')
          setResults([])
        }
        break
      case 'Escape':
        e.preventDefault()
        setIsOpen(false)
        break
    }
  }, [isOpen, results, selectedIndex, router])
  
  const selectResult = (result: SearchResult) => {
    router.push(result.route)
    setIsOpen(false)
    setQuery('')
    setResults([])
  }
  
  return (
    <div className="fixed bottom-8 right-8 z-50">
      {isOpen && (
        <div className="absolute bottom-20 right-0 w-64 bg-white rounded-lg shadow-lg border border-gray-200">
          <input
            autoFocus
            type="text"
            placeholder="搜尋公司..."
            value={query}
            onChange={e => handleQueryChange(e.target.value)}
            onKeyDown={handleKeyDown}
            className="w-full px-3 py-2 border-b border-gray-200 focus:outline-none"
          />
          {isLoading && <div className="px-3 py-2 text-sm text-gray-500">搜尋中...</div>}
          {results.length === 0 && query && !isLoading && (
            <div className="px-3 py-2 text-sm text-gray-500">無結果</div>
          )}
          <ul className="max-h-80 overflow-y-auto">
            {results.map((result, idx) => (
              <li key={result.id}>
                <button
                  onClick={() => selectResult(result)}
                  className={`w-full text-left px-3 py-2 text-sm hover:bg-blue-50 transition ${
                    idx === selectedIndex ? 'bg-blue-50 border-l-2 border-blue-500' : ''
                  }`}
                >
                  <div className="font-medium">{result.name}</div>
                  {result.category && <div className="text-xs text-gray-500">{result.category}</div>}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="bg-blue-500 hover:bg-blue-600 text-white rounded-full w-14 h-14 flex items-center justify-center shadow-lg transition"
        aria-label="搜尋"
      >
        🔍
      </button>
    </div>
  )
}

### 5. Mount 到 App Layout

在 app/layout.tsx 或任何上層 layout 引入 FAB：

import { CompanySearchFAB } from '@/components/CompanySearchFAB'

export default function RootLayout({ children }) {
  return (
    <html>
      <body>
        {children}
        <CompanySearchFAB />
      </body>
    </html>
  )
}

## 注意事項

### Debounce 時間權衡
- **300ms**：預設值，適合多數場景（UX 流暢 + 伺服器負載平衡）
- **100ms**：高反應度，但查詢頻率高，適合小型結果集或緩存良好的場景
- **600ms**：減少伺服器壓力，但用戶感受較「卡頓」

### Keyboard Navigation 邊界
- 當 results 為空時，↑↓ 無效果（index 維持 0）
- Enter 必須有 selectedIndex < results.length 才跳轉，否則無操作

### Route 欄位必須
search endpoint 出參**一定要包含 route 欄位**，不然 FAB 無法自動導航。若結果沒有「專屬詳頁」，可設定為特殊頁面（如 /search-result?id=${id}）

### 快速鍵衝突
若 app 已有全域快速鍵（如 Cmd+K 開 command palette），考慮繫結 FAB 的開啟：

useEffect(() => {
  const handleGlobalKeydown = (e: KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault()
      setIsOpen(true)
    }
  }
  window.addEventListener('keydown', handleGlobalKeydown)
  return () => window.removeEventListener('keydown', handleGlobalKeydown)
}, [])

### 結果樣式彈性
上例採「藍色 hover + 左邊界標記選項」，可改為：
- Badge 標記 category
- Star icon 標記常用項目
- 分組展示（如「最近搜尋」+ 「建議結果」）
- Dark mode 支援（檢查 prefers-color-scheme）

### 搜尋結果缺存
若搜尋頻繁且結果變化不大，加入簡單 in-memory cache：

const cache = new Map<string, SearchResult[]>()

const handleQueryChange = useCallback((q: string) => {
  if (cache.has(q)) {
    setResults(cache.get(q) || [])
    return
  }
  
  // 正常 debounced 搜尋...
  debounceRef.current = setTimeout(async () => {
    const { results } = await searchCompany(q, 10)
    cache.set(q, results)
    setResults(results)
  }, 300)
}, [])

## 變種應用

此 pattern 可套用於任何「entity 搜尋 → 導航」場景：

- **ticker 搜尋**：endpoint /api/search/ticker，route /stock/${ticker}
- **使用者搜尋**：endpoint /api/search/user，route /user/${userId}
- **通用全域搜尋**：endpoint /api/search/global，route 依結果類型動態決定
- **tag 搜尋**：endpoint /api/search/tag，route /tag/${tagId}

核心改變只有 endpoint URL、schema 結構、以及 route template，component 邏輯通用。