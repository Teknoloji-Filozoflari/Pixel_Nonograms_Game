@echo off
setlocal
cd /d "%~dp0"
title Pixel Nonograms

set "GAME_PYTHON=%~dp0.venv\runtime\Scripts\python.exe"
if not exist "%GAME_PYTHON%" set "GAME_PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%GAME_PYTHON%" (
    echo Oyunun Python ortami bulunamadi.
    echo Lutfen bu dosyayi projenin ana klasorunden calistirin.
    pause
    exit /b 1
)

set "PYTHONPATH=%~dp0src;%PYTHONPATH%"
"%GAME_PYTHON%" -m pixel_nonograms
if errorlevel 1 (
    echo.
    echo Oyun acilirken bir hata olustu. Yukaridaki hata mesajini paylasabilirsiniz.
    pause
    exit /b 1
)
endlocal
