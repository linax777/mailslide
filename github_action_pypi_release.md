# GitHub Action PyPI Release

## TestPyPI RC 驗證（uv tool）

當 tag 為 `v*rc*`（例如 `v0.3.10rc3`）時，workflow 會發佈到 TestPyPI。

因為 `mailslide` 同時存在於 PyPI / TestPyPI，`uv` 預設的 index 防護策略可能只看第一個找到該套件的 index，造成找不到 RC 版本。建議固定使用下面參數：

- `--default-index https://test.pypi.org/simple`
- `--index https://pypi.org/simple`
- `--index-strategy unsafe-best-match`
- `--prerelease allow`

### PowerShell（首次安裝）

```powershell
uv tool install "mailslide==0.3.10rc3" --default-index "https://test.pypi.org/simple" --index "https://pypi.org/simple" --index-strategy unsafe-best-match --prerelease allow
```

### PowerShell（已安裝後升級）

```powershell
uv tool upgrade "mailslide==0.3.10rc3" --default-index "https://test.pypi.org/simple" --index "https://pypi.org/simple" --index-strategy unsafe-best-match --prerelease allow --reinstall
```

### PowerShell 多行寫法（注意是反引號，不是 `\`）

```powershell
uv tool upgrade "mailslide==0.3.10rc3" `
  --default-index "https://test.pypi.org/simple" `
  --index "https://pypi.org/simple" `
  --index-strategy unsafe-best-match `
  --prerelease allow `
  --reinstall
```

### 檢查目前工具版本

```powershell
uv tool list --show-version-specifiers
```

## 常見問題

- `no version of mailslide==x.y.zrcN`
  - 多半是 index 策略導致，請確認有帶 `--index-strategy unsafe-best-match`。
- 剛發佈完成但抓不到
  - 先等 1-5 分鐘索引同步，或加上 `--no-cache` 重試。
- 要切回正式版
  - 改用 PyPI 來源與 stable 版本號，例如 `mailslide==0.3.10`。
