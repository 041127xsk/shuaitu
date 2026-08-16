# stzbHelper Windows 安装包

这套脚本用于生成适合发给电脑小白的一键安装包。

## 打包内容

- `stzbHelper-wails.exe`
- 随包数据库：安装后为 `data\default.db`
- 内置 ADB：安装后为 `platform-tools\adb.exe`
- WebView2 Runtime 安装器
- Npcap 安装器
- 安装时创建 `config.json`
- 开始菜单和桌面快捷方式

安装目录默认是当前用户可写目录：

```text
%LOCALAPPDATA%\Programs\stzbHelper
```

这样普通用户运行软件时可以正常写入 `config.json`、数据库和运行状态文件。

## 准备发布目录

从项目根目录运行：

```powershell
.\installer\prepare-release.ps1 -DatabasePath "E:\path\to\your.db"
```

如果不传 `-DatabasePath`，脚本会优先读取 `build\bin\config.json` 中的 `database_path`，并复制为安装包内的 `data\default.db`。

## 生成安装包

运行：

```powershell
.\installer\prepare-release.ps1 -DatabasePath "E:\path\to\your.db" -CompileInstaller
```

如果当前电脑没有 Inno Setup 6，脚本会自动下载并安装 Inno Setup 6.7.3。最终用户不需要安装 Inno Setup。

输出位置：

```text
build\installer-output\stzbHelper-Setup.exe
```

## 依赖说明

- ADB 会随安装包复制，不需要用户自己找 `adb.exe`。
- WebView2 安装器会随安装包携带并静默安装/修复。
- Npcap 是抓包驱动，安装时会启动官方安装程序，可能弹出 UAC 管理员权限提示。
- MuMu 模拟器和《率土之滨》本体不随安装包分发，用户仍需自己安装并登录游戏。

## 更新包注意事项

- `data\default.db` 使用 `onlyifdoesntexist`，升级安装不会覆盖用户已有数据库。
- `config.json` 只在不存在时创建，升级安装不会覆盖用户 ADB 和数据库选择。
- 如果要给用户发一份全新数据库，请让用户先备份/删除安装目录下旧的 `data\default.db`，或在软件内新建/选择数据库。
