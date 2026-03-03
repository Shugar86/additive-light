#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import http.server
import socketserver
import os
import sys
import mimetypes

# Добавляем правильный MIME-тип для WASM
mimetypes.init()
mimetypes.add_type('application/wasm', '.wasm')

PORT = 8001

# Переходим в директорию скрипта
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

print(f"Рабочая директория: {os.getcwd()}")
print(f"Файлы в директории: {os.listdir('.')}")

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Добавляем заголовки для корректной работы SharedArrayBuffer (требуется для некоторых WASM)
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        # Отключаем кеширование для разработки
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

Handler = CustomHandler

try:
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"\n{'='*50}")
        print(f"✅ Сервер запущен на http://localhost:{PORT}")
        print(f"{'='*50}")
        print("Нажмите Ctrl+C для остановки\n")
        httpd.serve_forever()
except OSError as e:
    if "Address already in use" in str(e) or "уже используется" in str(e):
        print(f"❌ Порт {PORT} уже занят!")
        print("Остановите другой процесс или используйте другой порт")
    else:
        print(f"❌ Ошибка: {e}")
    sys.exit(1)
except KeyboardInterrupt:
    print("\n\nСервер остановлен")
    sys.exit(0)

