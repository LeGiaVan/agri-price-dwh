@echo off
echo ============================================
echo   AgriPrice Vietnam - Dashboard Setup
echo ============================================
echo.

REM Kiem tra Python 3.12
py -3.12 --version >nul 2>&1
if errorlevel 1 (
    echo [LOI] Chua co Python 3.12!
    echo Tai tai: https://www.python.org/downloads/release/python-31210/
    echo Sau do chay lai file nay.
    pause
    exit /b 1
)

echo [OK] Da tim thay Python 3.12
echo.

REM Tao virtual environment
echo [1/3] Tao virtual environment (.venv312)...
py -3.12 -m venv .venv312
if errorlevel 1 (
    echo [LOI] Khong tao duoc venv!
    pause
    exit /b 1
)
echo [OK] Tao venv thanh cong
echo.

REM Cai packages
echo [2/3] Cai dat packages...
.venv312\Scripts\pip.exe install -r requirements.txt --quiet
if errorlevel 1 (
    echo [LOI] Cai package that bai!
    pause
    exit /b 1
)
echo [OK] Cai packages xong
echo.

REM Kiem tra file .env
echo [3/3] Kiem tra file .env...
if not exist "..\\.env" (
    echo [CANH BAO] Chua co file .env o thu muc goc!
    echo Sao chep file .env.example thanh .env va dien token:
    echo   - MOTHERDUCK_TOKEN
    echo   - GROQ_API_KEY
    echo.
) else (
    echo [OK] Da co file .env
)

echo.
echo ============================================
echo   Setup hoan tat! Chay dashboard bang lenh:
echo.
echo   .venv312\Scripts\streamlit.exe run app.py
echo ============================================
echo.
pause
