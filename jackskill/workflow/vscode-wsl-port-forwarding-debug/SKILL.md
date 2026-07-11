---
name: vscode-wsl-port-forwarding-debug
description: |
  診斷 VS Code Remote WSL 環境中 PORTS 面板為何只顯示部分 forwarded ports，其他正在 listening 的服務卻未出現。涵蓋 VS Code remote.WSL.localhostForwarding 設定、code-server autoForward 行為、wsl.conf 網路設定、netsh portproxy 規則交互等根因排查。
  
  TRIGGER when:
  - 使用者說「VSCode 的 port 顯示太少」
  - 「WSL forward 不出來」
  - 「VSCode PORTS 沒看到我的服務」
  - 「remote 端 port 看不到」
version: 1.0.0
category: workflow
tags: [wsl, vscode, port-forwarding, networking, debugging, remote-dev, portproxy]
languages: all
when_to_use: |
  當開發者在 WSL2 環境中啟用 VS Code Remote，PORTS 面板只顯示部分正在 listen 的服務。其他服務雖然在 WSL 內確實已啟動（netstat/ss 可見），但無法在 VS Code PORTS 面板上出現或轉發到 Windows host。

---

## Overview

VS Code 在 WSL Remote 環境下的 port 轉發機制涉及多層設定，常見的「PORTS 面板只顯示部分服務」問題往往源於以下環節之一：

1. **VS Code 自身的 `remote.WSL.localhostForwarding` 設定** — 控制是否啟用自動探測與轉發
2. **code-server 的 `autoForward` 行為** — 決定哪些 port 會被自動納入清單
3. **WSL2 內的網路配置** — `wsl.conf` 的 `[boot]` 和 `[network]` 段影響 localhost binding 的可見性
4. **Windows 端的 `netsh portproxy` 規則** — WSL localhost 與 Windows 之間的橋接設定
5. **防火牆與服務綁定位址** — 應用程式只綁定 `127.0.0.1` 而非 `0.0.0.0` 會影響跨層可見性

此 skill 透過系統化的診斷步驟，快速定位根因並應用相應的修復。

## 何時使用

- **立即症狀**：開啟 VS Code Remote（WSL），PORTS 面板在啟動應用後無法看到預期的 port
- **部分可見**：某些 port（如 3000、8080）自動出現，但其他服務（如 5432、8001）即使在 listening 也未出現
- **手動轉發無效**：嘗試在 PORTS 面板手動輸入 port 卻報告「無法連線」或「不可到達」
- **新 WSL 實例**：剛安裝 WSL2 或重建 distro，環境配置未完全同步到 VS Code Remote 預期

## 執行步驟

### 第 1 步：確認 WSL2 與 VS Code 版本相容性

在 WSL 終端執行：
```bash
wsl --version
```
確保 WSL2 版本 ≥ 2.0（支援 `netsh portproxy` 橋接）。

在 Windows PowerShell 檢查 VS Code Remote WSL 擴充：
```powershell
code --version
```
確保 VS Code ≥ 1.85（autoForward 已成熟）。

### 第 2 步：檢查 VS Code 設定

在 VS Code 中開啟 Remote WSL，按 `Ctrl+,` 開啟設定搜尋 `remote.WSL.localhostForwarding`，確認設定值：

**推薦配置**（`settings.json` 或 VS Code UI）：
```json
{
  "remote.WSL.localhostForwarding": true,
  "remote.autoForwardPorts": true
}
```

若設為 `false`，所有 port 轉發完全由手動控制。改為 `true` 後重啟 Remote 連線。

### 第 3 步：驗證 WSL 內服務確實在 listening

在 WSL 終端執行：
```bash
ss -tlnp | grep LISTEN
```
或：
```bash
netstat -tlnp | grep LISTEN
```

**查找你的應用**（例如 port 8001）：
```bash
ss -tlnp | grep :8001
```

若看到類似：
```
LISTEN    0      128        127.0.0.1:8001            0.0.0.0:*      users:(("python",pid=1234,fd=3))
```

說明服務已在 WSL 內的 `127.0.0.1:8001` listen。若顯示 `0.0.0.0:8001`，則更容易被 VS Code 自動發現。

### 第 4 步：檢查 wsl.conf 網路設定

編輯 WSL distro 的 `wsl.conf`（通常位於 `\\wsl.localhost\<distro>\etc\wsl.conf`）：

```ini
[boot]
systemd=true

[network]
generateHostsFile = true
generateResolvConf = true
hostname = wsl-dev
```

確保 `[network]` 段不會禁用 localhost 解析。若有 `localhost = false` 或類似設定應移除。

編輯後在 Windows PowerShell 重啟 distro：
```powershell
wsl --terminate <distro-name>
```

### 第 5 步：驗證 Windows 端 netsh portproxy 規則

在 Windows PowerShell（管理員）執行：
```powershell
netsh interface portproxy show all
```

應看到類似：
```
IPv4 to IPv4 Listeners:

连接名                 监听 ipv4 地址        监听端口   连接 ipv4 地址      连接端口
------------------ ----------------------- ----------- ----------------------- -----------
*                      127.0.0.1               8001      172.X.X.X                8001
```

若沒有任何規則，表示 VS Code 尚未自動建立 portproxy。手動建立（以 port 8001 為例）：

```powershell
netsh interface portproxy add v4tov4 listenport=8001 listenaddress=127.0.0.1 connectport=8001 connectaddress=<wsl-ip>
```

其中 `<wsl-ip>` 可透過在 WSL 終端執行 `hostname -I` 取得（例如 `172.31.0.1`）。

### 第 6 步：重新整理 VS Code 的 port autoForward 快取

在 VS Code Remote 終端執行：
```bash
rm -rf ~/.vscode-server/data/logs/*
```

然後在 VS Code 中：
1. 按 `Ctrl+Shift+P`
2. 輸入 `Remote-Containers: Rebuild Container` 或 `Remote-WSL: Reopen in WSL`
3. 等待 Remote 重新連線

### 第 7 步：驗證 VS Code PORTS 面板

重新連線後，開啟 VS Code PORTS 面板（View → Ports），應見到之前缺失的 port。若仍未出現：

在 PORTS 面板上方「Forward a Port」輸入框手動輸入 port 號，click「Forward」。若成功，代表網路層沒問題，只是 autoForward 探測邏輯未捕捉。

## 注意事項

### 已知限制

1. **WSL IP 變動**：WSL2 重啟後可能獲得新 IP，已建立的 `netsh portproxy` 規則指向舊 IP 會失效。VS Code 通常會自動更新，但若 WSL 長期運行再手動建立 portproxy，需定期檢查。

2. **防火牆阻擋**：Windows Defender Firewall 若未允許 localhost 迴路轉發，即使 portproxy 規則正確也無法工作。一般 localhost 轉發不需防火牆規則，但若自訂防火牆應確保 loopback 不被阻擋。

3. **code-server 與 VS Code Remote 的差異**：若同時運行 `code-server`（容器或遠端環境中的 Web IDE），其 autoForward 邏輯與 VS Code Remote WSL 擴充獨立，兩者設定不會互相影響。

4. **多 distro 場景**：若同時開啟多個 WSL distro，VS Code 通常只對當前活躍的 distro 管理 portproxy；切換 distro 時需重新建立規則。

5. **靜態 port 綁定**：應用只綁定 `127.0.0.1` 時，portproxy 從 WSL IP (e.g., `172.31.0.1`) 代理會失敗。應用應綁定 `0.0.0.0` 或應用層在多個地址上 listen。

### 快速檢查清單

遇到問題時依序檢查：

- [ ] `remote.WSL.localhostForwarding` 已啟用
- [ ] WSL 內 `ss -tlnp | grep :<port>` 確認服務在 listening
- [ ] `netsh interface portproxy show all` 在 Windows 端看到對應規則
- [ ] WSL IP 未變動（若變動，netsh portproxy 規則需更新）
- [ ] VS Code Remote 已完全重新連線（不只是重啟終端）
- [ ] 應用綁定位址包含 `0.0.0.0` 或至少 WSL 的 IP

### 與其他 skill 的界線

- **dev-port-conflict-fix**：排查本機 port 衝突（同一 port 多程序競爭）；本 skill 專注 WSL ↔ Windows 可見性層
- **1-service-watchdog-launchd** 與 systemd agent：監控服務存活；本 skill 排查已存活但看不見的服務