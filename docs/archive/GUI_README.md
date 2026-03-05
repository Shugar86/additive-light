# GDI Desktop GUI

Профессиональный интерфейс для Generative Design Intelligence.

## Внешний вид

- **Темная тема** в стиле инженерных CAD-приложений
- **Три панели:**
  1. Выбор файла и настройки
  2. Результаты анализа (zones, confidence)
  3. YAML telemetry preview

## Быстрый старт

```bash
# Установить PyQt6 (один раз)
pip install PyQt6

# Запуск
python launch_gui.py
# или
python -m gdi_app.gui.main_window
```

## Функционал

### 1. Выбор модели
- Drag & drop или Browse
- Отображение имени файла
- Автоматическая валидация STL

### 2. Настройки анализа
- **Build Axis:** Z (вертикаль), Y, X
- **Slice Step:** шаг среза (0.1 mm по умолчанию)
- **Min Confidence:** порог уверенности (0.7 = 70%)

### 3. Результаты
- **Global Confidence:** общая уверенность (цветовая индикация)
  - Зеленый: >= 90%
  - Желтый: 70-90%
  - Красный: < 70%
- **Detected Zones:** таблица с детекцией
  - Zone ID
  - Geometry type
  - Confidence per zone
- **YAML Preview:** полный телеметрий

### 4. Выходные файлы
Результаты сохраняются в `output/`:
- `{model}_telemetry.yaml` - полный YAML
- `manifests/{date}/{run_id}.json` - манифест

## Пример использования

1. Загрузите `benchmark_kit/ideal/ideal_cylinder.stl`
2. Нажмите "Analyze Geometry"
3. Ожидаемый результат:
   - Global Confidence: 100%
   - 1 Zone: Constant_Profile (Circle)
   - YAML с параметрами (radius=20mm, height=40mm)

## Статусы

- **Success:** Анализ завершен, confidence выше порога
- **Manual Review Required:** Низкая уверенность, требуется проверка
- **Error:** Проблема с файлом или pipeline

## Клавиатурные сокращения

- `Ctrl+O` - Открыть файл
- `Ctrl+Q` - Выход
