@echo off
rem ============================================================================
rem  AEC Drawing Intelligence - one-click setup and run (Windows 10 / 11)
rem
rem  Double-click this file. It will:
rem    1. find Python 3.12-3.14, or download a private portable Python 3.12
rem       into this folder (no admin rights, nothing installed system-wide)
rem    2. install the required packages (internet needed the first time)
rem    3. run the automated tests
rem    4. analyse the sample project and open the output folder
rem    5. open the review screen in your web browser
rem
rem  Options:   RUN.bat eval      also run the full synthetic benchmark (~3 min)
rem             RUN.bat nobrowser setup + tests + analysis only
rem ============================================================================
setlocal EnableExtensions EnableDelayedExpansion
title AEC Drawing Intelligence

set "APP=%~dp0aec-drawing-intelligence"
if not exist "%APP%\src\aecdi" (
    echo [ERROR] The folder "aec-drawing-intelligence" must be next to RUN.bat.
    pause
    exit /b 1
)
cd /d "%APP%"
set "LOG=%APP%\setup_log.txt"
set "PYVER=3.12.10"
set "RUNTIME=%APP%\.runtime\python"
set "PORT=8501"
if defined AECDI_PORT set "PORT=%AECDI_PORT%"
set "PY="
set "RUNPY="
set "PIP_DISABLE_PIP_VERSION_CHECK=1"
set "PYTHONUTF8=1"

echo.
echo  ==================================================================
echo    AEC Drawing Intelligence - setup and run
echo  ==================================================================
echo.

rem ---------------------------------------------------------------- 1. Python
echo  [1/5] Looking for Python 3.12 - 3.14 ...
if /i "%AECDI_PRIVATE_PYTHON%"=="1" goto private_python
if exist "%RUNTIME%\python.exe" goto private_python
call :try_python python
if not defined PY call :try_python "py -3.14"
if not defined PY call :try_python "py -3.13"
if not defined PY call :try_python "py -3.12"
if defined PY goto use_venv

:private_python
if exist "%RUNTIME%\python.exe" goto private_ready
echo        No suitable Python found. Downloading portable Python %PYVER% into this folder...
if not exist "%APP%\.runtime" mkdir "%APP%\.runtime"
call :download "https://www.python.org/ftp/python/%PYVER%/python-%PYVER%-embed-amd64.zip" "%APP%\.runtime\python.zip"
if errorlevel 1 goto fail_download
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath '%APP%\.runtime\python.zip' -DestinationPath '%RUNTIME%' -Force" >> "%LOG%" 2>&1
if not exist "%RUNTIME%\python.exe" goto fail_download
rem enable site-packages and make the source folder importable (paths are relative to the ._pth file)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p = Get-ChildItem -LiteralPath '%RUNTIME%' -Filter 'python*._pth' | Select-Object -First 1; $c = (Get-Content -LiteralPath $p.FullName) -replace '^#\s*import site','import site'; $c += '..\..\src'; Set-Content -LiteralPath $p.FullName -Value $c -Encoding ascii" >> "%LOG%" 2>&1
call :download "https://bootstrap.pypa.io/get-pip.py" "%APP%\.runtime\get-pip.py"
if errorlevel 1 goto fail_download
"%RUNTIME%\python.exe" "%APP%\.runtime\get-pip.py" --no-warn-script-location >> "%LOG%" 2>&1
if errorlevel 1 goto fail_install
del /q "%APP%\.runtime\python.zip" "%APP%\.runtime\get-pip.py" >nul 2>&1
:private_ready
set "RUNPY=%RUNTIME%\python.exe"
echo        Using portable Python in .runtime\python
goto install

:use_venv
echo        Using %PY%
if not exist "%APP%\.venv\Scripts\python.exe" (
    echo        Creating a virtual environment in .venv ...
    %PY% -m venv "%APP%\.venv" >> "%LOG%" 2>&1
)
if not exist "%APP%\.venv\Scripts\python.exe" goto fail_install
set "RUNPY=%APP%\.venv\Scripts\python.exe"
set "PYTHONPATH=%APP%\src"

rem ---------------------------------------------------------------- 2. packages
:install
echo  [2/5] Installing required packages (first run: a few minutes) ...
"%RUNPY%" -m pip install --upgrade pip --no-warn-script-location >> "%LOG%" 2>&1
"%RUNPY%" -m pip install --no-warn-script-location -r "%APP%\requirements.txt" >> "%LOG%" 2>&1
if errorlevel 1 goto fail_install
echo        Packages ready.

rem ---------------------------------------------------------------- 3. tests
echo  [3/5] Running the automated tests ...
"%RUNPY%" -m unittest discover -s "%APP%\tests" -p "test_*.py" > "%APP%\test_log.txt" 2>&1
if errorlevel 1 (
    echo        WARNING: some tests failed - see test_log.txt. Continuing.
) else (
    for /f "tokens=*" %%L in ('findstr /b /c:"Ran " "%APP%\test_log.txt"') do echo        %%L - all passed
)

rem ---------------------------------------------------------------- 4. analysis
echo  [4/5] Analysing the sample project ...
"%RUNPY%" -m aecdi.cli run "%APP%\sample_project" --out "%APP%\out"
if errorlevel 1 goto fail_run
if /i "%~1"=="eval" (
    echo        Running the synthetic benchmark, this takes a few minutes ...
    "%RUNPY%" -m aecdi.cli eval
)
start "" "%APP%\out"

rem ---------------------------------------------------------------- 5. review screen
if /i "%~1"=="nobrowser" goto done
echo  [5/5] Starting the review screen at http://localhost:%PORT%
echo        Your browser opens in a few seconds. Close this window or press Ctrl+C to stop.
echo.
start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 8; Start-Process 'http://localhost:%PORT%'"
"%RUNPY%" -m streamlit run "%APP%\ui\review_app.py" --server.headless true --server.port %PORT% --browser.gatherUsageStats false -- "%APP%\out"
goto done

rem ---------------------------------------------------------------- helpers
:try_python
%~1 -c "import sys; sys.exit(0 if (3, 12) <= sys.version_info[:2] <= (3, 14) else 1)" >nul 2>&1
if not errorlevel 1 set "PY=%~1"
exit /b 0

:download
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $ProgressPreference = 'SilentlyContinue'; Invoke-WebRequest -Uri '%~1' -OutFile '%~2' -UseBasicParsing" >> "%LOG%" 2>&1
if exist "%~2" exit /b 0
curl.exe -L -s -o "%~2" "%~1" >> "%LOG%" 2>&1
if exist "%~2" exit /b 0
exit /b 1

:fail_download
echo.
echo  [ERROR] Could not download Python. Check the internet connection (or proxy) and run again.
echo          Details: setup_log.txt
goto end_error
:fail_install
echo.
echo  [ERROR] Package installation failed. Check the internet connection and see setup_log.txt.
goto end_error
:fail_run
echo.
echo  [ERROR] The analysis did not complete. See the messages above.
goto end_error

:done
echo.
echo  Done. Outputs are in aec-drawing-intelligence\out
pause
exit /b 0

:end_error
pause
exit /b 1
