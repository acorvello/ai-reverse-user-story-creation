@echo off
setlocal
cd /d "%~dp0"
if errorlevel 1 (
    echo Nao foi possivel acessar a pasta do projeto.
    pause
    exit /b 1
)

python --version >nul 2>&1
if errorlevel 1 (
    echo Python nao encontrado. Instale o Python e habilite a opcao para adiciona-lo ao PATH.
    pause
    exit /b 1
)

set "APP_URL=http://127.0.0.1:8765"
curl.exe --fail --silent "%APP_URL%/api/health" | findstr.exe /c:"workspace" >nul
if not errorlevel 1 (
    echo A interface ja esta em execucao. Abrindo %APP_URL%
    start "" "%APP_URL%"
    exit /b 0
)

echo Iniciando a interface local...
start "AI Reverse User Story Creation - servidor" /D "%~dp0" python "%~dp0app.py"

for /l %%A in (1,1,30) do (
    curl.exe --fail --silent "%APP_URL%/api/health" | findstr.exe /c:"workspace" >nul
    if not errorlevel 1 (
        echo Servidor pronto. Abrindo %APP_URL%
        start "" "%APP_URL%"
        exit /b 0
    )
    ping.exe -n 2 127.0.0.1 >nul
)

echo O servidor nao respondeu no tempo esperado.
echo Verifique a janela "AI Reverse User Story Creation - servidor".
pause
exit /b 1
