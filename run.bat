@echo off
cd /d "%~dp0"
echo Instalando dependencias...
pip install -r requirements.txt -q
echo.
echo Iniciando Monitor de Tickers...
echo Abri tu navegador en http://localhost:8501
echo.
python -m streamlit run app.py --server.headless true
pause
