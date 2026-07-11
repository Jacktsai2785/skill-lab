---
name: github-repo-onboard
description: >-
  讀取外部 GitHub 倉庫 → 分析架構差異 → 產出重構計畫。
  TRIGGER when: 使用者提供 GitHub URL 並要求「以這個為核心重構」、「參考這個倉庫」、「移植這個專案」
when_to_use: 需要參考他人開源專案的架構，快速生成當前專案的重構計畫或遷移清單
version: 1.0.0
tags:
  - workflow
  - architecture
  - migration
  - github
  - analysis
languages: all
---

## Overview

github-repo-onboard 協助開發者以外部 GitHub 倉庫為參考，快速分析架構差異並產出重構計畫。當需要移植、參考或完整重構現有專案時，此 skill 自動化整個分析流程：

1. **遠端倉庫分析** — 克隆目標倉庫、提取核心結構（目錄樹、package.json、配置檔等）
2. **本地架構掃描** — 列舉現有專案的技術棧、依賴、目錄組織
3. **差異識別** — 精確對比兩個倉庫的結構差異（語言、框架、層次、命名慣例）
4. **遷移計畫產出** — 生成具體的 task list、檔案對應表、需要新增/移除/修改的清單

典型價值：5–20 分鐘內產出本來需要 1–2 小時手工比對的重構計畫。

## 何時使用

### 典型場景

1. **以開源專案為範本重構**
   - 貼上他人優秀開源專案的 GitHub URL
   - 說「以這個倉庫的架構重構我們的專案」
   - Skill 自動分析架構差異、產出遷移清單

2. **複製他人專案結構（快速啟動）**
   - 需要快速學習或複製一個成熟的專案骨架
   - 貼上參考倉庫 URL
   - 產出「按順序執行」的檔案結構建設清單

3. **技術棧升級或遷移**
   - 發現更優秀的技術棧或框架
   - 需要評估遷移複雜度、規劃分階段遷移
   - Skill 產出分階段的遷移 task list

4. **架構審查與設計決策**
   - 不確定現有架構是否合理
   - 貼上參考倉庫進行對標分析
   - 確認「我們的組織方式」相對於「業界最佳實踐」的差異

## 執行步驟

### 基本流程

**第 1 步：提供倉庫 URL 與背景**

使用者貼上 GitHub URL（例如 `https://github.com/owner/repo`）並說明意圖：
- 「以這個倉庫為核心重構我們的專案」
- 「參考這個倉庫的架構」
- 「複製這個專案的目錄組織」

**第 2 步：遠端倉庫分析**

輕量級取得倉庫結構：

```bash
# 用 gh 或 git 取得基本資訊
gh repo view owner/repo --json description,languages,stargazers
git ls-remote --heads https://github.com/owner/repo
git ls-remote --tags https://github.com/owner/repo

# 淺層 clone（取得完整結構但歷史較少）
git clone --depth 1 --filter=blob:none https://github.com/owner/repo /tmp/repo-onboard
```

分析重點：
- 頂層目錄樹（`find /tmp/repo-onboard -maxdepth 2 -type d | head -30`）
- 配置檔清單（`find /tmp/repo-onboard -maxdepth 2 -type f \( -name 'package.json' -o -name 'tsconfig.json' -o -name 'Makefile' -o -name 'pyproject.toml' -o -name '.github' \)`）
- 語言與框架識別（掃描 package.json、requirements.txt、go.mod、Cargo.toml 等）
- 核心依賴版本（`cat /tmp/repo-onboard/package.json | jq '.dependencies, .devDependencies' 2>/dev/null | head -40`）
- README 與文件結構（標識部署、開發指南、測試指令）

**第 3 步：本地專案掃描**

```bash
# 列舉本地專案結構
find . -maxdepth 3 -type d ! -path '*/node_modules/*' ! -path '*/.git/*' ! -path '*/dist/*' ! -path '*/build/*' ! -path '*/.next/*'

# 提取技術棧指標
[ -f package.json ] && cat package.json | jq '.dependencies, .devDependencies'
[ -f requirements.txt ] && cat requirements.txt
[ -f go.mod ] && head -20 go.mod
```

掃描內容：
- 本地目錄組織（深度 3–4 層，排除 node_modules/.git 等）
- 技術棧（語言、框架、主要依賴及版本）
- 構建工具與配置（Webpack/Vite/Turbo 等）
- 測試框架與 CI/CD 配置（.github/workflows）
- 文件與部署配置

**第 4 步：架構對比與差異識別**

生成對比表：

| 維度 | 參考倉庫 | 本地專案 | 建議動作 | 優先度 |
|------|--------|--------|--------|--------|
| 語言 | TypeScript 4.9 | JavaScript | 遷移至 TypeScript，升級配置 | 高 |
| 框架 | Next.js 14 + App Router | Create React App | 升級至 Next.js 14，遷移至 App Router | 高 |
| 包管理 | pnpm workspace | npm | 遷移至 pnpm，配置 workspace | 中 |
| 目錄結構 | `src/app`, `src/lib`, `src/components` | `src/pages`, `src/utils` | 重組目錄樹 | 高 |
| 構建工具 | Turbo | 無 | 導入 Turbo monorepo | 中 |
| 測試 | Vitest + @testing-library | Jest + Enzyme | 遷移至 Vitest | 中 |
| Linting | ESLint + Prettier | ESLint 僅 | 補充 Prettier 配置 | 低 |
| CI/CD | GitHub Actions（多個 workflow） | GitHub Actions 單一 | 拆分與最佳化 workflow | 低 |

**第 5 步：產出遷移計畫**

生成具體的 task list（Markdown 格式，可直接貼入 GitHub issue）：

```markdown
## 遷移計畫 — github-repo-onboard 產出

參考倉庫：[owner/repo](https://github.com/owner/repo)
分析日期：2026-06-13
預估工期：2–4 週

### Phase 1：基礎設施準備（優先度：高，工期：2–3 天）

- [ ] 初始化 TypeScript 配置
  - `tsconfig.json` 參考 [owner/repo/tsconfig.json]
  - `tsconfig.app.json` 新增 paths alias
  - `src/` 目錄下檔案副檔名改為 `.tsx`

- [ ] 遷移包管理工具至 pnpm
  - 新增 `pnpm-workspace.yaml`
  - `package.json` 改寫為 workspace root 格式
  - 執行 `pnpm install --frozen-lockfile`
  - 刪除 `package-lock.json` 與 `node_modules/`

- [ ] 導入 Turbo 並配置 monorepo
  - `npm install -g turbo`
  - 新增 `turbo.json`（參考 [owner/repo/turbo.json]）
  - 配置 task dependency graph

### Phase 2：目錄重組（優先度：高，工期：3–5 天）

- [ ] 建立新目錄結構
  - `mkdir -p src/app src/lib src/components src/utils`
  - 保留原有 `src/assets`, `src/styles`

- [ ] 遷移頁面至 App Router
  - 備份 `src/pages/` 至 `src/pages.bak/`
  - 新建 `src/app/layout.tsx` (root layout)
  - 逐個遷移 `src/pages/*.tsx` → `src/app/*/page.tsx`
  - 測試路由正常性

- [ ] 遷移共用邏輯至 `src/lib/`
  - 移動 `src/utils/*.ts` → `src/lib/`
  - 更新所有 import 路徑

- [ ] 遷移元件至 `src/components/`
  - 組織方式參考 [owner/repo/src/components] 結構
  - 補充 `components/index.ts` barrel export

### Phase 3：框架升級（優先度：高，工期：1–2 週）

- [ ] 升級至 Next.js 14
  - `npm install next@latest`（或 `pnpm add next@latest`）
  - 執行 `next upgrade` 進行自動遷移
  - 核實 `next.config.js`（參考 [owner/repo/next.config.js]）

- [ ] API 路由遷移
  - 新建 `src/app/api/` 目錄
  - 遷移 `src/pages/api/*.ts` → `src/app/api/*/route.ts`
  - 更新路由定義（從 `export default handler` → `export { handler as GET, POST }`）

- [ ] 驗證靜態生成 vs 動態路由
  - 補充 `generateStaticParams()` 用於靜態路由
  - 檢查 Image 元件是否使用 `next/image`
  - 執行 `next build` 檢查構建輸出

### Phase 4：開發工具與測試（優先度：中，工期：3–5 天）

- [ ] 補充 ESLint + Prettier
  - 複製 `.eslintrc.json` 與 `.prettierrc` from [owner/repo]
  - `pnpm add -D eslint prettier eslint-plugin-react eslint-plugin-react-hooks`
  - 執行 `pnpm run lint` 與 `pnpm run format`

- [ ] 導入 Vitest 並遷移測試
  - `pnpm add -D vitest @vitest/ui @testing-library/react @testing-library/jest-dom`
  - 新建 `vitest.config.ts`（參考 [owner/repo/vitest.config.ts]）
  - 遷移 `src/**/*.test.jsx` → `src/**/*.test.tsx`
  - 執行 `pnpm run test`

- [ ] 建立 E2E 測試骨架
  - `pnpm add -D playwright`
  - 新建 `e2e/` 目錄與基礎測試案例

### Phase 5：文件與上線（優先度：中，工期：1–2 天）

- [ ] 更新 README.md
  - 新增「專案結構」章節，說明 `src/app`, `src/lib`, `src/components` 的目的
  - 補充開發環境 setup 指令（`pnpm install && pnpm run dev`）
  - 新增 build & deploy 指令

- [ ] 更新開發指南
  - `docs/DEVELOPMENT.md` 說明 `pnpm` 與 Turbo 使用方式
  - 補充常見命令（lint, test, build）

- [ ] 效能檢測與最佳化
  - 執行 `next build` 檢查 bundle size
  - 用 Lighthouse 檢查首頁效能
  - 補充關鍵最佳化（image optimization, dynamic import）

- [ ] 上線與驗收
  - 建立 staging 分支進行驗收
  - 執行完整的功能測試與迴歸測試
  - 合併至 main 並發佈新版本

---

## 統計摘要

| 類別 | 數量 | 工期 |
|------|-----|------|
| 總 Task | 28 | 2–4 週 |
| 高優先度 | 16 | 1–2 週 |
| 中優先度 | 8 | 3–5 天 |
| 低優先度 | 4 | 1–2 天 |
```

## 注意事項

### 已知限制

1. **私有倉庫存取**
   - Skill 預設通過 HTTPS 無認證存取；若參考倉庫是私有的，需提前配置 GitHub Token（`gh auth login` 或 `.gitconfig`）
   - 建議：優先提供開源倉庫的 URL；必要時由使用者確認 token 有效性

2. **大型倉庫分析**
   - 若參考倉庫超過 500 MB，淺層 clone (`--depth 1`) 可能仍較慢（取決於網速）
   - 建議：預先檢查倉庫大小；必要時提供更小的參考子目錄或特定 branch

3. **Monorepo 與複雜結構**
   - 多 workspace 或複雜的 monorepo 結構可能產出過多 task；建議分清「核心架構」vs「週邊工具」
   - 建議：指定要參考的特定子目錄或 workspace（例如「只看 `packages/frontend/`」）

4. **語言與框架的假設**
   - Skill 依靠檔案名與配置檔推測語言；若倉庫混合多個語言或使用冷門框架，可能偵測不精確
   - 建議：用文字補充說明「我只要遷移前端部分」或「忽略 Rust 後端」

5. **版本與相容性**
   - 參考倉庫的依賴版本未必相容於本地專案的 Node.js/Python 版本
   - 建議：遷移計畫預留「版本評估與調適」的時間；避免盲目複製版本號

### 使用建議

1. **從高層開始** — 先分析目錄組織與技術棧選擇，再深入文件級遷移；不要試圖一次完成所有 phase

2. **分階段執行** — Task list 通常分為 3–5 個 phase；每個 phase 建立一個 Git branch，逐個合併；便於 rollback 與同步協作

3. **驗證相容性** — 遷移後務必跑完整測試套件、CI/CD pipeline，確保沒有迴歸

4. **保留備份** — 參考倉庫的主要檔案（package.json、tsconfig.json、.github/workflows）保留複本，方便後續差異對比與調整

5. **與參考倉庫同步** — 若參考倉庫活躍更新，定期檢查是否有重要變更（例如 React 大版本升級）；考慮建立監控 issue 追蹤上游動態

### 與其他 Skill 的協作

- **gstack-plan-eng-review** — 若需要架構審查，在 github-repo-onboard 產出計畫後，可邀請專家複審設計決策
- **gstack-ship** — 遷移完成後，使用此 skill 分階段上線與部署驗證
- **gstack-qa** — 遷移期間持續跑 QA，確保功能完整性與未知迴歸
- **gstack-investigate** — 若遷移期間碰到架構不相容問題，邀請專家診斷根本原因