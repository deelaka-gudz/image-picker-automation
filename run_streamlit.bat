@echo off
REM Wrapper for Windows Task Scheduler. Launches the Streamlit app directly
REM from .venv, independent of VS Code, so it survives a PC restart without
REM anyone needing to reopen a terminal and re-run it manually.
cd /d "%~dp0"
".venv\Scripts\streamlit.exe" run app.py --server.port 8508 --server.headless true
