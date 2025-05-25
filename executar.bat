@echo off
REM Script para executar o Race Telemetry Analyzer no Windows
REM Este arquivo facilita a execução do aplicativo sem problemas de importação

echo ===== Race Telemetry Analyzer =====
echo Iniciando aplicativo...

REM Verifica se o Python está instalado
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERRO: Python não encontrado. Por favor, instale Python 3.8 ou superior.
    echo Você pode baixar Python em: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

REM Verifica se as dependências estão instaladas
echo Verificando dependências...
python -c "import PyQt6" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Instalando dependências necessárias...
    python -m pip install PyQt6 numpy matplotlib scipy pandas
)

REM Executa o aplicativo
python run.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Ocorreu um erro ao executar o aplicativo.
    echo Verifique se todas as dependências estão instaladas.
    echo.
    pause
)
