@echo off
REM Creates a conda env "red-gui" (Python 3.11, which has CoolProp wheels), installs requirements, launches the GUI.
cd /d "%~dp0"
set CONDA_BAT=%USERPROFILE%\anaconda3\condabin\conda.bat
if not exist "%CONDA_BAT%" set CONDA_BAT=conda
call "%CONDA_BAT%" --version >nul 2>&1 || (
  echo Could not find conda. Run this from an Anaconda Prompt instead.
  exit /b 1
)
REM conda-forge avoids the Anaconda "defaults" channel Terms-of-Service prompt, which blocks -y installs.
call "%CONDA_BAT%" env list | findstr /b /c:"red-gui " >nul || call "%CONDA_BAT%" create -n red-gui -c conda-forge --override-channels python=3.11 -y || exit /b 1
call "%CONDA_BAT%" run -n red-gui --no-capture-output python -m pip install --upgrade pip || exit /b 1
call "%CONDA_BAT%" run -n red-gui --no-capture-output python -m pip install --only-binary=CoolProp -r requirements.txt || exit /b 1
call "%CONDA_BAT%" run -n red-gui --no-capture-output python GUI_MAIN.py
