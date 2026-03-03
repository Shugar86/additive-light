@echo off
chcp 65001 >nul
title OpenSCAD AI Desktop
echo ---------------------------------------------------
echo 🚀 Запуск десктопного ассистента OpenSCAD AI...
echo ---------------------------------------------------
cd /d "%~dp0\OpenSCAD_AI"
if exist gui_app.py (
    python gui_app.py
) else (
    echo ❌ Файл gui_app.py не найден в папке OpenSCAD_AI
    echo Пожалуйста, убедитесь, что папка скопирована корректно.
)
pause

