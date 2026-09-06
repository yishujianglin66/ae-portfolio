@echo off
rem MasterCut polish watchdog v2 - auto-restart on silent render death.
rem Deaths observed 2026-09-05: attempt1 = GPU TDR reset (LiveKernelEvent 141),
rem attempt2 = silent aerender death, no kernel event. Both after comp build,
rem during aerender render. This watchdog institutionalizes the manual
rem "crash self-heal restart" used throughout the v2-v9 era.
rem Flow per attempt: build (bridge saves master.aep) -> wait for aerender
rem auto-launch -> wait for aerender exit -> check polish/*.mp4 -> retry if none.
rem Usage: scripts\polish_watchdog.cmd <run_dir> <tag>
setlocal enabledelayedexpansion
set RUN_DIR=%1
set TAG=%2
if "%RUN_DIR%"=="" (echo usage: polish_watchdog.cmd ^<run_dir^> ^<tag^> & exit /b 1)
if "%TAG%"=="" set TAG=%~nx2
cd /d C:\Users\Administrator\Desktop\AE-Knowledge-Vault
set LOG=logs\polish_watchdog.log
set MAX=3

for /L %%i in (1,1,%MAX%) do (
  echo ====== %date% %time% attempt %%i/%MAX%: build ====== >> %LOG%
  python -u scripts\build_master_polish.py %RUN_DIR% %TAG% >> %LOG% 2>&1

  rem --- wait up to 120s for aerender to appear (auto-launched after build) ---
  set AE_SEEN=0
  for /L %%w in (1,1,24) do (
    tasklist /FI "IMAGENAME eq aerender.exe" 2>nul | find /I "aerender.exe" >nul && set AE_SEEN=1
    if "!AE_SEEN!"=="1" goto :wait_render
    timeout /t 5 /nobreak >nul
  )
  :wait_render
  if "!AE_SEEN!"=="0" (
    echo ====== %date% %time% attempt %%i: aerender never appeared ====== >> %LOG%
  ) else (
    echo ====== %date% %time% attempt %%i: aerender rendering, waiting for exit ====== >> %LOG%
    rem --- wait up to 40 min for aerender to exit ---
    for /L %%w in (1,1,480) do (
      tasklist /FI "IMAGENAME eq aerender.exe" 2>nul | find /I "aerender.exe" >nul || goto :render_done
      timeout /t 5 /nobreak >nul
    )
    :render_done
    echo ====== %date% %time% attempt %%i: aerender exited ====== >> %LOG%
  )

  rem --- success check: any mp4 under polish/ ---
  dir /b %RUN_DIR%\polish\*.mp4 >nul 2>&1
  if not errorlevel 1 (
    echo ====== %date% %time% SUCCESS on attempt %%i: polish output found ====== >> %LOG%
    echo [watchdog] polished output found, done.
    exit /b 0
  )
  echo [watchdog] attempt %%i ended without polish output, cooling down 10s...
  echo ====== %date% %time% attempt %%i ended WITHOUT output ====== >> %LOG%
  timeout /t 10 /nobreak >nul
)
echo [watchdog] %MAX% attempts exhausted - manual intervention needed. See %LOG%
exit /b 1
