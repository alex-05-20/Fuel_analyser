@echo off
setlocal
set "PYTHONDONTWRITEBYTECODE=1"
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Environnement Python du projet introuvable.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m ipykernel install --user --name fuel-analyser --display-name "Python - Fuel analyser"
if errorlevel 1 (
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m jupyterlab "notebooks\analyses.ipynb"
if errorlevel 1 pause
