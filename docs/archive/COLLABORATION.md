# Совместная работа — additive-light

Репозиторий: https://github.com/Shugar86/additive-light  
Участники: **Shugar86** (владелец) · **temixx_** (коллега)

---

## Структура веток

```
main          ← продакшн, только стабильный код
  └── develop ← интеграционная ветка, сюда мержим фичи
        ├── feature/temixx-<описание>   ← ветки коллеги
        └── feature/shugar-<описание>   ← твои ветки
```

**Правила:**
- `main` — только через PR из `develop`, требует 1 approve
- `develop` — только через PR из `feature/*`, требует 1 approve
- Прямые коммиты в `main` и `develop` **запрещены**

---

## Workflow: шаг за шагом

### Начало работы над задачей

```bash
# Всегда стартуй от свежего develop
git checkout develop
git pull origin develop

# Создай ветку с префиксом своего никнейма
git checkout -b feature/shugar-openscad-geometry
```

### В процессе работы

```bash
# Коммить маленькими логичными кусками
git add .
git commit -m "feat(gdi_core): add cylinder geometry parser"

# Пуш ветки на remote
git push origin feature/shugar-openscad-geometry
```

### Конвенция коммитов

Формат: `<тип>(<область>): <что сделано>`

| Тип | Когда |
|-----|-------|
| `feat` | новая функциональность |
| `fix` | исправление бага |
| `refactor` | рефакторинг без изменения поведения |
| `test` | добавление/правка тестов |
| `docs` | только документация |
| `chore` | зависимости, конфиг, .gitignore |

Примеры:
```
feat(gdi_core): add support for torus geometry
fix(web): correct camera orbit on mobile touch
refactor(OpenSCAD_AI): extract geometry validator into separate class
```

### Pull Request

1. Открыть PR на GitHub: `feature/shugar-...` → `develop`
2. Заполнить темплейт (заполняется автоматически)
3. Назначить коллегу ревьюером
4. После 1 approve — мержить **Squash and Merge**
5. Удалить feature-ветку после мержа

### Релиз в main

Когда `develop` стабилен:
```
develop → main (PR, 1 approve, Squash and Merge)
```
После мержа — создать тег версии:
```bash
git tag -a v1.2.0 -m "Release v1.2.0: ..."
git push origin v1.2.0
```

---

## Синхронизация с коллегой

```bash
# Посмотреть что есть на remote
git fetch origin

# Забрать изменения из develop (делать регулярно)
git checkout develop
git pull origin develop

# Ребейз своей фичи на свежий develop (чтобы не было конфликтов в PR)
git checkout feature/shugar-openscad-geometry
git rebase develop
```

---

## Зоны ответственности

| Область | Файлы/папки | Первичный ответственный |
|---------|-------------|------------------------|
| GDI Core (геометрия, рендер) | `gdi_core/`, `mesh/` | обсудить |
| OpenSCAD AI интеграция | `OpenSCAD_AI/` | обсудить |
| Web-интерфейс | `web/`, `index.html`, `script.js`, `style.css` | обсудить |
| Тесты и бенчмарки | `tests/`, `benchmark_kit/`, `test_manifests/` | оба |
| Сервер и деплой | `server.py`, `nginx_*.conf`, `DEPLOY.md` | обсудить |

> Если правишь чужую зону ответственности — **предупреди в чате** перед коммитом.

---

## Решение конфликтов

1. Регулярный `git rebase develop` минимизирует конфликты
2. При конфликте — решаем голосом/в чате, не ломаем молча чужой код
3. Если не уверен — создай черновой PR и попроси review

---

## Локальная настройка (один раз)

```bash
git config user.name "ТвойНикнейм"
git config user.email "твой@email.com"

# Защита от случайных пушей в main/develop
bash .github/install_hooks.sh
```
