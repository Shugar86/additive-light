# Changelog

Все существенные изменения проекта документируются в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.0.0/),
а версионирование следует принципам [Semantic Versioning](https://semver.org/lang/ru/).

## [Unreleased]

### Added
- Полный polish документации: README, AGENTS, CONTRIBUTING, CHANGELOG приведены к единому вайбу и структуре 10/10.
- Badges/shields для лицензии, Python, black, pytest, OpenSCAD и OpenRouter.

### Changed
- README.md: hero-секция, структурированный быстрый старт, таблица архитектуры, детальное дерево проекта, примеры для веба, CLI и Python API.
- AGENTS.md: уточнён контракт агента, DoD, список remotes и правила эскалации.
- CONTRIBUTING.md: расширен чек-лист DoD для PR, добавлены примеры коммитов и список запрещённых артефактов.

## [0.4.0] - 2026-06-14

### Added
- Vibe-first документация: `README.md`, `AGENTS.md`, `LICENSE`, `CONTRIBUTING.md`, `CHANGELOG.md`.

## [0.3.0] - 2026-03-05

### Added
- Руководство по защите веток (`.github/BRANCH_PROTECTION_GUIDE.md`).
- Шаблон pull request'а (`.github/pull_request_template.md`).
- Руководство по совместной R&D-работе (`COLLABORATION.md`).

## [0.2.0] - 2026-03-03

### Added
- From Mock to Model sprint: интеграция LLM, песочница исполнения, геометрии прямоугольных профилей.

## [0.1.0] - 2026-03-03

### Added
- Начальная структура проекта: веб-приложение ADDITIVE_LAB, скелет GDI-пайплайна, базовые тесты.

## [11.1] - 2025-11-28 (Pro Update)

### Added
- **Web Worker:** рендеринг OpenSCAD перенесён в отдельный поток (`worker.js`).
  - Интерфейс больше не зависает при сложных расчётах.
  - Улучшена стабильность за счёт изоляции ядра.
- **Оптимизация:** добавлена директива `set_global_fn(50)` в AI-промпт для ускорения генерации в 2–3 раза.

### Fixed
- **Загрузка модулей:** исправлена ошибка `import.meta` путём использования динамического `import()` и Worker.
- **Скачивание:** исправлена логика формирования Blob для STL-файлов (корректные MIME-типы).

## [11.0] - 2025-11-28

### Added
- **OpenRouter Integration:** полный переход на OpenRouter API.
- **Локальный OpenSCAD:** движок рендеринга перенесён в локальные файлы (`openscad.wasm`, `openscad.min.js`).
- **Smart Validation:** трёхуровневая валидация AI-кода.
- **Server Headers:** обновлён `server.py` для поддержки заголовков COOP/COEP.

### Changed
- **UI:** кнопка "СКОМПИЛИРОВАТЬ" теперь имеет авто-ожидание загрузки движков.
- **Logic:** удалён "тихий откат" на примитивный парсер.
