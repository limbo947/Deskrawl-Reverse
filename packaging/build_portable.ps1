#Requires -Version 5.1
<#
.SYNOPSIS
  构建「点开即用」的 Windows 便携包（PyInstaller one-folder + 随包 data/ + zip）。

.DESCRIPTION
  产物：dist\<ExeName>\ 目录（exe + _internal\ + data\）与 dist\<ExeName>-<ver>-win64.zip。
  随包数据是**白名单**：只拷 so_dump、loc 与示例构建 demo-hunter.json。个人构建
  （data/builds 其余）、本机会话状态、几十 MB 的 data/schema 逆向产物一律不入包——分发即泄漏。

.EXAMPLE
  .\packaging\build_portable.ps1
  .\packaging\build_portable.ps1 -ExeName DeskrawlTool -Version v0.1.0 -NoInstall
#>
[CmdletBinding()]
param(
  [string]$ExeName = 'Deskrawl计算台',   # 与 GUI 现有中文命名一致；解压工具出问题时可改 ASCII
  [string]$Version = '',                 # 空则取 git describe --tags --always
  [string]$Python  = '',                 # 空则依次用 .venv-gui / PATH 上的 python
  [switch]$NoInstall                     # CI 中依赖已装好，跳过 pip
)
$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

# 解释器优先级：显式参数 → 仓库内 .venv-gui（与 启动GUI.bat 同一份）→ PATH
$py = if ($Python) { $Python }
      elseif (Test-Path "$root\.venv-gui\Scripts\python.exe") { "$root\.venv-gui\Scripts\python.exe" }
      else { (Get-Command python).Source }
Write-Host "使用解释器：$py"

if (-not $NoInstall) {
  & $py -m pip install --upgrade -r "$root\requirements-gui.txt" -r "$root\requirements-build.txt"
  if ($LASTEXITCODE -ne 0) { throw 'pip 安装依赖失败' }
}

if (-not $Version) { $Version = (git -C $root describe --tags --always) }
$env:DESKRAWL_EXE_NAME = $ExeName     # spec 读它定 exe/目录名（单一开关）

& $py -m PyInstaller --noconfirm --clean "$root\packaging\deskrawl.spec" `
     --distpath "$root\dist" --workpath "$root\build\pyi"
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller 构建失败' }

# 随包数据白名单（见文件头 DESCRIPTION）；data/ 放 exe 同级，才与源码的 __file__ 布局同构
$out = Join-Path "$root\dist" $ExeName
$dataOut = Join-Path $out 'data'
New-Item -ItemType Directory -Force (Join-Path $dataOut 'builds') | Out-Null
Copy-Item (Join-Path "$root\data" 'so_dump') $dataOut -Recurse -Force
Copy-Item (Join-Path "$root\data" 'loc') $dataOut -Recurse -Force
Copy-Item (Join-Path "$root\data\builds" 'demo-hunter.json') (Join-Path $dataOut 'builds') -Force

$zip = Join-Path "$root\dist" "$ExeName-$Version-win64.zip"
& $py "$root\packaging\make_zip.py" $zip $out
if ($LASTEXITCODE -ne 0) { throw '打包 zip 失败' }

$sizeMb = [math]::Round((Get-ChildItem $out -Recurse -File | Measure-Object -Sum Length).Sum / 1MB, 1)
Write-Host "完成：$out（解压后 $sizeMb MB）"
# 用字符串输出而非 Format-List：格式对象会把调用方的管道污染坏（实测 Select-Object 直接报错）
$hash = (Get-FileHash $zip -Algorithm SHA256).Hash
Write-Host "SHA256: $hash"
