@echo off
cd /d %~dp0..
dashboard\.venv312\Scripts\streamlit.exe run dashboard/app.py --server.port 8501
pause
