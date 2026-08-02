# Code-review Git hooks

`pre-commit` 與 `pre-push` 共用 `lib-review.sh`。它們只會在 Claude 明確輸出
最後一行 `VERDICT: FAIL` 時阻擋；CLI 不存在、隔離環境建立失敗、timeout、CLI error
或沒有明確 verdict 都維持既有 fail-open 行為，而且不會寫入 PASS cache。

## 目前已啟用的保護與成本控制

- pre-commit 的 timeout 下限是 300 秒；pre-push 每個 ref 的下限是 900 秒。
  `REVIEW_TIMEOUT` 只能放寬，較小值會被提升並印出警告。
- 審查在只含 `base_tree` 與 `target_tree` 的暫時 Git repository 中進行；Claude
  只能使用 `refs/review/base`、`refs/review/target` 與該暫時目錄下的讀取工具。
- 只有完整相同的 repo、base/target tree、working-tree fingerprint、prompt、policy、
  CLI version 與 effort 所得的明確 PASS 可在 TTL 內重用。預設位置是
  `~/.githooks/review-cache/`、TTL 為 7 天；任何讀取／解析問題一律當作 cache miss。
- 預設固定 `xhigh`。`medium` / `high` 僅能以
  `REVIEW_EFFORT=medium|high REVIEW_ALLOW_LOWER_EFFORT=1` 明確手動啟用。
  自動 effort 分級暫不啟用，直到 miss budget、最低樣本量與信賴上界門檻被明確定義，
  並完成 xhigh 影子稽核校準。

常用逃生口：`SKIP_REVIEW=1 git commit ...` 或 Git 原生 `--no-verify`。

## 測試

```bash
hooks/tests/test-lib-review.sh
```

測試會使用本地 stub，不呼叫 Claude，覆蓋 timeout 下限、隔離工作目錄、PASS cache、
untracked 變更 cache miss 與 initial commit 的 empty-tree 路徑。
