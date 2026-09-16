@echo off
chcp 65001 >nul
title 部署 NapCat
cd /d "%~dp0"

echo ==========================================
echo   自动部署 NapCat（QQ 协议端）
echo ==========================================
echo.

rem ---------- 已部署过就直接退出 ----------
if exist "NapCat\Shell\napcat.mjs" (
    echo [√] 检测到 NapCat 已部署，无需重复安装。
    goto :qqcheck
)

rem ---------- 1. 下载 ----------
echo [1/3] 正在从 GitHub 下载 NapCat 最新版...
set "ZIP=%TEMP%\NapCat.Shell.zip"
if exist "%ZIP%" del /f /q "%ZIP%" >nul 2>&1
where curl.exe >nul 2>&1
if not errorlevel 1 (
    curl.exe -fL --retry 2 --connect-timeout 15 -o "%ZIP%" "https://github.com/NapNeko/NapCatQQ/releases/latest/download/NapCat.Shell.zip"
) else (
    powershell -NoProfile -Command "try { [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://github.com/NapNeko/NapCatQQ/releases/latest/download/NapCat.Shell.zip' -OutFile $env:ZIP -UseBasicParsing } catch { exit 1 }"
)
if not exist "%ZIP%" goto :dlfail

rem ---------- 2. 解压到 NapCat\Shell ----------
echo [2/3] 解压中（约 95MB，稍等）...
set "EXT=%TEMP%\napcat_deploy_tmp"
if exist "%EXT%" rd /s /q "%EXT%" >nul 2>&1
mkdir "%EXT%"
tar -xf "%ZIP%" -C "%EXT%" >nul 2>&1
if not exist "%EXT%\napcat.mjs" (
    rem 个别老系统没有 tar，退回 PowerShell 解压
    powershell -NoProfile -Command "try { Expand-Archive -Path $env:ZIP -DestinationPath $env:EXT -Force } catch { exit 1 }"
)
if not exist "%EXT%\napcat.mjs" goto :zipfail
if not exist "NapCat" mkdir "NapCat"
robocopy "%EXT%" "%~dp0NapCat\Shell" /E /MOVE /NFL /NDL /NJH /NJS /NC /NS >nul
rd /s /q "%EXT%" >nul 2>&1
del /f /q "%ZIP%" >nul 2>&1
if not exist "NapCat\Shell\napcat.mjs" goto :zipfail
echo [√] NapCat 已部署到 NapCat\Shell

rem 被启动器调用时到这里就返回，不重复检查 QQ、不停下等待
if "%~1"=="--from-launcher" exit /b 0

rem ---------- 3. 检查 QQ ----------
:qqcheck
echo.
echo [3/3] 检查 QQ 是否安装...
set "QQFOUND="
for %%P in (
    "%ProgramFiles%\Tencent\QQ\QQ.exe"
    "%ProgramFiles(x86)%\Tencent\QQ\QQ.exe"
    "D:\Program Files\Tencent\QQ\QQ.exe"
    "D:\Tencent\QQ\QQ.exe"
    "D:\QQ\QQ.exe"
    "E:\QQ.exe"
    "F:\QQ.exe"
) do if not defined QQFOUND if exist %%P set "QQFOUND=%%~P"
if not defined QQFOUND (
    rem 常见路径没找到，再去注册表里找。
    rem 注意：不用管道符（for /f 反引号里 ^| 转义不可靠）；
    rem QQ NT 卸载项常不写安装目录，用 DisplayIcon 兜底定位 QQ.exe。
    for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "$u=$null; foreach($k in 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*','HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'){ if($u){break}; foreach($p in (Get-ItemProperty $k -ErrorAction SilentlyContinue)){ if($p.DisplayName -match '^QQ' -and -not $u){ $loc=$p.InstallLocation; if($loc){ $q=Join-Path $loc 'QQ.exe'; if(Test-Path $q){ $u=$q } elseif(Test-Path $loc){ $u=$loc } } else { $ic=($p.DisplayIcon -replace ',\d+$',''); if($ic -like '*\QQ.exe' -and (Test-Path $ic)){ $u=$ic } } } } } }; if($u){ $u }"`) do if not defined QQFOUND set "QQFOUND=%%~i"
)
if defined QQFOUND (
    echo [√] 检测到 QQ：%QQFOUND%
    echo     启动机器人时会自动使用，一般不用改 bat。
) else (
    echo [!] 没检测到 QQ。请先安装：https://im.qq.com
    echo     装好后启动器仍找不到的话，再右键编辑 启动机器人.bat 里的 QQ_EXE= 一行。
)
echo.
echo ===== 部署完成 =====
echo 接下来双击 启动机器人.bat，会弹出小号登录二维码，手机扫码即可。
goto :end

:dlfail
echo.
echo [错误] 下载失败：连不上 GitHub。
echo 请开代理后重试，或手动下载 NapCat.Shell.zip：
echo   https://github.com/NapNeko/NapCatQQ/releases
echo 把它解压到本项目的 NapCat\Shell 文件夹即可。
goto :end

:zipfail
echo.
echo [错误] 解压失败。请手动把 NapCat.Shell.zip 解压到 NapCat\Shell 后重试。
goto :end

:end
if "%~1"=="--from-launcher" exit /b 0
pause
