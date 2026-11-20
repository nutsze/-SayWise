@echo off
rem Сборка Grasp одной командой: тесты -> Grasp.exe -> GraspSetup.exe -> portable zip (в dist\)
rem Аргументы передаются в build.py, например:  build.bat --skip-ui-matrix
chcp 65001 >nul
setlocal
cd /d "%~dp0"

if not exist .venv\Scripts\python.exe (
    echo Creating virtual environment .venv ...
    py -3.12 -m venv .venv || python -m venv .venv || goto :error
    .venv\Scripts\python.exe -m pip install --upgrade pip || goto :error
    .venv\Scripts\python.exe -m pip install -r requirements-dev.txt || goto :error
)

.venv\Scripts\python.exe build.py %* || goto :error
echo.
echo Done. Output: dist\
exit /b 0

:error
echo.
echo BUILD FAILED (code %errorlevel%)
exit /b 1
