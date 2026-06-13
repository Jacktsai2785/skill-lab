---
name: plan-with-external-benchmarks
trigger: |
  TRIGGER when: 「我想做 X feature，先看別人怎麼做」「benchmark 一下再規劃」「產業地圖／feature 設計」「competitors 怎麼實作」「業界標準做法」
when_to_use: 新功能規劃前需要了解業界實踐、競品設計或技術標準，避免閉門造車；特別是涉及 UX 決策、架構選型、產品方向時
description: |
  Plan mode 固定流程：並行 Explore agent（看 codebase 現況）+ WebSearch/WebFetch（看業界標竿）
  → 整合進 plan → AskUserQuestion 收斂 3 個核心設計抉擇
version: 1.0.0
tags:
  - planning
  - research
  - benchmarking
  - design-decisions
  - external-data
  - workflow
languages: all
---

## Overview

「從我想做什麼」到「怎麼做最好」的中間，往往有 3 個陷阱：
1. **閉門造車** — 不知道業界怎麼做，規劃得再完美也可能踩過的坑
2. **設計決策無據** — 「應該選 A 還是 B」沒有外部參考，容易後悔
3. **內部現況認知不足** — 邊界條件、既有實作、技術債沒有清楚理解

本 skill 在 Plan mode 中自動化執行一套前置流程：
- 同步爬取業界 benchmark（並行 WebSearch + WebFetch 看競品、開源實現、最佳實踐）
- 並行掃描 codebase（Explore agent 看現有實作邊界）
- 整合結果到 plan draft 中
- 用 `AskUserQuestion` 把最關鍵的 3 個設計抉擇收斂到明確答案

結果是你會進入 `/plan` 時已經有「業界這麼做、我們現在這樣、我們可以那樣」的 3 維度對比，大幅降低後期 review 發現「咦，其實有更好的方案」的風險。

## 何時使用

### 典型觸發場景
- **Feature 規劃** — 「我想加 real-time collaboration」「計畫做 AI-powered 功能」
- **架構決策** — 「要不要從 REST 改 GraphQL」「database 應該 scale 到什麼程度」
- **UX 改版** — 「dashboard 該怎麼重新組織」「navigation 的最佳實踐」
- **整合方案** — 「OAuth 應該怎麼建」「file upload 的流程」
- **技術選型** — 「該用哪個 library」「前端框架選項」

### 不適合用的場景
- Bug fix 或 hotfix（已經明確問題所在）
- 純粹的 refactoring（內部優化，不涉及外部設計）
- 需要立即部署的緊急工作
- 已經確定方案、只是實作細節的規劃

## 執行流程

### 前置：進入 Plan mode
```
/enter-plan-mode
```
確認你要進 Plan mode（如果尚未進入）。

### 第 1 階段：並行蒐集

同時啟動兩條線：

**A. 內部程式碼掃描（Explore agent）**
```
agent(subagent_type: 'Explore', prompt: """
掃描這個 codebase，找出：
1. 已經存在的 [特性名] 相關實作（檔案、模組、設計模式）
2. 現有架構的限制（技術債、已知瓶頸、邊界條件）
3. 可以複用的模組或模式

聚焦在「我們現在的起點是什麼」，而不是「應該怎麼改」。
""")
```

**B. 業界 benchmark（WebSearch + WebFetch）**
```
parallel([
  () => web_search("[特性名] best practices 2026", filter: "recent"),
  () => web_search("[特性名] open source implementations"),
  () => web_search("competitor [特性名] design", filter: "case studies"),
  () => web_fetch("官方文件 URL", sections: "architecture/design"),
])
```

針對你的特性，具體搜尋：
- **「最佳實踐」** — 官方文件、技術文章、GitHub trending
- **「競品做法」** — 競爭產品的公開技術文章、上市說明會
- **「開源參考」** — GitHub stars 最高的同類 library

### 第 2 階段：整合成 3 個設計抉擇

把蒐集的資訊整理成「設計選項對比表」：

| 設計維度 | 方案 A | 方案 B | 方案 C | 業界趨勢 |
|---------|--------|--------|--------|---------|
| **架構** | 中心化 | 分散 | Hybrid | 看實現複度 |
| **效能** | O(n) | O(log n) | O(1) | 看負載 |
| **複度** | 低 | 中 | 高 | 看維護成本 |

從這個表中挑出最關鍵的 3 個抉擇（通常是：架構方向、複度/成本權衡、擴展性）。

### 第 3 階段：收斂設計決策

用 `AskUserQuestion` 明確 3 個問題：

```javascript
AskUserQuestion({
  questions: [
    {
      question: "針對 [特性]，我們要優先 [A 軸] 還是 [B 軸]？",
      header: "設計方向",
      options: [
        { 
          label: "A 方案（理由）", 
          description: "優點 / 缺點 / 業界例子"
        },
        { 
          label: "B 方案（理由）", 
          description: "優點 / 缺點 / 業界例子"
        }
      ]
    },
    {
      question: "複度／成本權衡：我們願意承諾多少投入？",
      header: "投入預算",
      options: [
        { label: "MVP（快速上線）", description: "..." },
        { label: "基礎版（夠用）", description: "..." },
        { label: "企業級（完整）", description: "..." }
      ]
    },
    {
      question: "擴展性：預期的規模是？",
      header: "擴展假設",
      options: [
        { label: "小型（<1k users）", description: "..." },
        { label: "中型（1k-100k）", description: "..." },
        { label: "大型（>100k）", description: "..." }
      ]
    }
  ]
})
```

使用者的回答會直接進入 plan draft 的「設計決策」章節。

### 第 4 階段：進入完整 Plan

有了這 3 個明確的決策，你可以：
```
/plan
```
進入完整規劃模式，plan 會自動融合 benchmark 結果 + 設計決策 + codebase 現況，生成更札實的方案。

## 注意事項

### 信息品質
- **WebSearch 結果有雜訊** — 要求 Explore agent 在 WebFetch 前先掃描結論（grep 關鍵字），避免抓到無關文章
- **競品資訊有延遲** — 如果搜到的是 2-3 年前的文章，記得問「這還是現在的做法嗎」
- **開源實現未必是最佳** — stars 多 ≠ 生產級，務必檢查是否有 major version / breaking changes

### 時間成本
- 蒐集 benchmark 通常花 5–10 分鐘（取決於搜尋難度）
- 不要追求「所有可能的方案都看一遍」——聚焦在top 3–5 個實踐
- 如果某個維度的資訊太少，直接跳過（不要浪費時間）

### 設計決策的收斂
- 3 個決策是經驗值，不是硬性限制——如果只有 1-2 個關鍵抉擇，就問 1-2 個
- 如果決策有多於 3 個，優先級排序：「影響架構」>「影響成本」>「影響體驗」
- 用戶回答後，**立即寫進 plan draft**——別放到後期「咦怎麼沒記」

### 與既有 skill 的搭配
- **結束後進 `/plan`** — 這個 skill 的輸出是 plan 的前置，不是替代
- **不要混用 `writing-plans`** — writing-plans 是規範 plan 結構，本 skill 是前置蒐集
- **Plan review 用 `/plan-eng-review`** — benchmark 資訊會自動帶入 review context

### 邊界條件
- 若 codebase 是全新專案（無既有實作），Explore 會返回空結果——正常，就著重於 benchmark 邊
- 若業界沒有成熟做法（e.g. 非常新的技術），WebSearch 會返回很少結果——改成「我們怎麼從第一原理出發」的 planning
- 若使用者在 AskUserQuestion 時卡住（無法選），這通常代表 benchmark 資訊不足，可追加一輪 WebFetch