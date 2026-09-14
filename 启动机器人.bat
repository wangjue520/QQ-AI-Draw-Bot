@echo off
title 跑图姬
cd /d "%~dp0"

REM ================== 按你的实际环境修改这两行 ==================
set "FORGE_DIR=F:\sd-forge-aki\sd-webui-forge-aki-v1.0\sd-webui-forge-aki"
set "QQ_EXE=F:\QQ.exe"
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
echo [1/4] Python:
%PY% --version
echo.

echo [2/4] 检查依赖（卡太久说明网络不通）...
%PY% -m pip install -U --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    echo 默认源失败，自动换清华镜像重试 ...
    %PY% -m pip install -U --disable-pip-version-check -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
)
if errorlevel 1 goto pipfail
echo.

echo [3/4] 检查 Forge / NapCat ...
powershell -NoProfile -Command "if (Get-NetTCPConnection -State Listen -LocalPort 7860 -ErrorAction SilentlyContinue) { Write-Host '  Forge 已在运行' } else { Start-Process -FilePath '%FORGE_DIR%\webui-user.bat' -WorkingDirectory '%FORGE_DIR%' -WindowStyle Minimized; Write-Host '  Forge 未运行，已最小化启动（模型加载约 3 分钟，加载完才能跑图）' }"
powershell -NoProfile -Command "if (Get-Process NapCatWinBootMain -ErrorAction SilentlyContinue) { Write-Host '  NapCat 已在运行' } else { $env:NAPCAT_PATCH_PACKAGE='%~dp0NapCat\Shell\qqnt.json'; $env:NAPCAT_LOAD_PATH='%~dp0NapCat\Shell\loadNapCat.js'; $env:NAPCAT_INJECT_PATH='%~dp0NapCat\Shell\NapCatWinBootHook.dll'; $env:NAPCAT_LAUNCHER_PATH='%~dp0NapCat\Shell\NapCatWinBootMain.exe'; $env:NAPCAT_MAIN_PATH='%~dp0NapCat\Shell\napcat.mjs'; Start-Process -FilePath $env:NAPCAT_LAUNCHER_PATH -ArgumentList '\"%QQ_EXE%\"', $env:NAPCAT_INJECT_PATH -WorkingDirectory '%~dp0NapCat\Shell' -WindowStyle Minimized; Write-Host '  NapCat 未运行，已最小化启动' }"
powershell -NoProfile -Command "Start-Process -FilePath 'py.exe' -ArgumentList '-3','%~dp0napcat_auto_login.py' -WorkingDirectory '%~dp0' -WindowStyle Hidden"
echo   小号自动登录任务已提交（NapCat 起来后自动上线，无需扫码）
echo.

echo [4/4] 启动机器人（本窗口不能关，关了机器人就下线）...
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
