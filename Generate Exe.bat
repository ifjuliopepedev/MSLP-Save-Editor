@echo off
title Gerador de Executavel - MSLP Editor

echo [1/5] Entrando na pasta do projeto...
cd /d "%~dp0"

echo [2/5] Limpando arquivos antigos...
rd /s /q build 2>nul
rd /s /q dist 2>nul
del /f /q "*.spec" 2>nul

echo [3/5] Gerando executavel com PyInstaller...
python -m PyInstaller --noconfirm --onedir --windowed ^
--name "MSLPEditor" ^
--icon="Icon.ico" ^
--add-data "Icon.ico;." ^
--hidden-import customtkinter ^
--version-file version.txt ^
"MSLP Editor.pyw"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ###########################################
    echo [ERRO] Falha ao gerar executavel
    echo ###########################################
    pause
    exit /b
)

echo [4/5] Build concluida com sucesso!

echo [5/5] Finalizado!
echo Executavel em: dist\MSLPEditor.exe

pause
