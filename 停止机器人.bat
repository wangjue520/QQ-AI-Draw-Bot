@echo off
title 停止 跑图姬
cd /d "%~dp0"
echo ==========================================
echo   正在停止 跑图姬 ...
echo ==========================================
echo.

powershell -NoProfile -Command "$list = Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^python' -and $_.CommandLine -match 'bot\.py' }; if ($list) { foreach ($p in $list) { Write-Host ('  结束进程 PID=' + $p.ProcessId + '  ' + $p.Name); Stop-Process -Id $p.ProcessId -Force } ; Write-Host '' ; Write-Host '机器人已停止。' } else { Write-Host '没有发现正在运行的机器人（bot.py）进程。' }"

echo.
pause
