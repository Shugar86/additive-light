#!/bin/bash
# Скрипт установки локальных Git хуков для команды
# Вызывается один раз: bash .github/install_hooks.sh

cp .github/pre-push .git/hooks/pre-push
chmod +x .git/hooks/pre-push

echo "✅ Локальная защита Git настроена: push напрямую в main/develop заблокирован."
echo "👉 Теперь можно безопасно работать в ветках feature/*."
