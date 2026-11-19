# Testnet Wallet Tools

## 水龍頭與測試幣查詢

新增 `faucet_catalog.py` 與 `faucet_catalog.json`，可按網路、幣種及提供商篩選公開入口，並列出申領條件。Circle 網路與 USDC/EURC/cirBTC 的配對是候選項，**不代表每個配對均有供應**。此工具不會自動提交領幣請求，也不會繞過 CAPTCHA 或配額。

```bash
.venv/bin/python faucet_catalog.py --network sepolia
.venv/bin/python faucet_catalog.py --token HYPE
.venv/bin/python faucet_catalog.py --provider Circle --token USDC --json
.venv/bin/python faucet_catalog.py --network 'Base Sepolia' --address 0x0000000000000000000000000000000000000001
```

## 水龍頭索引

`faucets.json` 列出 Circle 公開 Faucet 網路與常見提供商；`faucets.py` 可依鏈名稱查詢。此功能只列出官方入口，不自動提交申領、處理 CAPTCHA 或規避頻率限制。

```bash
.venv/bin/python faucets.py
.venv/bin/python faucets.py --network sepolia
.venv/bin/python faucets.py --json
```

Circle 提供 USDC、EURC、cirBTC，但每條鏈實際支援資產不同；以官方網站即時選項為準。


使用一組 **僅供測試的 BIP-39 助記詞**，依 `m/44'/60'/0'/0/i` 衍生 EVM 地址，查詢各測試鏈原生幣餘額，並可選擇將**已合法取得**的測試幣轉到地址 #0。

不提供多地址自動領取水龍頭、繞過配額或 CAPTCHA 的功能。水龍頭需依各供應商規則自行領取。

## 餘額、收據與 ERC-20 歸集

`audit.py` 可讀取所有已設定 RPC 的鏈，逐一檢查 HD 地址的原生幣與指定 ERC-20 餘額，也可驗證交易收據。未設定 RPC 的鏈不會被檢查；沒有交易收據不能宣稱已成功領幣。ERC-20 合約地址必須先從官方來源核對。

```bash
.venv/bin/python audit.py --count 10 --network sepolia --output reports/sepolia.audit.json
.venv/bin/python audit.py --network sepolia --tx 0xYOUR_TRANSACTION_HASH
.venv/bin/python tokens.py balances --network sepolia --contract 0xVERIFIED_ERC20_CONTRACT --count 10
.venv/bin/python tokens.py sweep --network sepolia --contract 0xVERIFIED_ERC20_CONTRACT --count 10
# 審核 dry-run、確認來源與合約後才選擇廣播：
.venv/bin/python tokens.py sweep --network sepolia --contract 0xVERIFIED_ERC20_CONTRACT --count 10 --execute --confirm TRANSFER-TESTNET-TOKENS
```

交易廣播不等於確認成功；請用鏈上交易收據與餘額再驗證。ERC-20 歸集需要來源地址有原生 Gas Token。腳本不提供繞過 faucet 限額的批量領幣。

## 使用

```bash
cd /home/devspace/projects/testnet-wallet-tools
.venv/bin/pip install -r requirements.txt
.venv/bin/python wallet.py networks
.venv/bin/python wallet.py addresses --count 10
export RPC_SEPOLIA='https://YOUR-TRUSTED-SEPOLIA-RPC'
.venv/bin/python wallet.py balances --network sepolia --count 10
.venv/bin/python wallet.py sweep --network sepolia --count 10
# 檢查 dry-run 後才選擇廣播
.venv/bin/python wallet.py sweep --network sepolia --count 10 --execute --confirm TRANSFER-TESTNET-FUNDS
```

其他鏈請在 `networks.json` 設定已查證的 chain ID，並提供對應的 `RPC_...` 環境變數。Arc、Codex 等網路的 ID 留空以避免誤轉；需先核對官方文件。各鏈**互相獨立**，sweep 只在同一條鏈上轉帳，不是跨鏈橋。

**注意**：轉帳使用一般 EVM 原生幣 21000 gas 的估計；特殊鏈、帳戶與動態費率可能不適用。執行前請自行確認 Gas 與目的地；交易發出後不可撤銷。此工具不適用於主網資金或 ERC-20 代幣。

助記詞位於 `secrets/mnemonic.txt`，不會由程式輸出或提交 Git；VM 是連網環境，請勿將這組助記詞用於主網資產。執行 `.venv/bin/python -m unittest -v` 可執行離線測試。
