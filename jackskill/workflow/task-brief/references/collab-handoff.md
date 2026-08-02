# Collab 交棒規則

## 先判斷意圖

- `review`：已有 diff、程式、文件、log、測試或 trace，目標是查錯、驗證或判斷能否接受。
- `design`：尚未定案，要產生、比較或選擇方案；附件可能只是背景材料。
- `implementation`：方向已定，要直接產出或修改。

## 再選執行器

| 條件 | 執行器 |
|---|---|
| 明確、可逆、易驗證，第二模型增益有限 | `normal_agent` |
| 已有產物，需要獨立 evidence 查核 | `collab_review` |
| 多個合理方案、重大 trade-off、高返工成本或明確要求雙腦 | `collab_design` |

使用者明確指定 `collab-design` 或 `collab-review` 時直接交棒；只缺會改變方向的關鍵事實才追問。

## 分開 Risk 與 Collaboration

- Risk tier 決定最低安全路徑：Low→Fast、Medium→Reviewed、High→Council、Critical→Guarded。
- Collaboration mode 表達使用者想要的強度：`auto`、`reviewed`、`council`。
- 最終路徑取兩者較重者；Collaboration 不得降低 Risk floor。
- 使用者要求兩個獨立方案時，保持真實 risk tier，使用 `council` 並保存理由，不要把任務假標為 High。

## 交棒命令

方案協作：

```bash
collab design --brief BRIEF.json \
  --collaboration-mode council \
  --collaboration-reason "user requested independent alternative proposals"
```

既有產物查核：

```bash
collab review --evidence /absolute/path/to/evidence \
  --prompt "要查證的具體問題"
```

一般 Agent 不建立 collab run。高風險 implementation 可在執行前用 collab-design 建立契約，完成後再用 collab-review 查核真實 evidence。
