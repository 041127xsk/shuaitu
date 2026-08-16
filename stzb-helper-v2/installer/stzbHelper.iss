#define MyAppName "stzbHelper"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "stzbHelper"
#define MyAppExeName "stzbHelper-wails.exe"
#define PackageDir "..\build\package"

[Setup]
AppId={{5D4F6CE4-021C-49F1-8F43-1E8E30F73E9B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\build\installer-output
OutputBaseFilename=stzbHelper-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "chinesesimp"; MessagesFile: "{#PackageDir}\deps\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务"; Flags: checkedonce

[Files]
Source: "{#PackageDir}\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#PackageDir}\使用说明.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#PackageDir}\data\default.db"; DestDir: "{app}\data"; DestName: "default.db"; Flags: ignoreversion onlyifdoesntexist
Source: "{#PackageDir}\platform-tools\*"; DestDir: "{app}\platform-tools"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#PackageDir}\deps\MicrosoftEdgeWebView2Setup.exe"; DestDir: "{tmp}"; Flags: ignoreversion deleteafterinstall skipifsourcedoesntexist
Source: "{#PackageDir}\deps\npcap-installer.exe"; DestDir: "{tmp}"; Flags: ignoreversion deleteafterinstall skipifsourcedoesntexist

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\使用说明"; Filename: "{app}\使用说明.md"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{tmp}\MicrosoftEdgeWebView2Setup.exe"; Parameters: "/silent /install"; StatusMsg: "正在安装/修复 WebView2 Runtime..."; Flags: waituntilterminated; Check: ShouldRunWebView2Installer
Filename: "{tmp}\npcap-installer.exe"; Description: "安装 Npcap 抓包驱动"; StatusMsg: "正在启动 Npcap 安装程序，请按提示完成安装..."; Flags: waituntilterminated; Check: ShouldInstallNpcap
Filename: "{app}\{#MyAppExeName}"; Description: "启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
function JsonEscape(Value: string): string;
begin
  Result := Value;
  StringChangeEx(Result, '\', '\\', True);
end;

function ShouldInstallNpcap(): Boolean;
begin
  Result := FileExists(ExpandConstant('{tmp}\npcap-installer.exe')) and
    (not RegKeyExists(HKLM, 'SOFTWARE\Npcap'));
end;

function ShouldRunWebView2Installer(): Boolean;
begin
  Result := FileExists(ExpandConstant('{tmp}\MicrosoftEdgeWebView2Setup.exe'));
end;

procedure CreateDefaultConfig();
var
  ConfigPath: string;
  AppDir: string;
  ConfigText: string;
begin
  ConfigPath := ExpandConstant('{app}\config.json');
  if FileExists(ConfigPath) then
    exit;

  AppDir := ExpandConstant('{app}');
  ConfigText :=
    '{' + #13#10 +
    '  "adb_path": "' + JsonEscape(AppDir + '\platform-tools\adb.exe') + '",' + #13#10 +
    '  "adb_serial": "127.0.0.1:16384",' + #13#10 +
    '  "scroll_count": 4000,' + #13#10 +
    '  "scroll_delay": 100,' + #13#10 +
    '  "scroll_duration": 100,' + #13#10 +
    '  "stop_on_duplicate": false,' + #13#10 +
    '  "database_path": "' + JsonEscape(AppDir + '\data\default.db') + '",' + #13#10 +
    '  "default_dis_max_level": 19,' + #13#10 +
    '  "default_atk_min_level": 25,' + #13#10 +
    '  "adb_profiles": [' + #13#10 +
    '    {' + #13#10 +
    '      "id": "default",' + #13#10 +
    '      "name": "默认模拟器",' + #13#10 +
    '      "adb_path": "' + JsonEscape(AppDir + '\platform-tools\adb.exe') + '",' + #13#10 +
    '      "adb_serial": "127.0.0.1:16384"' + #13#10 +
    '    }' + #13#10 +
    '  ],' + #13#10 +
    '  "active_adb_profile_id": "default"' + #13#10 +
    '}';

  SaveStringToFile(ConfigPath, ConfigText, False);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    CreateDefaultConfig();
end;
