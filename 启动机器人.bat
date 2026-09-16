@echo off
chcp 65001 >nul
title 跑图姬
cd /d "%~dp0"

REM ================== 按你的实际环境修改这两行 ==================
set "FORGE_DIR=F:\sd-forge-aki\sd-webui-forge-aki-v1.0\sd-webui-forge-aki"
set "QQ_EXE=F:\QQ.exe"
REM   FORGE_DIR：Forge 的目录（里面放着 webui-user.bat 的那一层）
REM   QQ_EXE：QQ 的安装位置（文件不存在时启动器会自动探测，一般不用改）
REM ==============================================================

echo ==========================================
echo   跑图姬 一键启动器
echo ==========================================
echo.

set PY=
py -3 --version >nul 2>&1
if not errorlevel 1 set PY=py -3
if not defined PY (
    python --version >nul 2>&1
    if not errorlevel 1 set PY=python
)
if not defined PY goto nopython
echo [1/5] Python:
%PY% --version
echo.

echo [2/5] 检查依赖（卡太久说明网络不通）...
%PY% -m pip install -U --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    echo 默认源失败，自动换清华镜像重试 ...
    %PY% -m pip install -U --disable-pip-version-check -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
)
if errorlevel 1 goto pipfail
echo.

echo [3/5] 检查 NapCat ...
if not exist "%~dp0NapCat\Shell\napcat.mjs" (
    echo   首次使用，正在自动部署 NapCat ...
    call "%~dp0部署NapCat.bat" --from-launcher
)
if exist "%~dp0NapCat\Shell\napcat.mjs" (
    echo   NapCat 已就绪
) else (
    echo   [警告] NapCat 未就绪，机器人能启动但 QQ 连不上（重跑本 bat 或双击 部署NapCat.bat）
)
echo.

echo [4/5] 检查 Forge / NapCat / QQ ...
if not exist "%FORGE_DIR%\webui-user.bat" (
    echo   [警告] FORGE_DIR 指向的目录不对：%FORGE_DIR%
    echo   请右键编辑本 bat，把 FORGE_DIR= 改成你的 Forge 目录后重开
)
powershell -NoProfile -Command "if (Get-NetTCPConnection -State Listen -LocalPort 7860 -ErrorAction SilentlyContinue) { Write-Host '  Forge 已在运行' } else { Start-Process -FilePath '%FORGE_DIR%\webui-user.bat' -WorkingDirectory '%FORGE_DIR%' -WindowStyle Minimized; Write-Host '  Forge 未运行，已最小化启动（模型加载约 3 分钟，加载完才能跑图）' }"
if not exist "%QQ_EXE%" (
    echo   QQ_EXE=%QQ_EXE% 不存在，尝试自动探测 QQ ...
    set "QQ_DETECTED="
    rem 不用管道符（for /f 反引号里 ^| 转义不可靠）；QQ NT 卸载项常不写安装目录，用 DisplayIcon 兜底
    for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "$c=@('%ProgramFiles%\Tencent\QQ\QQ.exe','%ProgramFiles(x86)%\Tencent\QQ\QQ.exe','D:\Program Files\Tencent\QQ\QQ.exe','D:\Tencent\QQ\QQ.exe','D:\QQ\QQ.exe','E:\QQ.exe','F:\QQ.exe'); foreach($k in 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*','HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'){ foreach($p in (Get-ItemProperty $k -ErrorAction SilentlyContinue)){ if($p.DisplayName -match '^QQ'){ $loc=$p.InstallLocation; if($loc){ $c+=(Join-Path $loc 'QQ.exe') } else { $c+=($p.DisplayIcon -replace ',\d+$','') } } } }; $f=$null; foreach($x in $c){ if(-not $f -and ($x -like '*\QQ.exe') -and (Test-Path $x)){ $f=$x } }; if($f){ $f }"`) do set "QQ_DETECTED=%%~i"
    if defined QQ_DETECTED (
        echo   已自动找到 QQ：%QQ_DETECTED%
        set "QQ_EXE=%QQ_DETECTED%"
    ) else (
        echo   [警告] 自动探测失败。请安装 QQ：https://im.qq.com ，或编辑本 bat 的 QQ_EXE=
    )
)
if exist "%QQ_EXE%" (
    powershell -NoProfile -Command "if (Get-Process NapCatWinBootMain -ErrorAction SilentlyContinue) { Write-Host '  NapCat 已在运行' } else { $env:NAPCAT_PATCH_PACKAGE='%~dp0NapCat\Shell\qqnt.json'; $env:NAPCAT_LOAD_PATH='%~dp0NapCat\Shell\loadNapCat.js'; $env:NAPCAT_INJECT_PATH='%~dp0NapCat\Shell\NapCatWinBootHook.dll'; $env:NAPCAT_LAUNCHER_PATH='%~dp0NapCat\Shell\NapCatWinBootMain.exe'; $env:NAPCAT_MAIN_PATH='%~dp0NapCat\Shell\napcat.mjs'; Start-Process -FilePath $env:NAPCAT_LAUNCHER_PATH -ArgumentList '\"%QQ_EXE%\"', $env:NAPCAT_INJECT_PATH -WorkingDirectory '%~dp0NapCat\Shell' -WindowStyle Minimized; Write-Host '  NapCat 未运行，已最小化启动' }"
    if "%PY%"=="py -3" (
        powershell -NoProfile -Command "Start-Process -FilePath 'py.exe' -ArgumentList '-3','%~dp0napcat_auto_login.py' -WorkingDirectory '%~dp0' -WindowStyle Hidden"
    ) else (
        powershell -NoProfile -Command "Start-Process -FilePath 'python.exe' -ArgumentList '%~dp0napcat_auto_login.py' -WorkingDirectory '%~dp0' -WindowStyle Hidden"
    )
    echo   小号自动登录任务已提交（自动上线 + 自动配好反向 WS，无需扫码）
) else (
    echo   [警告] 没有可用 QQ，跳过 NapCat 启动
)
echo.

echo [5/5] 启动机器人（本窗口不能关，关了机器人就下线）...
%PY% bot.py
goto end

:nopython
echo [错误] 没找到 Python。
echo 请先安装 Python 3.10+ ： https://www.python.org/downloads/
echo 安装时务必勾选 Add python.exe to PATH ！
goto end

:pipfail
echo [错误] 依赖安装失败，请检查网络（或代理）后重试。
goto end

:end
echo.
pause
