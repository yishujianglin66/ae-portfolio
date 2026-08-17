@echo off
set "SRC=C:\Users\Administrator\Desktop\AE-Knowledge-Vault"
set "AE2025=C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\Scripts"
set "AE2026=C:\Program Files\Adobe\Adobe After Effects 2026\Support Files\Scripts"

if exist "%AE2025%" (set "DST=%AE2025%") else (set "DST=%AE2026%")

copy /Y "%SRC%\test_load_listener.jsx" "%DST%\test_load_listener.jsx"
copy /Y "%SRC%\start_mcp_listener.jsx" "%DST%\start_mcp_listener.jsx"
echo DONE -^> %DST%
pause
