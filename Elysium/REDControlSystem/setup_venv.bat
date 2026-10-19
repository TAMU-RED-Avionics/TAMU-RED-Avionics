@echo off
REM Creates .venv with Python 3.10+ (the GUI code needs 3.10), installs requirements, launches the GUI.
cd /d "%~dp0"
set PYEXE=
for %%V in (3.12 3.11 3.10) do (
  if not defined PYEXE (
    py -%%V -c "import sys" >nul 2>&1 && set PYEXE=py -%%V
  )
)
if not defined PYEXE (
  echo No Python 3.10-3.12 found. Install one from python.org, or use setup_conda.bat instead.
  exit /b 1
)
echo Using: %PYEXE%
if exist .venv\Scripts\python.exe (
  .venv\Scripts\python.exe -c "import sys; sys.exit(sys.version_info < (3,10))" || rmdir /s /q .venv
)
if not exist .venv\Scripts\python.exe %PYEXE% -m venv .venv || exit /b 1
.venv\Scripts\python.exe -m pip install --upgrade pip || exit /b 1
.venv\Scripts\python.exe -m pip install --only-binary=CoolProp -r requirements.txt || exit /b 1
.venv\Scripts\python.exe GUI_MAIN.py
