@echo off
REM TruthLens one-click launcher for Windows.
REM Double-click this file. The first run sets TruthLens up (a few minutes, needs internet once);
REM after that it opens TruthLens in your web browser. Close this window to stop TruthLens.
setlocal
title TruthLens
cd /d "%~dp0"
if not exist "pyproject.toml" if exist "truthlens\pyproject.toml" cd /d "%~dp0truthlens"
if not exist "pyproject.toml" (
  echo Could not find the TruthLens files. Keep this launcher inside the TruthLens folder.
  pause
  exit /b 1
)
set "SAMPLE=%CD%\samples\sample_report_v05.html"
if not exist "%SAMPLE%" set "SAMPLE=%CD%\samples\sample_report_v041.html"

REM 1. Find a stable Python 3.10-3.13. Newer or preview versions (3.14+) lack ready-made packages
REM    and fail to install without Microsoft C++ Build Tools, so they are used only as a last resort.
set "SYS_PY="
for %%V in (3.12 3.13 3.11 3.10) do (
  if not defined SYS_PY (
    py -%%V -c "import sys" >nul 2>nul && set "SYS_PY=py -%%V"
  )
)
if not defined SYS_PY (
  where python >nul 2>nul && python -c "import sys; sys.exit(0 if (3, 9) <= sys.version_info[:2] <= (3, 13) else 1)" >nul 2>nul && set "SYS_PY=python"
)
if not defined SYS_PY (
  where py >nul 2>nul && set "SYS_PY=py -3"
)
if not defined SYS_PY (
  echo.
  echo Python is not installed on this computer.
  echo   1. Go to https://www.python.org/downloads/ and install Python 3.12.
  echo   2. On the first install screen, tick "Add python.exe to PATH".
  echo   3. Double-click this launcher again.
  echo.
  echo Meanwhile, the sample report opens in your browser. It needs no internet.
  if exist "%SAMPLE%" start "" "%SAMPLE%"
  pause
  exit /b 1
)

REM 2. Create TruthLens's own Python environment in the .venv folder (first run only).
set "PY=%CD%\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo First run: setting up TruthLens. This takes a few minutes...
  %SYS_PY% -m venv .venv
  if errorlevel 1 (
    echo Could not create the Python environment. Copy the message above and ask your IT team.
    pause
    exit /b 1
  )
)

REM 2b. A .venv made earlier with Python 3.14+ cannot install; rebuild it with the Python found above.
if not "%SYS_PY%"=="py -3" "%PY%" -c "import sys; sys.exit(0 if sys.version_info[:2] <= (3, 13) else 1)" >nul 2>nul
if not "%SYS_PY%"=="py -3" if errorlevel 1 (
  echo Rebuilding the Python environment with %SYS_PY% ...
  rmdir /s /q .venv
  %SYS_PY% -m venv .venv
)

REM 3. Install TruthLens into it. "python -m pip" works even where pip.exe is blocked.
"%PY%" -c "import fastapi, uvicorn, truthlens.pipeline" >nul 2>nul
if errorlevel 1 (
  "%PY%" -m pip install --upgrade pip >nul 2>nul
  "%PY%" -m pip install -e ".[api]"
  if errorlevel 1 (
    echo.
    echo The install did not finish.
    echo If you see "Microsoft Visual C++ 14.0 or greater is required" above, install Python 3.12 from python.org,
    echo delete the .venv folder here, and double-click this launcher again.
    echo Otherwise it usually means no internet, or a proxy that blocks python.org.
    echo Try again on a network that allows it, or ask your IT team to allow "pypi.org".
    echo Meanwhile, the sample report opens in your browser. It needs no internet.
    if exist "%SAMPLE%" start "" "%SAMPLE%"
    pause
    exit /b 1
  )
)

REM 4. Start TruthLens and open the browser.
echo.
echo TruthLens is running at http://127.0.0.1:8765
echo Your browser will open in a moment. Keep this window open while you use TruthLens; close it to stop.
start "" /b cmd /c "timeout /t 4 >nul & start http://127.0.0.1:8765"
"%PY%" -m uvicorn truthlens.api:app --app-dir "%CD%" --host 127.0.0.1 --port 8765
pause
