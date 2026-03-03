@echo off
chcp 65001 >nul
title Additive Light Web Server
echo ---------------------------------------------------
echo 🚀 Запуск веб-сервера Additive Light...
echo ---------------------------------------------------
cd /d "%~dp0"
python server.py
pause
