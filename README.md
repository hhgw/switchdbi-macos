# SwitchDbiMacos

一个面向 macOS（兼容 Linux）的 Switch DBI USB 传输项目。  
项目起因是：在 macOS 上需要一个更顺手的工具，把 `.nsp/.nsz/.xci/.xcz` 等文件通过 `DBI backend` 方式传输到 Switch（Switch 端开启 DBI 传输）。

本项目核心是 `switch_dbi_installer.py`，但整体目标是提供一套“开箱可用”的目录结构、配置和使用流程，而不是只给一个脚本。
本项目完全由codex生成，本人只通过prompt提出修改完善需求。

---

## 1. 项目是做什么的

这个项目用于把本地安装包通过 USB 发送给 Switch 上的 DBI，减少手动命令和路径配置成本。

它提供：
- GUI 模式（默认）：适合日常点击操作
- CLI 模式：适合批处理或自动化
- 配置文件：统一管理 Python 与 `dbibackend` 路径
- 文件安全校验：过滤后缀、去重、同名冲突检测（避免 DBI backend 覆盖）
- 依赖检查：启动前检查 `pyusb` / `tkinter` 环境

默认支持后缀：
- `.nsp`
- `.nsz`
- `.xci`
- `.xcz`

---

## 2. 项目结构

```text
SwitchDbiMacos/
├── switch_dbi_installer.py   # 主程序（GUI + CLI）
├── config.json               # 路径配置
├── tools/
│   └── dbi/
│       └── dbibackend        # DBI backend
└── USAGE_DBI_MAC.md          # 额外使用说明
```

---

## 3. 从 clone 到可用（快速开始）

1. 克隆项目并进入目录

```bash
git clone <your-repo-url>
cd SwitchDbiMacos
```

2. 安装依赖

```bash
python3 -m pip install pyusb
```

如果你希望 GUI 支持拖拽文件，再安装：

```bash
python3 -m pip install tkinterdnd2
```

3. 检查配置文件 `config.json`

```json
{
  "backend_path": "./tools/dbi/dbibackend",
  "python_path": "/path/to/your/python"
}
```

4. 启动程序（GUI）

```bash
python3 switch_dbi_installer.py
```

5. 在 Switch 端进入 DBI 并选择：

`DBI -> Install title from DBIbackend`

---

## 4. 环境配置说明

系统与运行环境：
- 操作系统：`macOS`（主要目标）或 `Linux`
- Python：建议 `3.9+`
- 必需依赖：`pyusb`
- GUI 依赖：`tkinter`（通常系统 Python 已带）
- 可选依赖：`tkinterdnd2`（仅用于拖拽体验）

`config.json` 字段说明：
- `backend_path`：`dbibackend` 路径，支持相对路径与绝对路径
- `python_path`：用于运行 `dbibackend` 的 Python 解释器路径

说明：
- GUI/CLI 默认都读取 `config.json`
- CLI 可以通过参数临时覆盖（`--backend`、`--python`）

---

## 5. 使用方式

### 5.1 GUI（推荐）

```bash
python3 switch_dbi_installer.py
```

操作步骤：
1. 确认 `DBI backend` 与 `Python` 路径
2. 添加文件或文件夹（支持按钮选择；安装 `tkinterdnd2` 后支持拖拽）
3. 按需勾选选项：
- 递归扫描文件夹
- 包含非标准后缀
- Dry Run（只预览命令，不执行）
4. 点击“开始传输到 Switch”
5. 按提示在 Switch 端执行 `Install title from DBIbackend`

### 5.2 CLI

基本格式：

```bash
python3 switch_dbi_installer.py <file_or_dir> [more_inputs...]
```

示例：

```bash
# 单文件
python3 switch_dbi_installer.py ~/Downloads/game.nsp

# 目录递归
python3 switch_dbi_installer.py ~/Downloads/switch_games --recursive

# 仅预览命令
python3 switch_dbi_installer.py ~/Downloads/switch_games --recursive --dry-run

# 临时覆盖配置路径
python3 switch_dbi_installer.py ~/Downloads/game.nsp \
  --backend ./tools/dbi/dbibackend \
  --python /usr/bin/python3
```

---

## 6. CLI 参数

- `inputs`：文件或目录（可多个）
- `--config`：配置文件路径，默认 `./config.json`
- `--backend`：指定 `dbibackend` 路径
- `--python`：指定 Python 解释器路径
- `--recursive`：递归扫描目录
- `--include-unsupported`：包含非标准后缀文件
- `--dry-run`：只打印命令，不执行传输
- `--gui`：强制启动 GUI

---

## 7. 常见问题

### 找不到 `dbibackend`

检查 `config.json` 的 `backend_path`，或 CLI 使用 `--backend` 指定。

### 缺少 `pyusb`

```bash
python3 -m pip install pyusb
```

并确认 `python_path` 与你安装依赖时用的是同一个 Python 环境。

### 没有可安装文件

默认只允许 `.nsp/.nsz/.xci/.xcz`。  
如需传其他后缀，使用 `--include-unsupported`。

### 同名文件冲突

`dbibackend` 按文件名处理，同名会覆盖。请先重命名或分批传输。

---

## 8. 注意事项

- 请仅传输你合法拥有和可使用的内容。
- 传输过程中请保持 USB 连接稳定。
