param(
    [string]$DatabasePath = "",
    [string]$InnoSetupPath = "",
    [switch]$SkipDownload,
    [switch]$CompileInstaller,
    [switch]$SkipInnoInstall
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$BuildBin = Join-Path $RepoRoot "build\bin"
$PackageDir = Join-Path $RepoRoot "build\package"
$DepsDir = Join-Path $PackageDir "deps"
$DataDir = Join-Path $PackageDir "data"
$PlatformToolsDir = Join-Path $PackageDir "platform-tools"
$InstallerOutputDir = Join-Path $RepoRoot "build\installer-output"

$PlatformToolsUrl = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
$WebView2Url = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"
$NpcapUrl = "https://npcap.com/dist/npcap-1.88.exe"
$InnoSetupUrl = "https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-6.7.3.exe"
$InnoChineseLanguageUrl = "https://raw.githubusercontent.com/jrsoftware/issrc/main/Files/Languages/Unofficial/ChineseSimplified.isl"

function New-CleanDirectory($Path) {
    if (Test-Path $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
    New-Item -ItemType Directory -Path $Path | Out-Null
}

function Download-File($Url, $OutputPath) {
    Write-Host "下载 $Url"
    Invoke-WebRequest -Uri $Url -OutFile $OutputPath
}

function Try-DownloadFile($Url, $OutputPath) {
    try {
        Download-File $Url $OutputPath
        return $true
    } catch {
        Write-Warning "下载失败: $Url"
        Write-Warning $_.Exception.Message
        return $false
    }
}

function Find-InnoSetupCompiler {
    param([string]$ExplicitPath)

    if ($ExplicitPath -and (Test-Path $ExplicitPath)) {
        return (Resolve-Path $ExplicitPath).Path
    }

    $Command = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($Command) {
        return $Command.Source
    }

    $Candidates = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
        "${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe"
    )
    foreach ($Candidate in $Candidates) {
        if (Test-Path $Candidate) {
            return $Candidate
        }
    }

    return ""
}

function Install-InnoSetupCompiler {
    if ($SkipInnoInstall) {
        throw "未找到 Inno Setup 编译器 ISCC.exe，且已指定 -SkipInnoInstall。"
    }

    New-Item -ItemType Directory -Path $DepsDir -Force | Out-Null
    $InstallerPath = Join-Path $DepsDir "innosetup-6.7.3.exe"
    if (-not (Test-Path $InstallerPath)) {
        Download-File $InnoSetupUrl $InstallerPath
    }

    Write-Host "正在安装 Inno Setup 6（仅用于本机打包，最终用户不需要安装它）..."
    $Args = "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /CURRENTUSER"
    $Process = Start-Process -FilePath $InstallerPath -ArgumentList $Args -Wait -PassThru -WindowStyle Hidden
    if ($Process.ExitCode -ne 0) {
        throw "Inno Setup 安装失败，退出码: $($Process.ExitCode)"
    }

    $Compiler = Find-InnoSetupCompiler -ExplicitPath ""
    if (-not $Compiler) {
        throw "Inno Setup 已安装但仍找不到 ISCC.exe，请手动安装 Inno Setup 6 后重试。"
    }
    return $Compiler
}

function Ensure-InnoLanguageFile {
    param([string]$CompilerPath)

    $LanguagePath = Join-Path $DepsDir "ChineseSimplified.isl"
    if (Try-DownloadFile $InnoChineseLanguageUrl $LanguagePath) {
        return
    }

    $DefaultLanguagePath = Join-Path (Split-Path $CompilerPath -Parent) "Default.isl"
    if (Test-Path $DefaultLanguagePath) {
        Write-Warning "简体中文语言包下载失败，改用 Inno Setup 自带默认语言继续编译。"
        Copy-Item -LiteralPath $DefaultLanguagePath -Destination $LanguagePath -Force
        return
    }

    Write-Warning "找不到 Inno Setup 默认语言文件，使用仓库内置 fallback 语言文件继续编译。"
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot "DefaultInstallerLanguage.isl") -Destination $LanguagePath -Force
}

function Resolve-DatabasePath {
    param([string]$ExplicitPath)

    if ($ExplicitPath) {
        return (Resolve-Path $ExplicitPath).Path
    }

    $ConfigPath = Join-Path $BuildBin "config.json"
    if (Test-Path $ConfigPath) {
        $Config = Get-Content -Raw $ConfigPath | ConvertFrom-Json
        if ($Config.database_path -and (Test-Path $Config.database_path)) {
            return (Resolve-Path $Config.database_path).Path
        }
    }

    $Candidate = Get-ChildItem -Path $BuildBin -Filter "*.db" -File -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($Candidate) {
        return $Candidate.FullName
    }

    throw "没有找到要随安装包分发的数据库。请传入 -DatabasePath E:\path\to\your.db"
}

Set-Location $RepoRoot

Write-Host "构建 Wails 桌面程序..."
wails build -o stzbHelper-wails.exe

New-CleanDirectory $PackageDir
New-Item -ItemType Directory -Path $DepsDir, $DataDir, $InstallerOutputDir -Force | Out-Null

Copy-Item -LiteralPath (Join-Path $BuildBin "stzbHelper-wails.exe") -Destination (Join-Path $PackageDir "stzbHelper-wails.exe") -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "user-guide.md") -Destination (Join-Path $PackageDir "使用说明.md") -Force

$ResolvedDatabasePath = Resolve-DatabasePath -ExplicitPath $DatabasePath
Write-Host "复制数据库: $ResolvedDatabasePath"
Copy-Item -LiteralPath $ResolvedDatabasePath -Destination (Join-Path $DataDir "default.db") -Force

if (-not $SkipDownload) {
    $ZipPath = Join-Path $DepsDir "platform-tools-latest-windows.zip"
    Download-File $PlatformToolsUrl $ZipPath
    Expand-Archive -LiteralPath $ZipPath -DestinationPath $PackageDir -Force
    Remove-Item -LiteralPath $ZipPath -Force

    Download-File $WebView2Url (Join-Path $DepsDir "MicrosoftEdgeWebView2Setup.exe")
    Download-File $NpcapUrl (Join-Path $DepsDir "npcap-installer.exe")
} elseif (-not (Test-Path $PlatformToolsDir)) {
    Write-Warning "已跳过下载，但 $PlatformToolsDir 不存在；安装包内将没有内置 ADB。"
}

Write-Host "发布目录已准备: $PackageDir"

if ($CompileInstaller) {
    $InnoSetupPath = Find-InnoSetupCompiler -ExplicitPath $InnoSetupPath
    if (-not $InnoSetupPath) {
        $InnoSetupPath = Install-InnoSetupCompiler
    }
    Ensure-InnoLanguageFile -CompilerPath $InnoSetupPath

    Write-Host "编译安装包..."
    & $InnoSetupPath (Join-Path $PSScriptRoot "stzbHelper.iss")
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup 编译失败，退出码: $LASTEXITCODE"
    }
    Write-Host "安装包输出目录: $InstallerOutputDir"
}
