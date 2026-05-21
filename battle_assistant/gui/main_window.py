"""
战报助手 - 主界面
"""
import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

# 添加项目路径
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from battle_assistant.core.config import Config
from battle_assistant.core.adb_helper import ADBHelper
from battle_assistant.core.scroller import AutoScroller
from battle_assistant.core.importer import DataImporter
from battle_assistant.core.exporter import export_to_excel, export_to_excel_by_alliance


class BattleAssistantApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("战报助手 v1.0")
        self.root.geometry("600x500")
        self.root.resizable(False, False)

        # 初始化配置
        self.config = Config(str(ROOT / "config.json"))

        # 初始化核心模块
        self.adb = None
        self.scroller = None
        self.importer = DataImporter(str(ROOT / "data" / "heroes.db"))

        # 状态缓存（避免频繁更新 UI）
        self._last_adb_status = ""
        self._last_game_status = ""
        self._last_data_status = ""
        self._updating = False

        # 自动检测 ADB
        self._auto_detect_adb()

        # 创建界面
        self._create_widgets()

        # 启动状态更新（延迟 1 秒）
        self.root.after(1000, self._update_status)

    def _auto_detect_adb(self):
        """自动检测 ADB"""
        adb_path = self.config.auto_detect_adb()
        if adb_path:
            self.adb = ADBHelper(adb_path, self.config.get("serial"))
            self.scroller = AutoScroller(self.adb)

    def _create_widgets(self):
        """创建界面组件"""
        # 顶部状态栏
        self._create_status_bar()

        # 主选项卡
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 选项卡
        self._create_scroll_tab()
        self._create_import_tab()
        self._create_export_tab()
        self._create_settings_tab()

        # 底部日志
        self._create_log_area()

    def _create_status_bar(self):
        """创建状态栏"""
        frame = ttk.Frame(self.root)
        frame.pack(fill=tk.X, padx=10, pady=5)

        # ADB 状态
        self.adb_status = ttk.Label(frame, text="ADB: 未连接", foreground="red")
        self.adb_status.pack(side=tk.LEFT)

        # 游戏状态
        self.game_status = ttk.Label(frame, text="游戏: 未检测", foreground="gray")
        self.game_status.pack(side=tk.LEFT, padx=20)

        # 数据统计
        self.data_status = ttk.Label(frame, text="数据: 0 条战报")
        self.data_status.pack(side=tk.RIGHT)

    def _create_scroll_tab(self):
        """创建翻页选项卡"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="自动翻页")

        # 翻页设置
        settings_frame = ttk.LabelFrame(tab, text="翻页设置", padding=10)
        settings_frame.pack(fill=tk.X, padx=10, pady=5)

        # 翻页次数
        ttk.Label(settings_frame, text="翻页次数:").grid(row=0, column=0, sticky=tk.W)
        self.scroll_count = tk.IntVar(value=self.config.get("scroll_count"))
        ttk.Spinbox(settings_frame, from_=1, to=100000, textvariable=self.scroll_count, width=10).grid(row=0, column=1, padx=5)

        # 翻页间隔
        ttk.Label(settings_frame, text="间隔(秒):").grid(row=0, column=2, padx=(20, 0))
        self.scroll_delay = tk.DoubleVar(value=self.config.get("scroll_delay"))
        ttk.Spinbox(settings_frame, from_=0.01, to=10, increment=0.01, textvariable=self.scroll_delay, width=10).grid(row=0, column=3, padx=5)

        # 滑动时长
        ttk.Label(settings_frame, text="滑动时长(ms):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.scroll_duration = tk.IntVar(value=self.config.get("scroll_duration"))
        ttk.Spinbox(settings_frame, from_=50, to=2000, increment=50, textvariable=self.scroll_duration, width=10).grid(row=1, column=1, padx=5)

        # 控制按钮
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        self.start_btn = ttk.Button(btn_frame, text="开始翻页", command=self._start_scroll)
        self.start_btn.pack(side=tk.LEFT)

        self.stop_btn = ttk.Button(btn_frame, text="停止翻页", command=self._stop_scroll, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=10)

        # 进度条
        self.scroll_progress = ttk.Progressbar(tab, mode='determinate')
        self.scroll_progress.pack(fill=tk.X, padx=10, pady=5)

        # 进度标签
        self.scroll_label = ttk.Label(tab, text="就绪")
        self.scroll_label.pack(padx=10)

    def _create_import_tab(self):
        """创建导入选项卡"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="数据导入")

        # 数据源
        src_frame = ttk.LabelFrame(tab, text="数据源", padding=10)
        src_frame.pack(fill=tk.X, padx=10, pady=5)

        self.src_path = tk.StringVar()
        ttk.Entry(src_frame, textvariable=self.src_path, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(src_frame, text="浏览", command=self._browse_src).pack(side=tk.LEFT, padx=5)
        ttk.Button(src_frame, text="自动查找", command=self._auto_find_src).pack(side=tk.LEFT)

        # 导入选项
        opt_frame = ttk.LabelFrame(tab, text="导入选项", padding=10)
        opt_frame.pack(fill=tk.X, padx=10, pady=5)

        self.filter_npc = tk.BooleanVar(value=self.config.get("filter_npc"))
        ttk.Checkbutton(opt_frame, text="过滤 NPC 战斗（打城）", variable=self.filter_npc).pack(anchor=tk.W)

        self.filter_incomplete = tk.BooleanVar(value=self.config.get("filter_incomplete"))
        ttk.Checkbutton(opt_frame, text="过滤攻方武将不足 3 名", variable=self.filter_incomplete).pack(anchor=tk.W)

        # 导入按钮
        ttk.Button(tab, text="开始导入", command=self._start_import).pack(pady=10)

        # 导入结果
        self.import_result = ttk.Label(tab, text="")
        self.import_result.pack(padx=10)

    def _create_export_tab(self):
        """创建导出选项卡"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="数据导出")

        # 导出选项
        opt_frame = ttk.LabelFrame(tab, text="导出选项", padding=10)
        opt_frame.pack(fill=tk.X, padx=10, pady=5)

        self.export_valid = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt_frame, text="只导出有效战报（攻方3武将）", variable=self.export_valid).pack(anchor=tk.W)

        self.export_no_npc = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt_frame, text="排除 NPC 战斗", variable=self.export_no_npc).pack(anchor=tk.W)

        self.export_members = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_frame, text="包含同盟成员", variable=self.export_members).pack(anchor=tk.W)

        # 导出模式
        mode_frame = ttk.LabelFrame(tab, text="导出模式", padding=10)
        mode_frame.pack(fill=tk.X, padx=10, pady=5)

        self.export_mode = tk.StringVar(value="single")
        ttk.Radiobutton(mode_frame, text="单个 Excel 文件", variable=self.export_mode, value="single").pack(anchor=tk.W)
        ttk.Radiobutton(mode_frame, text="按同盟分组（每个同盟一个文件）", variable=self.export_mode, value="by_alliance").pack(anchor=tk.W)

        # 导出按钮
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(btn_frame, text="导出 Excel", command=self._export_excel).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="打开导出目录", command=self._open_export_dir).pack(side=tk.LEFT, padx=10)

        # 导出结果
        self.export_result = ttk.Label(tab, text="")
        self.export_result.pack(padx=10)

    def _create_settings_tab(self):
        """创建设置选项卡"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="设置")

        # ADB 设置
        adb_frame = ttk.LabelFrame(tab, text="ADB 设置", padding=10)
        adb_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(adb_frame, text="ADB 路径:").grid(row=0, column=0, sticky=tk.W)
        self.adb_path = tk.StringVar(value=self.config.get("adb_path"))
        ttk.Entry(adb_frame, textvariable=self.adb_path, width=50).grid(row=0, column=1, padx=5)
        ttk.Button(adb_frame, text="浏览", command=self._browse_adb).grid(row=0, column=2)

        ttk.Label(adb_frame, text="模拟器端口:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.serial = tk.StringVar(value=self.config.get("serial"))
        ttk.Entry(adb_frame, textvariable=self.serial, width=20).grid(row=1, column=1, padx=5, sticky=tk.W)

        # 游戏版本
        ttk.Label(adb_frame, text="游戏版本:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.game_version = tk.StringVar(value=self.config.get("game_version"))
        version_combo = ttk.Combobox(adb_frame, textvariable=self.game_version, values=["auto", "uc", "official"], state="readonly", width=10)
        version_combo.grid(row=2, column=1, padx=5, sticky=tk.W)

        # 保存按钮
        ttk.Button(tab, text="保存设置", command=self._save_settings).pack(pady=10)

        # 重新检测按钮
        ttk.Button(tab, text="重新检测 ADB", command=self._redetect_adb).pack(pady=5)

    def _create_log_area(self):
        """创建日志区域"""
        frame = ttk.LabelFrame(self.root, text="日志", padding=5)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.log_text = tk.Text(frame, height=6, state=tk.DISABLED)
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)

        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _log(self, message: str):
        """添加日志"""
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _update_status(self):
        """更新状态栏（只在状态变化时更新 UI）"""
        # 防止重复调用
        if self._updating:
            self.root.after(10000, self._update_status)
            return
        
        self._updating = True
        
        try:
            # ADB 状态
            adb_ok = self.adb and self.adb.is_connected()
            adb_text = "ADB: 已连接" if adb_ok else "ADB: 未连接"
            adb_color = "green" if adb_ok else "red"
            if adb_text != self._last_adb_status:
                self.adb_status.config(text=adb_text, foreground=adb_color)
                self._last_adb_status = adb_text

            # 游戏状态
            game_text = "游戏: 未检测"
            game_color = "gray"
            if adb_ok:
                try:
                    game = self.adb.detect_game()
                    if game == "uc":
                        game_text, game_color = "游戏: UC版", "blue"
                    elif game == "official":
                        game_text, game_color = "游戏: 官服", "blue"
                    else:
                        game_text, game_color = "游戏: 未运行", "gray"
                except Exception:
                    pass
            if game_text != self._last_game_status:
                self.game_status.config(text=game_text, foreground=game_color)
                self._last_game_status = game_text

            # 数据统计
            try:
                stats = self.importer.get_stats()
                data_text = f"数据: {stats['reports']} 条战报, {stats['members']} 条成员"
                if data_text != self._last_data_status:
                    self.data_status.config(text=data_text)
                    self._last_data_status = data_text
            except Exception:
                pass
                
        except Exception:
            pass
        finally:
            self._updating = False

        # 定时更新（10 秒间隔，减少闪烁）
        self.root.after(10000, self._update_status)

    def _start_scroll(self):
        """开始翻页"""
        if not self.adb:
            messagebox.showerror("错误", "ADB 未连接，请先配置 ADB")
            return

        if not self.adb.is_connected():
            messagebox.showerror("错误", "ADB 未连接，请检查模拟器是否运行")
            return

        # 保存配置
        self.config.set("scroll_count", self.scroll_count.get())
        self.config.set("scroll_delay", self.scroll_delay.get())
        self.config.set("scroll_duration", self.scroll_duration.get())
        self.config.save()

        # 设置回调
        self.scroller.set_callbacks(
            on_progress=self._on_scroll_progress,
            on_complete=self._on_scroll_complete,
            on_error=self._on_scroll_error
        )

        # 开始翻页
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.scroll_progress["value"] = 0
        self.scroll_progress["maximum"] = self.scroll_count.get()

        self._log(f"开始翻页: {self.scroll_count.get()} 次")
        self.scroller.start(
            count=self.scroll_count.get(),
            delay=self.scroll_delay.get(),
            duration=self.scroll_duration.get()
        )

    def _stop_scroll(self):
        """停止翻页"""
        if self.scroller:
            self.scroller.stop()
            self._log("翻页已停止")

        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)

    def _on_scroll_progress(self, current: int, total: int):
        """翻页进度回调"""
        self.scroll_progress["value"] = current
        self.scroll_label.config(text=f"翻页进度: {current}/{total}")

    def _on_scroll_complete(self):
        """翻页完成回调"""
        self.root.after(0, lambda: self._scroll_done())

    def _scroll_done(self):
        """翻页完成（在主线程中执行）"""
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.scroll_label.config(text="翻页完成")
        self._log("翻页完成！请运行数据导入")

    def _on_scroll_error(self, error: str):
        """翻页错误回调"""
        self.root.after(0, lambda: self._scroll_error(error))

    def _scroll_error(self, error: str):
        """翻页错误（在主线程中执行）"""
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self._log(f"翻页错误: {error}")
        messagebox.showerror("翻页错误", error)

    def _browse_src(self):
        """浏览数据源"""
        path = filedialog.askopenfilename(
            title="选择 stzbHelper 数据库",
            filetypes=[("SQLite 数据库", "*.db"), ("所有文件", "*.*")]
        )
        if path:
            self.src_path.set(path)

    def _auto_find_src(self):
        """自动查找数据源"""
        # 在常见位置查找
        search_dirs = [ROOT, ROOT / "tools" / "stzb-capture", Path(".")]
        for dir_path in search_dirs:
            path = self.importer.find_stzb_db(str(dir_path))
            if path:
                self.src_path.set(path)
                self._log(f"找到数据库: {path}")
                return

        messagebox.showinfo("提示", "未找到 stzbHelper 数据库，请手动选择")

    def _start_import(self):
        """开始导入"""
        src = self.src_path.get()
        if not src:
            messagebox.showerror("错误", "请选择数据源")
            return

        if not os.path.exists(src):
            messagebox.showerror("错误", f"文件不存在: {src}")
            return

        # 保存配置
        self.config.set("filter_npc", self.filter_npc.get())
        self.config.set("filter_incomplete", self.filter_incomplete.get())
        self.config.save()

        # 导入
        self._log(f"开始导入: {src}")
        try:
            imported, skipped, filtered_npc, filtered_incomplete, members = self.importer.import_data(
                src,
                filter_npc=self.filter_npc.get(),
                filter_incomplete=self.filter_incomplete.get()
            )

            result_text = (
                f"导入完成: {imported} 条战报, {members} 条成员\n"
                f"跳过(重复): {skipped}, 过滤(NPC): {filtered_npc}, 过滤(武将不足): {filtered_incomplete}"
            )
            self.import_result.config(text=result_text)
            self._log(result_text)

            # 更新统计
            stats = self.importer.get_stats()
            self.data_status.config(text=f"数据: {stats['reports']} 条战报, {stats['members']} 条成员")

        except Exception as e:
            self._log(f"导入错误: {e}")
            messagebox.showerror("导入错误", str(e))

    def _export_excel(self):
        """导出 Excel"""
        mode = self.export_mode.get()

        if mode == "single":
            # 单文件模式
            default_path = self.config.get("last_export_path") or str(ROOT / "data" / "battle_reports.xlsx")
            path = filedialog.asksaveasfilename(
                title="保存 Excel 文件",
                defaultextension=".xlsx",
                filetypes=[("Excel 文件", "*.xlsx")],
                initialfile=Path(default_path).name,
                initialdir=str(Path(default_path).parent)
            )

            if not path:
                return

            # 保存配置
            self.config.set("last_export_path", path)
            self.config.save()

            # 导出
            self._log(f"开始导出: {path}")
            try:
                count = export_to_excel(
                    str(self.importer.db_path),
                    path,
                    filter_valid=self.export_valid.get(),
                    filter_no_npc=self.export_no_npc.get(),
                    include_members=self.export_members.get()
                )

                self.export_result.config(text=f"导出完成: {count} 条记录")
                self._log(f"导出完成: {path}")

                # 询问是否打开
                if messagebox.askyesno("导出完成", f"已导出到:\n{path}\n\n是否打开文件？"):
                    os.startfile(path)

            except Exception as e:
                self._log(f"导出错误: {e}")
                messagebox.showerror("导出错误", str(e))

        else:
            # 按同盟分组模式
            default_dir = self.config.get("last_export_dir") or str(ROOT / "data" / "alliances")
            output_dir = filedialog.askdirectory(
                title="选择导出目录",
                initialdir=default_dir
            )

            if not output_dir:
                return

            # 保存配置
            self.config.set("last_export_dir", output_dir)
            self.config.save()

            # 导出
            self._log(f"开始按同盟导出到: {output_dir}")
            try:
                exported_files = export_to_excel_by_alliance(
                    str(self.importer.db_path),
                    output_dir,
                    filter_valid=self.export_valid.get(),
                    filter_no_npc=self.export_no_npc.get(),
                    include_members=self.export_members.get()
                )

                count = len(exported_files)
                self.export_result.config(text=f"导出完成: {count} 个同盟")
                self._log(f"导出完成: {count} 个同盟")

                # 询问是否打开目录
                if messagebox.askyesno("导出完成", f"已导出 {count} 个同盟的 Excel 文件到:\n{output_dir}\n\n是否打开目录？"):
                    os.startfile(output_dir)

            except Exception as e:
                self._log(f"导出错误: {e}")
                messagebox.showerror("导出错误", str(e))

    def _open_export_dir(self):
        """打开导出目录"""
        # 优先打开按同盟导出的目录
        export_dir = self.config.get("last_export_dir")
        if export_dir and os.path.exists(export_dir):
            os.startfile(export_dir)
            return

        # 其次打开单文件导出的目录
        export_path = self.config.get("last_export_path")
        if export_path and os.path.exists(export_path):
            os.startfile(str(Path(export_path).parent))
        else:
            os.startfile(str(ROOT / "data"))

    def _browse_adb(self):
        """浏览 ADB 路径"""
        path = filedialog.askopenfilename(
            title="选择 ADB 可执行文件",
            filetypes=[("ADB", "adb.exe"), ("所有文件", "*.*")]
        )
        if path:
            self.adb_path.set(path)

    def _save_settings(self):
        """保存设置"""
        self.config.set("adb_path", self.adb_path.get())
        self.config.set("serial", self.serial.get())
        self.config.set("game_version", self.game_version.get())
        self.config.save()

        # 重新初始化 ADB
        self._auto_detect_adb()

        messagebox.showinfo("提示", "设置已保存")
        self._log("设置已保存")

    def _redetect_adb(self):
        """重新检测 ADB"""
        self.config.set("adb_path", "")
        self._auto_detect_adb()
        self._update_status()

        if self.adb:
            self._log(f"ADB 路径: {self.config.get('adb_path')}")
        else:
            self._log("未找到 ADB")

    def run(self):
        """运行应用"""
        self.root.mainloop()


def main():
    app = BattleAssistantApp()
    app.run()


if __name__ == "__main__":
    main()
