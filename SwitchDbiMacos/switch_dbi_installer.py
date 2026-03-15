#!/usr/bin/env python3
"""Switch DBI 安装封装工具（macOS/Linux）。

功能：
- 支持 CLI 自动化模式
- 支持 GUI 图形界面模式（适合 VSCode 直接运行）
- 可选拖拽功能（需安装 `tkinterdnd2`）
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Iterable


SUPPORTED_EXTENSIONS = {".nsp", ".nsz", ".xci", ".xcz"}
PROJECT_DIR = Path(__file__).resolve().parent
CONFIG_FILE = PROJECT_DIR / "config.json"
DEFAULT_BACKEND_REL_PATH = Path("tools") / "dbi" / "dbibackend"
DEFAULT_CONFIG = {
    "backend_path": str(DEFAULT_BACKEND_REL_PATH),
    "python_path": sys.executable,
}


def load_config(config_file: Path = CONFIG_FILE) -> dict[str, str]:
    if not config_file.exists():
        try:
            config_file.write_text(json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
        return DEFAULT_CONFIG.copy()

    try:
        config = json.loads(config_file.read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            raise ValueError("配置格式错误，应为 JSON 对象")
    except Exception as exc:
        raise RuntimeError(f"读取配置失败：{exc}") from exc

    backend = config.get("backend_path", str(DEFAULT_BACKEND_REL_PATH))
    python_path = config.get("python_path", sys.executable)
    return {
        "backend_path": str(backend),
        "python_path": str(python_path),
    }

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD  # type: ignore

    HAS_DND = True
except Exception:
    DND_FILES = None
    TkinterDnD = None
    HAS_DND = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="通过 USB 使用 DBI backend 向 Switch 安装文件。"
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        help="CLI 模式下要安装的文件或目录。",
    )
    parser.add_argument(
        "--config",
        default=str(CONFIG_FILE),
        help="配置文件路径，默认：./config.json",
    )
    parser.add_argument(
        "--backend",
        default=None,
        help="dbibackend 脚本/可执行文件路径。可从 config.json 读取。",
    )
    parser.add_argument(
        "--python",
        default=None,
        help="用于运行 dbibackend 的 Python 解释器路径。可从 config.json 读取。",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="递归扫描目录中的文件。",
    )
    parser.add_argument(
        "--include-unsupported",
        action="store_true",
        help="同时包含非标准后缀文件并传给 dbibackend。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅打印解析结果和命令，不实际启动 dbibackend。",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="强制使用 GUI 模式。",
    )
    return parser.parse_args()


def resolve_command_path(command: str, base_dir: Path | None = None) -> Path:
    candidate = Path(command).expanduser()
    if candidate.exists():
        return candidate.resolve()

    if not candidate.is_absolute() and base_dir is not None:
        base_candidate = (base_dir / candidate).expanduser()
        if base_candidate.exists():
            return base_candidate.resolve()

    which_result = shutil.which(command)
    if which_result:
        return Path(which_result).resolve()

    raise FileNotFoundError(f"找不到命令或路径：{command}")


def iter_directory_files(path: Path, recursive: bool) -> Iterable[Path]:
    if recursive:
        yield from (p for p in path.rglob("*") if p.is_file())
        return
    yield from (p for p in path.iterdir() if p.is_file())


def _check_duplicate_basenames(files: list[Path]) -> None:
    # DBI backend 以文件名为键，同名文件会互相覆盖，因此提前阻止。
    seen_names: dict[str, Path] = {}
    duplicates: list[tuple[str, Path, Path]] = []
    for file_path in files:
        name = file_path.name
        if name in seen_names:
            duplicates.append((name, seen_names[name], file_path))
        else:
            seen_names[name] = file_path

    if duplicates:
        lines = ["检测到同名文件（DBI backend 会覆盖同名项）："]
        for name, old, new in duplicates:
            lines.append(f"  - {name}")
            lines.append(f"    1) {old}")
            lines.append(f"    2) {new}")
        lines.append("请先重命名冲突文件，或分批安装。")
        raise ValueError("\n".join(lines))


def collect_files_from_inputs(
    raw_inputs: list[str],
    recursive: bool,
    include_unsupported: bool,
) -> list[Path]:
    files: list[Path] = []
    for raw in raw_inputs:
        path = Path(raw).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"输入路径不存在：{path}")
        if path.is_file():
            files.append(path.resolve())
            continue

        for file_path in iter_directory_files(path.resolve(), recursive):
            files.append(file_path.resolve())

    return normalize_file_list(files, include_unsupported=include_unsupported)


def normalize_file_list(files: list[Path], include_unsupported: bool) -> list[Path]:
    cleaned: list[Path] = []
    seen: set[Path] = set()
    for path in files:
        p = path.expanduser().resolve()
        if not p.exists() or not p.is_file():
            continue
        if not include_unsupported and p.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        if p in seen:
            continue
        cleaned.append(p)
        seen.add(p)

    cleaned = sorted(cleaned, key=lambda p: str(p).lower())
    _check_duplicate_basenames(cleaned)
    return cleaned


def check_python_deps(python_exec: Path) -> None:
    check_code = (
        "import tkinter; import usb.core; "
        "print('python dependencies ok: tkinter + pyusb')"
    )
    cmd = [str(python_exec), "-c", check_code]
    try:
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        message = [
            "当前 Python 环境缺少 dbibackend 所需依赖。",
            "请先安装：",
            "  python3 -m pip install pyusb",
            "",
            "如果缺少 tkinter，请使用带 Tk 支持的 Python 发行版。",
            "",
            "原始错误：",
            exc.stderr.strip() or exc.stdout.strip() or "(无错误输出)",
        ]
        raise RuntimeError("\n".join(message)) from exc


def build_backend_command(
    python_exec: Path, backend_path: Path, files: list[Path]
) -> list[str]:
    return [str(python_exec), str(backend_path), *[str(p) for p in files]]


def run_backend_command(
    cmd: list[str],
    output_cb: Callable[[str], None] | None = None,
) -> int:
    if output_cb is None:
        return subprocess.run(cmd).returncode

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    assert process.stdout is not None
    for line in process.stdout:
        output_cb(line.rstrip("\n"))
    process.wait()
    return process.returncode


class DBIInstallerGUI:
    def __init__(self) -> None:
        self.root = TkinterDnD.Tk() if HAS_DND else tk.Tk()
        self.root.title("Switch DBI USB 安装器")
        self.root.geometry("900x650")
        self.root.minsize(760, 520)

        config = load_config(CONFIG_FILE)
        self.backend_var = tk.StringVar(value=str(config.get("backend_path", str(DEFAULT_BACKEND_REL_PATH))))
        self.python_var = tk.StringVar(value=str(config.get("python_path", sys.executable)))
        self.recursive_var = tk.BooleanVar(value=True)
        self.include_unsupported_var = tk.BooleanVar(value=False)
        self.dry_run_var = tk.BooleanVar(value=False)

        self.selected_files: list[Path] = []
        self.install_in_progress = False

        self._build_ui()
        self._log("程序已就绪。")
        if not HAS_DND:
            self._log("拖拽功能未启用。可选安装：pip install tkinterdnd2")

    def _build_ui(self) -> None:
        container = ttk.Frame(self.root, padding=10)
        container.pack(fill=tk.BOTH, expand=True)

        path_frame = ttk.LabelFrame(container, text="运行环境")
        path_frame.pack(fill=tk.X)

        ttk.Label(path_frame, text="DBI backend:").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        backend_entry = ttk.Entry(path_frame, textvariable=self.backend_var)
        backend_entry.grid(row=0, column=1, sticky="ew", padx=6, pady=6)
        ttk.Button(path_frame, text="浏览...", command=self._pick_backend).grid(
            row=0, column=2, sticky="e", padx=6, pady=6
        )

        ttk.Label(path_frame, text="Python:").grid(row=1, column=0, sticky="w", padx=6, pady=6)
        python_entry = ttk.Entry(path_frame, textvariable=self.python_var)
        python_entry.grid(row=1, column=1, sticky="ew", padx=6, pady=6)
        ttk.Button(path_frame, text="浏览...", command=self._pick_python).grid(
            row=1, column=2, sticky="e", padx=6, pady=6
        )

        path_frame.columnconfigure(1, weight=1)

        select_frame = ttk.LabelFrame(container, text="文件选择")
        select_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        drop_text = "将文件/文件夹拖拽到此处" if HAS_DND else "请使用下方按钮选择文件/文件夹"
        self.drop_label = ttk.Label(select_frame, text=drop_text, relief=tk.GROOVE, anchor="center")
        self.drop_label.pack(fill=tk.X, padx=8, pady=8, ipady=10)

        if HAS_DND:
            self.drop_label.drop_target_register(DND_FILES)
            self.drop_label.dnd_bind("<<Drop>>", self._on_drop_files)

        list_frame = ttk.Frame(select_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.listbox = tk.Listbox(list_frame, selectmode=tk.EXTENDED)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        action_frame = ttk.Frame(select_frame)
        action_frame.pack(fill=tk.X, padx=8, pady=(0, 8))
        ttk.Button(action_frame, text="添加文件", command=self._add_files).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(action_frame, text="添加文件夹", command=self._add_folder).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(action_frame, text="移除选中", command=self._remove_selected).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(action_frame, text="清空列表", command=self._clear_files).pack(side=tk.LEFT)

        options_frame = ttk.LabelFrame(container, text="选项")
        options_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Checkbutton(options_frame, text="递归扫描文件夹", variable=self.recursive_var).pack(
            side=tk.LEFT, padx=8, pady=8
        )
        ttk.Checkbutton(
            options_frame, text="包含非标准后缀文件", variable=self.include_unsupported_var
        ).pack(side=tk.LEFT, padx=8, pady=8)
        ttk.Checkbutton(options_frame, text="仅预览（Dry Run）", variable=self.dry_run_var).pack(
            side=tk.LEFT, padx=8, pady=8
        )

        bottom_frame = ttk.Frame(container)
        bottom_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        button_row = ttk.Frame(bottom_frame)
        button_row.pack(fill=tk.X, pady=(0, 6))

        self.install_button = ttk.Button(
            button_row, text="开始传输到 Switch", command=self._install
        )
        self.install_button.pack(side=tk.LEFT)

        self.exit_button = ttk.Button(button_row, text="结束程序", command=self.root.destroy)
        self.exit_button.pack(side=tk.LEFT, padx=(8, 0))

        self.log_text = tk.Text(bottom_frame, height=11, wrap=tk.WORD, state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def _log(self, message: str) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _pick_backend(self) -> None:
        path = filedialog.askopenfilename(title="选择 dbibackend")
        if path:
            self.backend_var.set(path)

    def _pick_python(self) -> None:
        path = filedialog.askopenfilename(title="选择 Python 解释器")
        if path:
            self.python_var.set(path)

    def _add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="选择游戏文件",
            filetypes=[
                ("Switch 文件", "*.nsp *.nsz *.xci *.xcz"),
                ("全部文件", "*.*"),
            ],
        )
        if paths:
            self._append_paths([Path(p) for p in paths])

    def _add_folder(self) -> None:
        folder = filedialog.askdirectory(title="选择文件夹")
        if not folder:
            return
        folder_path = Path(folder)
        files = list(iter_directory_files(folder_path, recursive=self.recursive_var.get()))
        self._append_paths(files)

    def _append_paths(self, paths: list[Path]) -> None:
        existing = set(self.selected_files)
        added = 0
        for path in paths:
            p = path.expanduser().resolve()
            if not p.exists():
                continue
            if p.is_dir():
                files = list(iter_directory_files(p, recursive=self.recursive_var.get()))
                for f in files:
                    fp = f.resolve()
                    if fp not in existing:
                        self.selected_files.append(fp)
                        existing.add(fp)
                        added += 1
                continue
            if p.is_file() and p not in existing:
                self.selected_files.append(p)
                existing.add(p)
                added += 1

        self._refresh_list()
        self._log(f"已添加 {added} 个文件，当前共 {len(self.selected_files)} 个。")

    def _remove_selected(self) -> None:
        indexes = set(self.listbox.curselection())
        if not indexes:
            return
        self.selected_files = [p for i, p in enumerate(self.selected_files) if i not in indexes]
        self._refresh_list()
        self._log(f"已移除 {len(indexes)} 个文件。")

    def _clear_files(self) -> None:
        self.selected_files.clear()
        self._refresh_list()
        self._log("已清空文件列表。")

    def _refresh_list(self) -> None:
        self.listbox.delete(0, tk.END)
        for file_path in sorted(self.selected_files, key=lambda p: str(p).lower()):
            self.listbox.insert(tk.END, str(file_path))

    def _on_drop_files(self, event: tk.Event) -> None:  # type: ignore[override]
        raw = event.data
        paths = [Path(p) for p in self.root.tk.splitlist(raw)]
        self._append_paths(paths)

    def _install(self) -> None:
        if self.install_in_progress:
            return
        if not self.selected_files:
            messagebox.showerror("未选择文件", "请先添加至少一个文件。")
            return

        include_unsupported = self.include_unsupported_var.get()
        try:
            backend_path = resolve_command_path(self.backend_var.get().strip(), base_dir=PROJECT_DIR)
            python_exec = resolve_command_path(self.python_var.get().strip())
            check_python_deps(python_exec)
            final_files = normalize_file_list(self.selected_files, include_unsupported=include_unsupported)
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            messagebox.showerror("校验失败", str(exc))
            return

        if not final_files:
            messagebox.showerror(
                "无可安装文件",
                "过滤后没有可安装文件。\n"
                "支持后缀：" + ", ".join(sorted(SUPPORTED_EXTENSIONS)),
            )
            return

        cmd = build_backend_command(python_exec, backend_path, final_files)
        file_count = len(final_files)
        preview = "\n".join(str(p) for p in final_files[:8])
        if file_count > 8:
            preview += f"\n...（还有 {file_count - 8} 个）"
        ok = messagebox.askyesno(
            "确认传输",
            "已准备通过 DBI 向 Switch 传输文件。\n\n"
            "请在 Switch 上选择：DBI -> Install title from DBIbackend\n\n"
            f"文件数量：{file_count}\n\n"
            f"{preview}\n\n"
            "是否立即开始？",
        )
        if not ok:
            return

        if self.dry_run_var.get():
            self._log("Dry Run 命令：")
            self._log(" ".join(f'"{part}"' if " " in part else part for part in cmd))
            return

        self.install_in_progress = True
        self.install_button.configure(state=tk.DISABLED)
        self._log("正在启动 dbibackend...")
        self._log("Switch 操作：DBI -> Install title from DBIbackend")

        def worker() -> None:
            # 在后台线程执行，避免阻塞界面。
            def output(line: str) -> None:
                self.root.after(0, lambda: self._log(line))

            return_code = run_backend_command(cmd, output_cb=output)
            self.root.after(0, lambda: self._on_install_finished(return_code))

        threading.Thread(target=worker, daemon=True).start()

    def _on_install_finished(self, return_code: int) -> None:
        self.install_in_progress = False
        self.install_button.configure(state=tk.NORMAL)
        if return_code == 0:
            self._log("传输完成。")
            messagebox.showinfo("完成", "传输完成。")
        else:
            self._log(f"传输失败，退出码：{return_code}")
            messagebox.showerror("失败", f"dbibackend 退出码：{return_code}")

    def run(self) -> None:
        self.root.mainloop()


def run_cli(args: argparse.Namespace) -> int:
    if not args.inputs:
        print("[错误] CLI 模式下未提供输入文件或目录。", file=sys.stderr)
        print("提示：不带参数运行可直接打开 GUI。", file=sys.stderr)
        return 2

    config = load_config(Path(args.config))
    backend_value = args.backend or config.get("backend_path", str(DEFAULT_BACKEND_REL_PATH))
    python_value = args.python or config.get("python_path", sys.executable)

    try:
        backend_path = resolve_command_path(backend_value, base_dir=PROJECT_DIR)
        python_exec = resolve_command_path(python_value)
        files = collect_files_from_inputs(args.inputs, args.recursive, args.include_unsupported)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 2

    if not files:
        print("[错误] 没有找到可安装文件。", file=sys.stderr)
        print(
            "支持后缀："
            + ", ".join(sorted(SUPPORTED_EXTENSIONS)),
            file=sys.stderr,
        )
        return 2

    try:
        check_python_deps(python_exec)
    except RuntimeError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 3

    cmd = build_backend_command(python_exec, backend_path, files)

    print("即将使用 DBI backend 处理以下文件：")
    for i, file_path in enumerate(files, start=1):
        print(f"  {i}. {file_path}")
    print("\n执行命令：")
    print("  " + " ".join(f'"{part}"' if " " in part else part for part in cmd))

    if args.dry_run:
        print("\nDry Run 模式，未实际执行。")
        return 0

    print(
        "\nSwitch 端操作：\n"
        "  1) 打开 DBI\n"
        "  2) 选择 'Install title from DBIbackend' (Y)\n"
        "  3) 保持 USB 连接直到安装完成\n"
    )
    return run_backend_command(cmd)


def main() -> int:
    args = parse_args()
    if args.gui or len(sys.argv) == 1:
        app = DBIInstallerGUI()
        app.run()
        return 0
    return run_cli(args)


if __name__ == "__main__":
    raise SystemExit(main())
