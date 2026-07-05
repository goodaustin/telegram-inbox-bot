@echo off
REM 自動啟動並在當掉時自動重跑的機器人啟動器。
REM 此檔位於專案的 windows\ 資料夾；%~dp0.. 會回到專案根目錄。
cd /d "%~dp0.."
:loop
echo [%date% %time%] 啟動機器人...
uv run python -m inbox_bot.main
echo [%date% %time%] 機器人結束，5 秒後重新啟動... (要永久停止請關閉此視窗)
timeout /t 5 /nobreak >nul
goto loop
