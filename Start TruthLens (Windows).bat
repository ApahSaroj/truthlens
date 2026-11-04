@echo off
REM Double-click to install (first time only) and open TruthLens in your browser.
REM Works from the project folder or from the folder the zip was unpacked into.
title TruthLens
set "VENV=%~dp0.venv"
cd /d "%~dp0"
if not exist "pyproject.toml" if exist "truthlens\pyproject.toml" cd /d "%~dp0truthlens"
if not exist "pyproject.toml" (
  echo Could not find the TruthLens files next to this launcher. Put it in the truthlens folder.
  pause
  exit /b 1
)
where python >nul 2>nul
if errorlevel 1 (
  echo Python is not installed. Get it from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
  pause
  exit /b 1
)
if not exist "%VENV%\Scripts\python.exe" (
  echo First run: setting up TruthLens. This takes a few minutes...
  python -m venv "%VENV%"
)
set "PY=%VENV%\Scripts\python.exe"
"%PY%" -c "import fastapi, uvicorn, truthlens.pipeline" >nul 2>nul
if errorlevel 1 (
  "%PY%" -m pip install -e ".[api]"
  if errorlevel 1 (
    echo Install failed. Copy the error above and ask for help.
    pause
    exit /b 1
  )
)
REM 3b. Optional (v0.7): "match by meaning" in the compare tab. Tried once; if it cannot install
REM     (no Windows package for this Python, no internet), TruthLens works without it.
if not exist "%VENV%\meaning-tried.txt" (
  "%PY%" -c "import fastembed" >nul 2>nul
  if errorlevel 1 (
    echo Adding the optional "match by meaning" feature, about 145 MB. This is tried once...
    "%PY%" -m pip install -e ".[api,meaning]" >nul 2>nul
    if errorlevel 1 (
      echo The optional "match by meaning" feature could not be installed. TruthLens works without it.
    ) else (
      echo "Match by meaning" is installed. Its model, 67 MB, downloads the first time you use it.
    )
  )
  echo tried> "%VENV%\meaning-tried.txt"
)
echo.
echo TruthLens is running. Your browser will open in a moment.
echo Keep this window open while you use it. Close it to stop TruthLens.
start "" /b cmd /c "timeout /t 4 >nul & start http://127.0.0.1:8765"
"%PY%" -m uvicorn truthlens.api:app --app-dir "%CD%" --host 127.0.0.1 --port 8765
pause
