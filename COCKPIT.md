# COCKPIT — additive-light _dev

## Who this project is (personality, 1-2 sentences)

**Слепой инженер с растущим набором измерительных инструментов.** Он наощупь исследует 3D-скан детерминированными «щупами», не притворяется, что видит всё, и когда инструмента не хватает — честно просит новый, вместо того чтобы нарисовать красивую ложь.

## How it feels (tone, vibe — for each layer/persona)

| Слой / персона | Vibe | Голос |
|---|---|---|
| **Deterministic core (v1)** | `calm`, `professional`, `methodical` | Сухой, точный, без магии. «RMSE 0.003 mm. Вот зоны. Вот STEP.» |
| **Spike Generator** | `honest`, `protective` | Не усредняет шпонку. «Здесь phi_variance выше порога — нужен `feature_detector_for_keyway`.» |
| **Sensors (align, slice, fit)** | `quiet`, `reliable` | Работают в тени; ошибка — только с числом и контекстом |
| **Coder / build123d** | `craftsman` | Параметрический скрипт как контракт с инженером, не black box |
| **Swarm (v2, dormant)** | `energetic`, `collaborative` [planned] | Команда специалистов включается по запросу ядра, не по умолчанию |
| **VibeGuard / Judge** | `skeptical`, `strict` | Проверяет геометрию; failure → reflection loop, не toxic positivity |
| **CAPP-lite (v3)** | `thoughtful`, `industrial` [planned] | «Как это, вероятно, делали?» — гипотеза маршрута, не догма |

## For whom (3 audiences)

1. **Инженер-конструктор / RE-оператор** — нужен редактируемый parametric CAD и измеримая точность, не mesh-аппроксимация от LLM.
2. **Deeptech / grant jury (Sber500)** — bench-driven demo: baseline-таблицы, one-command pipeline, явная архитектура «deterministic first».
3. **R&D / agent-архитектор** — расширяемый swarm, Skill Library, VibeCraft-персоны; v2 как платформа роста инструментов.

## Emotions it evokes

- **Доверие** — цифры воспроизводимы, отчёт JSON прозрачен
- **Уважение к границам** — out-of-scope не скрывается
- **Спокойная уверенность** — на ideal/real scan baseline hero numbers впечатляют без hype
- **Лёгкое нетерпение** — v2 ещё не fulfil'ит SkillRequest; потенциал swarm ощущается, но не включён
- **Инженерная гордость** — parametric script как «контракт», STEP как «артефакт»

## What makes it special (3-5 unique traits)

1. **Deterministic-first в мире LLM-CAD** — LLM не в critical path v1; измерения решают, а не «нарратив».
2. **Spike Generator как честная граница scope** — structured `SkillRequest` вместо silent smearing.
3. **Triple-pack на выходе** — STEP + build123d script + JSON report с метриками и skill requests.
4. **Bench-driven culture** — 36 STL, evil-shafts, real scan `Кнопка_2.stl`; спринты закрываются числами.
5. **Растущий toolkit (Voyager-style)** — инфраструктура skill bootstrap уже в репо, ждёт v2 activation.

## Current focus (one paragraph, link to STATE.md for blockers)

Sprint 0–4 закрыт: детерминированный pipeline тел вращения работает, Spike Generator детектирует out-of-scope и пишет запросы в report. **Сейчас — порог v2:** превратить `SkillRequest` из записи в JSON в реально исполняемый рост навыков (keyway, transverse hole) через `controlled_bootstrapper` и LangGraph coordinator. Тон продукта остаётся `calm` + `professional`: никаких обещаний «AI нарисует всё» — только измеримая реконструкция и явная эскалация. Блокеры и план шагов — в [STATE.md](STATE.md).
