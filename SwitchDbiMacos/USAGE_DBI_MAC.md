# Switch DBI USB 安装器（macOS）

本项目是一个 macOS/Linux 上的 Switch DBI 安装器 GUI/CLI 封装，便于通过 USB 传输 `.nsp/.nsz/.xci/.xcz` 文件给 Switch 的 DBI backend。

## 1. 准备

1. 克隆仓库并进入目录：

```bash
git clone <your-repo-url>
cd SwitchDbiMacos
```

2. 安装 Python 依赖：

```bash
python3 -m pip install pyusb
```

> 如果你想启用拖拽功能，安装：

```bash
python3 -m pip install tkinterdnd2
```

3. 检查 `config.json`（项目根目录）：

```json
{
  "backend_path": "./tools/dbi/dbibackend",
  "python_path": "python3"
}
```

- `backend_path`：指向 `dbibackend` 脚本/可执行文件，相对路径或绝对路径都可。
- `python_path`：运行 `dbibackend` 的 Python 可执行路径。

## 2. GUI 模式（推荐）

直接运行：

```bash
python3 switch_dbi_installer.py
```

在界面中：
- `DBI backend` 填写 `dbibackend` 路径（默认从 `config.json` 读）
- `Python` 填写 Python 可执行路径（默认从 `config.json` 读）
- 添加文件或文件夹
- 可选：启用“递归扫描”、“包含非标准后缀”、“Dry Run”
- 点击“开始传输到 Switch”后，在 Switch 端选择 `DBI -> Install title from DBIbackend`。

## 3. CLI 模式

```bash
python3 switch_dbi_installer.py <file-or-folder> [--config config.json] [--backend path] [--python path] [--recursive] [--include-unsupported] [--dry-run]
```

示例：

```bash
python3 switch_dbi_installer.py ~/Downloads/game.nsp
```

使用自定义配置：

```bash
python3 switch_dbi_installer.py ~/Downloads/switch_games --recursive --dry-run --config ./config.json
```

## 4. 重要说明

- 默认仅支持后缀：`.nsp`, `.nsz`, `.xci`, `.xcz`。
- CLI 和 GUI 都会检测“同名文件”，避免 DBI 覆盖问题。
- 仅安装你合法拥有的游戏文件。

---

## 5. 常见问题

- 找不到 `dbibackend`：请检查 `backend_path` 是否正确，或使用 `--backend` 覆盖。
- 找不到 Python：请检查 `python_path` 是否可执行，或使用 `--python` 覆盖。
- 无可安装文件：请确认文件存在且后缀合法，或启用 `--include-unsupported`。
