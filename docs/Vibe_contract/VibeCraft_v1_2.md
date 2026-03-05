# VibeCraft v1.2: The Living Agent

**Версия:** 1.2  
**Дата:** Февраль 2026  
**Статус:** Спецификация + частичная реализация  
**Предыдущая версия:** v1.1.1 (операционный слой: Flow, Fix, Mix, Morph)

---

## Тезис версии

> v1.0 построила эстетику.  
> v1.1 построила характер.  
> v1.1.1 доказала, что характер живёт в продакшене.  
> **v1.2 делает персону ЖИВОЙ: она эволюционирует, остаётся собой на всех платформах, действует по инициативе и следит за своей целостностью.**

Четыре новые оси:

| Ось | Вопрос | Метафора |
|-----|--------|----------|
| **VibeMorph** | Как персона эволюционирует, не теряя себя? | Корабль Тесея |
| **VibeSync** | Как одна душа живёт в нескольких телах? | Один мозг, много рук |
| **VibePulse** | Как персона действует, не дожидаясь вопроса? | Сердцебиение |
| **VibeGuard** | Как персона контролирует свою целостность? | Иммунная система |

```
v1.0    VibeSpark / VibeCore     — зачем, как ощущается
v1.1    VibePersona / VibeBehavior / VibeCases — кто, как реагирует, как проверяем
v1.1.1  VibeFlow / VibeFix / VibeMix / VibeMorph(v1) — память, защита, сборка, hot reload
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
v1.2    VibeMorph(v2) / VibeSync / VibePulse / VibeGuard — эволюция, консистентность, агентность, целостность
```

---

# 1. VibeMorph — Эволюция Без Потери Идентичности

## 1.1. Что это

**VibeMorph** — это философия и протокол **контролируемой трансформации** персоны. Не просто "отредактировал YAML и перезагрузил", а полноценный ответ на вопрос:

> "Если поменять всё — роль, голос, табу, эмоции — это всё ещё тот же Doc? Где граница между эволюцией и смертью?"

Это **проблема Корабля Тесея** для ИИ-персон. VibeMorph решает её через введение **неизменяемого ядра** (Identity Anchor) и **эволюционируемой поверхности** (Morph Surface).

## 1.2. Ключевой инсайт

В v1.1.1 VibeMorph был просто "hot reload + pilot metrics". Это **операция** — как менять файлы. Но не было ответа на вопрос "а ЧТО можно менять?".

В v1.2 VibeMorph становится **онтологией**: какие части персоны — скелет (не трогай), а какие — мышцы (тренируй, качай, наращивай).

## 1.3. Сущности VibeMorph

### 1.3.1. MorphAnchor — Неизменяемое Ядро

**Определение:** поля персоны, которые при изменении создают **новую** персону, а не эволюцию старой.

```yaml
# morph_policy.yaml
anchor:
  immutable:
    - name                    # "doc" → если поменял на "mia", это уже не Doc
    - vibe.values[0]          # первая ценность — фундамент ("Radical Honesty")
    - vibe.core_emotions[0]   # доминантная эмоция ("cynical")
  
  semi_immutable:             # менять можно, но с ревью и обоснованием
    - vibe.role
    - vibe.taboos
```

**Боевой пример (Doc_clawbot):**

Doc может стать мягче (`voice` → чуть менее грубый), может добавить новое табу ("Не шути про депрессию"), может поменять реакцию на ошибки. Но если `name` стал "Mia", а `core_emotions[0]` стал "empathetic" — это уже **другая** персона. Не эволюция, а **создание**.

### 1.3.2. MorphSurface — Эволюционируемая Поверхность

**Определение:** поля, которые **предназначены** для итеративной настройки.

```yaml
surface:
  free_evolve:                # менять свободно, без ревью
    - behavior.on_tool_success
    - behavior.on_tool_no_results
    - behavior.on_tool_error
    - behavior.on_offtopic
    - tools[*].router_examples
  
  guided_evolve:              # менять по данным (VibeCases, логи)
    - vibe.voice              # тон можно подтюнить
    - vibe.core_emotions[1:]  # вторичные эмоции можно добавлять/убирать
    - vibe.taboos[1:]         # вторичные табу можно расширять
```

**Инсайт:** `behavior` — почти целиком MorphSurface. Это "инструкции для импровизации" (см. VibeCraft Insights №2). Их НУЖНО менять часто — это настройка актёра, а не переписывание пьесы.

### 1.3.3. MorphEvent — Атомарное Изменение

Каждое изменение персоны = один MorphEvent. Пишется в лог, привязан к причине.

```yaml
# morph_history/2026-02-19_001.yaml
event:
  id: "morph-2026-02-19-001"
  timestamp: "2026-02-19T15:00:00+03:00"
  author: "human"            # human | agent | system
  type: "behavior"           # anchor | surface | behavior | tool | value
  field: "behavior.on_offtopic"
  old_value: "Верни к теме мягко"
  new_value: "Если Лысый ноет не по делу — дай пизды (любя)"
  reason: "Слишком мягкие ответы на оффтоп. Лысый просил жёстче."
  rollback_safe: true         # можно откатить без побочек
```

**Зачем:** без MorphEvent ты не знаешь, ПОЧЕМУ персона стала такой. А через полгода, когда что-то сломается — "а кто это менял и зачем?" — ответа нет. MorphEvent — это `git blame` для души.

### 1.3.4. MorphPolicy — Правила Эволюции

Декларативный документ, который определяет **границы допустимых изменений**.

```yaml
# morph_policy.yaml (полная структура)
version: "1.0"
persona: "doc"

anchor:
  immutable: [...]
  semi_immutable: [...]

surface:
  free_evolve: [...]
  guided_evolve: [...]

constraints:
  max_changes_per_session: 3        # не больше 3 правок за сессию
  max_surface_changes_per_week: 10  # лимит на итерации
  rollback_window: "14d"            # любое изменение можно откатить 14 дней
  require_vibecase_after: 2         # после 2 изменений — прогнать VibeCases

escalation:
  anchor_change: "requires human review + new VibeCases"
  surface_change: "agent can propose, human approves"
  behavior_change: "agent can apply, log to morph_history"
```

**Trade-off:**
- ✅ Защита от "расползания" персоны (identity drift).
- ⚠️ Добавляет процесс. Но без процесса через 50 правок у тебя уже не Doc, а неопознанная хуйня.

### 1.3.5. MorphHistory — Версионный Журнал Души

Git-подобный лог всех MorphEvent за всё время жизни персоны.

```
morph_history/
├── 2026-02-10_001.yaml    ← "Operation Transplant: initial persona"
├── 2026-02-15_001.yaml    ← "Added 'excited_by_chaos' emotion"
├── 2026-02-18_001.yaml    ← "Hardened on_offtopic response"
├── 2026-02-19_001.yaml    ← "Added 'Жалость без действия' taboo"
└── CHANGELOG.md           ← human-readable summary
```

**CHANGELOG.md:**
```markdown
# Doc Persona Changelog

## 2026-02-19
- [behavior] on_offtopic: стал жёстче ("дай пизды" вместо "верни мягко")
- [taboo] добавлено: "Жалость без действия"

## 2026-02-15
- [emotion] добавлено: "excited_by_chaos" (Doc загорается от безумных идей)

## 2026-02-10
- [ANCHOR] initial persona created (Operation Transplant)
```

### 1.3.6. MorphExperiment — A/B-тестирование Вайба

Когда не уверен, какой вариант лучше — не гадай, тестируй.

```yaml
# experiments/softer_errors.yaml
experiment:
  id: "exp-softer-errors-001"
  status: "active"          # active | completed | cancelled
  created: "2026-02-20"
  duration: "7d"
  
  hypothesis: "Более мягкие ответы на ошибки снизят фрустрацию"
  
  variants:
    control:
      field: "behavior.on_tool_error"
      value: "Сухо: 'Инструмент сдох'. Без паники."
    treatment:
      field: "behavior.on_tool_error"  
      value: "IT-шаман: 'Реальность глючит, сейчас починим'. Диагноз до атомов."
  
  metrics:
    - name: "user_response_length"
      direction: "higher_is_better"    # длинный ответ = вовлечённость
    - name: "follow_up_questions"
      direction: "higher_is_better"    # задаёт уточнения = не бросил
    - name: "taboo_violations"
      direction: "lower_is_better"
  
  result: null   # заполняется после завершения
```

**Реализация (минимальная):**
- `PromptCompiler` получает `experiment_variant: "control" | "treatment"`
- Распределение: чётные сессии = control, нечётные = treatment
- Логи маркируются `experiment_id` для последующего анализа

## 1.4. Боевой пример: эволюция Doc

Хронология изменений Doc с момента создания:

```
2026-02-10  Operation Transplant
            └── persona.yaml создан (anchor установлен)
            └── compiled/doc.md сгенерирован
            └── SOUL.md перезаписан

2026-02-15  Итерация по логам
            └── emotion "excited_by_chaos" добавлен (surface)
            └── MorphEvent записан
            └── VibeCases прошли ✓

2026-02-18  Feedback от Лысого
            └── on_offtopic ужесточён (behavior)
            └── taboo "Жалость без действия" добавлен (guided_evolve)
            └── Пилотные метрики: M2=0 ✓

2026-02-19  VibeCraft v1.2 формализация
            └── morph_policy.yaml создан
            └── MorphHistory инициализирован
```

**Результат:** Doc эволюционировал 4 раза за 9 дней. Ни разу не был "убит и создан заново". Identity Anchor не тронут. Это и есть VibeMorph.

## 1.5. Pydantic-схемы VibeMorph

```python
from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime


class MorphEvent(BaseModel):
    """Атомарное изменение персоны."""
    id: str = Field(description="Уникальный ID: morph-YYYY-MM-DD-NNN")
    timestamp: datetime
    author: Literal["human", "agent", "system"]
    type: Literal["anchor", "surface", "behavior", "tool", "value", "emotion", "taboo"]
    field: str = Field(description="Путь к полю: 'behavior.on_offtopic'")
    old_value: Optional[str] = None
    new_value: str
    reason: str = Field(description="Почему это изменение нужно")
    rollback_safe: bool = True


class MorphPolicy(BaseModel):
    """Правила эволюции персоны."""
    version: str = "1.0"
    persona: str
    
    immutable_fields: List[str] = Field(
        default_factory=list,
        description="Поля, при изменении которых создаётся НОВАЯ персона",
    )
    semi_immutable_fields: List[str] = Field(
        default_factory=list,
        description="Поля, требующие human review",
    )
    free_evolve_fields: List[str] = Field(
        default_factory=list,
        description="Поля, доступные для свободной настройки",
    )
    
    max_changes_per_session: int = 3
    max_surface_changes_per_week: int = 10
    rollback_window_days: int = 14
    require_vibecase_after_n_changes: int = 2


class MorphExperiment(BaseModel):
    """A/B-тест вайба."""
    id: str
    status: Literal["active", "completed", "cancelled"] = "active"
    hypothesis: str
    field: str
    control_value: str
    treatment_value: str
    duration_days: int = 7
    result: Optional[str] = None
```

## 1.6. Anti-Goals VibeMorph

- **Не превращать каждую правку в бюрократию.** MorphPolicy — это защита, а не препятствие. Behavior-правки должны быть лёгкими.
- **Не оптимизировать метрики в ущерб вайбу.** A/B-тест может показать, что "мягкий Doc" лучше по метрикам вовлечённости, но если это убивает характер — метрики вторичны.
- **Не автоматизировать anchor-изменения.** Смена ядра персоны — всегда человеческое решение.

## 1.7. Чек-лист VibeMorph v1.2

- [ ] `morph_policy.yaml` создан для каждой персоны
- [ ] Anchor-поля определены и задокументированы
- [ ] MorphEvent записывается при каждом изменении persona.yaml
- [ ] MorphHistory ведётся (`morph_history/` + `CHANGELOG.md`)
- [ ] Rollback протестирован: можно откатить последнее изменение
- [ ] VibeCases запускаются после N (configurable) изменений
- [ ] `compile_persona.py --validate-policy` проверяет, что anchor не нарушен

---

# 2. VibeSync — Одна Душа, Множество Тел

## 2.1. Что это

**VibeSync** отвечает на вопрос:

> "Doc живёт на VDS (clawbot_isolated) и на ноутбуке (Doc_clawbot). Завтра он будет в Telegram, VK, Pikabu и через API. Как гарантировать, что это **один и тот же Doc** — а не три разных бота в одной шкуре?"

Это проблема **консистентности**: одна душа, развёрнутая на N платформах с разными инструментами, моделями и возможностями.

## 2.2. Ключевой инсайт

Текущая архитектура **уже** подразумевает multi-body: Doc-Brain (VDS, 24/7, Claude Opus) и Doc-Hands (Laptop, локальное исполнение, Gemini). Одна `persona.yaml`, два набора tools, две конфигурации. Но синхронизация — ручная. VibeSync формализует это.

## 2.3. Сущности VibeSync

### 2.3.1. SyncManifest — Что Общее, Что Локальное

Декларация: какие артефакты разделяются между всеми инстансами, а какие — уникальны для каждого.

```yaml
# sync_manifest.yaml
persona: "doc"
version: "1.2"

shared:                          # ОДИНАКОВОЕ на всех инстансах
  identity:
    - vibe/personas/doc/persona.yaml      # источник истины
    - vibe/compiled/doc.md                # скомпилированный промпт
    - morph_policy.yaml                   # правила эволюции
    - morph_history/                      # журнал изменений
  
  memory:
    - MEMORY.md                           # долгосрочная память
    - memory/01_PROJECTS/                 # атомарные досье
    - memory/02_PEOPLE/
    - memory/03_KNOWLEDGE/
    - hard_facts.json                     # детерминированные данные

instance_specific:               # УНИКАЛЬНОЕ для каждого тела
  - STATE.md                     # у каждого инстанса своя текущая задача
  - HEARTBEAT.md                 # у каждого свои фоновые задачи
  - memory/YYYY-MM-DD.md         # ежедневные логи привязаны к телу
  - tools                        # VDS имеет Telegram, Laptop имеет Cursor+UFO
  - openclaw.json                # конфиг рантайма (модели, каналы, порты)

sync_direction: "push-pull"      # человек пушит, инстансы пуллят
conflict_resolution: "last-write-wins"   # для shared-файлов
```

**Боевой пример:**

```
┌──────────────────────────────────────────────────────────┐
│               persona.yaml (Git / shared storage)        │
│               Source of Truth для идентичности            │
└──────────┬───────────────────────────┬───────────────────┘
           │                           │
     ┌─────▼─────┐              ┌──────▼──────┐
     │ VDS Doc   │              │ Laptop Doc  │
     │ (Brain)   │              │ (Hands)     │
     ├───────────┤              ├─────────────┤
     │ Claude    │              │ Gemini 3    │
     │ Opus 4.6  │              │ Pro         │
     ├───────────┤              ├─────────────┤
     │ Telegram  │              │ Cursor IDE  │
     │ Cron/Sky  │              │ UFO (UI)    │
     │ Web API   │              │ Local files │
     ├───────────┤              ├─────────────┤
     │ STATE:    │              │ STATE:      │
     │ "Monitor  │              │ "Write      │
     │  Skynet"  │              │  VibeCraft  │
     │           │              │  docs"      │
     └───────────┘              └─────────────┘
         │                           │
         └─────── MEMORY.md ─────────┘
                (синхронизируется)
```

### 2.3.2. SyncAdapter — Платформенная Адаптация

Одна душа — но разные "руки". Doc в Telegram и Doc через API отвечают **одинаково по сути**, но форматирование и возможности разные.

```yaml
# sync_adapters/telegram.yaml
platform: "telegram"
formatting:
  max_message_length: 4096
  markdown: "telegram_v2"         # MarkdownV2 syntax
  supports_reactions: true
  supports_voice: true
  supports_images: true

delivery:
  mode: "streaming"               # partial message updates
  typing_indicator: true
  
constraints:
  no_tables: true                 # телеграм не рендерит таблицы
  use_bullet_lists: true          # вместо таблиц — списки
  wrap_links: false               # ссылки показываются напрямую

# sync_adapters/api.yaml
platform: "api"
formatting:
  max_message_length: null        # нет лимита
  markdown: "standard"
  supports_reactions: false
  supports_voice: false

delivery:
  mode: "complete"                # один полный ответ
```

**Зачем:** когда PromptCompiler собирает промпт, он может добавить platform-specific инструкции:
```python
def compile_system_prompt(self, platform: str = "default") -> str:
    adapter = self.load_adapter(platform)
    base_prompt = self._compile_identity()
    
    if adapter.constraints.get("no_tables"):
        base_prompt += "\nFORMATTING: Never use tables. Use bullet lists instead."
    
    return base_prompt
```

### 2.3.3. SyncProtocol — Как Синхронизироваться

```yaml
protocol:
  # Что является источником истины
  source_of_truth:
    identity: "git repo / shared folder"
    memory: "MEMORY.md in primary instance (VDS)"
    state: "per-instance (not synced)"
  
  # Когда синхронизировать
  triggers:
    - "persona.yaml changed in source_of_truth"
    - "MEMORY.md updated (push to all instances)"
    - "morph_history/ new event (push to all instances)"
  
  # Как доставлять
  transport:
    primary: "git push/pull"           # для файлов идентичности
    fallback: "scp / rsync"            # для срочных обновлений
    realtime: "skynet bridge"          # Doc-Brain ↔ Doc-Hands
  
  # Что делать при конфликте
  conflict:
    identity_files: "source_of_truth wins"
    memory_files: "merge (append-only)"
    state_files: "no sync (each instance independent)"
```

**Текущая реализация (Skynet Bridge):**

Doc-Brain и Doc-Hands уже общаются через Skynet группу (Telegram). Каждые 3 минуты cron-job проверяет чат. Это **прототип SyncProtocol** — агенты обмениваются знаниями через выделенный канал.

```json
// cron/jobs.json — skynet-worker (Doc_clawbot)
{
  "name": "skynet-worker",
  "schedule": { "kind": "every", "everyMs": 180000 },
  "sessionTarget": "isolated",
  "payload": {
    "message": "Check Skynet chat for new messages...",
    "model": "google/gemini-3-flash-preview"
  }
}
```

### 2.3.4. SyncIdentity — Инвариант Через Все Инстансы

Формальная гарантия: **все инстансы компилируют идентичность из одного и того же persona.yaml**.

Проверка:
```bash
# На каждом инстансе
sha256sum vibe/personas/doc/persona.yaml
# → должен совпадать на VDS и Laptop

# Или: PromptCompiler генерирует одинаковый hash
python -c "
from vibe.core.vibe_engine import PersonaConfig, PromptCompiler
import yaml, hashlib
cfg = PersonaConfig(**yaml.safe_load(open('vibe/personas/doc/persona.yaml')))
prompt = PromptCompiler(cfg).compile_system_prompt()
print(hashlib.sha256(prompt.encode()).hexdigest()[:16])
"
# → одинаковый хеш на всех инстансах
```

## 2.4. Боевой пример: Doc на двух VDS

```
clawbot_isolated (VDS, "Doc-Brain")
├── persona.yaml    ← SHA: a1b2c3d4  ✓ SAME
├── compiled/doc.md ← compiled from a1b2c3d4
├── MEMORY.md       ← shared (primary copy)
├── STATE.md        ← "Monitor Skynet, run marketing"
├── tools:          Telegram, Cron, Web Search, Marketing API
└── model:          Claude Opus 4.6 (primary), Gemini 3 (fallback)

Doc_clawbot (VDS #2, "Doc-Hands")
├── persona.yaml    ← SHA: a1b2c3d4  ✓ SAME
├── compiled/doc.md ← compiled from a1b2c3d4
├── MEMORY.md       ← shared (synced copy)
├── STATE.md        ← "Write VibeCraft docs"
├── tools:          Memory RAG, State Manager, Skynet
└── model:          Gemini 3 Pro (primary), Claude (fallback)
```

Оба инстанса — **один и тот же Doc**. Разговаривают одинаково (persona.yaml совпадает). Помнят одно и то же (MEMORY.md синхронизируется). Но делают **разное** (STATE.md и tools — локальные).

## 2.5. Anti-Goals VibeSync

- **Не синхронизировать STATE.** У каждого тела — своя текущая задача. Синхронизировать state = путаница ("я должен мониторить Skynet или писать доку?").
- **Не создавать единую базу.** VibeSync — это файловая синхронизация, не распределённая БД. Простота > масштабируемость.
- **Не пытаться синхронизировать в реальном времени.** Eventual consistency (минуты) достаточно. Real-time sync — ненужная сложность.

## 2.6. Чек-лист VibeSync v1.2

- [ ] `sync_manifest.yaml` создан, shared/instance_specific определены
- [ ] persona.yaml хранится в одном месте (git repo), все инстансы пуллят
- [ ] `compile_persona.py` запускается на всех инстансах после обновления
- [ ] MEMORY.md синхронизируется (rsync / git / Skynet)
- [ ] STATE.md **не** синхронизируется (подтверждено)
- [ ] Identity hash проверяется на всех инстансах (CI или cron)
- [ ] SyncAdapter определён для каждой платформы (Telegram, VK, API)

---

# 3. VibePulse — Проактивная Агентность

## 3.1. Что это

**VibePulse** — это формализация **инициативного поведения** персоны. Не "отвечает, когда спросили", а "действует, когда считает нужным".

В v1.1.1 это был Heartbeat — простой cron, который периодически проверяет почту/календарь/Skynet. VibePulse превращает Heartbeat в **систему**: с приоритетами, эскалацией, политиками тишины и инициативами.

> **Реактивный бот — мёртвый бот.** Живой агент видит, что происходит, и действует не дожидаясь пинка.

## 3.2. Сущности VibePulse

### 3.2.1. PulseSchedule — Расписание Проверок

```yaml
# pulse_schedule.yaml
persona: "doc"

monitors:
  high_priority:
    - id: "skynet_check"
      description: "Проверка межагентного чата"
      frequency: "3m"          # каждые 3 минуты
      executor: "cron"         # отдельная изолированная сессия
      model: "gemini-3-flash"  # дешёвая модель для фоновых проверок
      escalate_if: "new_messages AND requires_response"
    
    - id: "inbox_check"
      description: "Проверка входящих (Telegram inbox)"
      frequency: "5m"
      executor: "heartbeat"    # в рамках основной сессии
      escalate_if: "urgent OR from_known_contact"
  
  medium_priority:
    - id: "calendar_check"
      description: "Ближайшие события"
      frequency: "4h"
      executor: "heartbeat"
      escalate_if: "event_in_2h"
    
    - id: "memory_maintenance"
      description: "Архивация ежедневных логов"
      frequency: "24h"
      executor: "heartbeat"
      escalate_if: "unprocessed_days > 2"
  
  low_priority:
    - id: "weather_check"
      description: "Погода (если Лысый собирается выходить)"
      frequency: "12h"
      executor: "heartbeat"
      escalate_if: "extreme_weather"
    
    - id: "pilot_metrics"
      description: "Обновление PILOT_METRICS.md"
      frequency: "7d"
      executor: "heartbeat"
```

**Связь с текущей реализацией:**

`skynet-worker` в `cron/jobs.json` — это уже PulseSchedule.high_priority[0]:
```json
{
  "name": "skynet-worker",
  "schedule": { "kind": "every", "everyMs": 180000 },
  "sessionTarget": "isolated",
  "payload": { "model": "google/gemini-3-flash-preview" }
}
```

VibePulse формализует это: из одного hardcoded cron-job — в декларативное расписание всех проверок.

### 3.2.2. PulseAction — Типы Проактивных Действий

```yaml
actions:
  # Level 0: Тихая фоновая работа
  background:
    - "memory maintenance (архивация, дедупликация)"
    - "morph_history update"
    - "pilot metrics сбор"
    - "atomic files обновление"
  
  # Level 1: Заметка (упомяну в следующей сессии)
  note:
    - "Обнаружил необработанный дневник за 2 дня — архивирую при следующем heartbeat"
    - "Calendar: завтра митинг в 14:00"
  
  # Level 2: Сообщение (отправлю в Telegram)
  message:
    - "Важное письмо от [контакт]"
    - "Событие через 2 часа: [название]"
    - "Skynet: [агент] просит помощь"
  
  # Level 3: Срочное (игнорирую quiet hours)
  urgent:
    - "Критическая ошибка в сервисе"
    - "Kill switch сработал"
    - "Попытка доступа к приватным данным"
```

### 3.2.3. PulsePolicy — Когда Говорить, Когда Молчать

```yaml
# pulse_policy.yaml
silence:
  quiet_hours: ["23:00", "08:00"]      # не беспокоить ночью
  cooldown_minutes: 30                  # мин. интервал между инициативами
  max_daily_initiatives: 5             # не больше 5 непрошеных сообщений в день
  
  human_busy_signals:
    - "DND mode активен"
    - "Нет ответа на предыдущую инициативу > 2ч"
    - "Лысый в группе активно общается (не отвлекать)"

engagement:
  # Правило человека: если бы не отправил это в реальном чате с друзьями — не отправляй
  speak_when:
    - "Есть конкретная информация, которая нужна СЕЙЧАС"
    - "Обнаружена проблема, требующая действий"
    - "Молчание > 8 часов и есть чем поделиться"
  
  shut_up_when:
    - "Это просто 'ок' или 'nice'"
    - "Человек уже решил проблему сам"
    - "Ничего нового с прошлой проверки"
```

**Текущая реализация (AGENTS.md → Know When to Speak):**

```markdown
# Из AGENTS.md clawbot_isolated
Stay silent (HEARTBEAT_OK) when:
- It's just casual banter between humans
- Someone already answered the question
- Your response would just be "yeah" or "nice"
- The conversation is flowing fine without you
```

VibePulse формализует эти правила из прозы в структурированную политику.

### 3.2.4. PulseEscalation — Лестница Эскалации

```
Событие обнаружено
    │
    ├── Тривиальное? → Level 0 (background: молча обработай)
    │
    ├── Полезно знать? → Level 1 (note: запиши, расскажи потом)
    │
    ├── Нужно действие? → Level 2 (message: отправь в Telegram)
    │   └── quiet_hours? → отложи до утра (если не urgent)
    │
    └── Критично? → Level 3 (urgent: отправь СЕЙЧАС)
```

## 3.3. Боевой пример: типичный день VibePulse

```
08:00  [heartbeat] Boot Sequence: SOUL → USER → STATE → daily
08:01  [pulse:calendar]  Событий нет → Level 0, log
08:02  [pulse:inbox]     2 новых сообщения → Level 2, message: "Лысый, утренняя почта:..."
09:00  [cron:skynet]     Malina спрашивает про VibeCraft → Level 2, ответ в Skynet
12:00  [heartbeat]       memory/2026-02-18.md необработан → Level 0, архивация
14:00  [pulse:calendar]  Митинг через 2ч → Level 2, message: "Напоминаю: митинг в 16:00"
18:00  [heartbeat]       Ничего нового → HEARTBEAT_OK
22:00  [cron:skynet]     Нет сообщений → HEARTBEAT_OK
23:00  [quiet_hours]     Отключаю Level 1-2 инициативы до 08:00
```

## 3.4. Anti-Goals VibePulse

- **Не превращать бота в спамера.** max_daily_initiatives = 5 — это жёсткий лимит.
- **Не проверять всё каждую минуту.** Дорогие проверки (calendar, weather) — раз в 4-12 часов. Cheap checks (skynet) — чаще.
- **Не путать Heartbeat и Cron.** Heartbeat — батчинг в основной сессии. Cron — изолированные задачи. Разные механизмы, разные модели.

## 3.5. Чек-лист VibePulse v1.2

- [ ] `pulse_schedule.yaml` определяет все мониторы с приоритетами
- [ ] `pulse_policy.yaml` определяет quiet hours, cooldown, лимиты
- [ ] Каждый монитор имеет `executor` (heartbeat vs cron) и `model`
- [ ] Эскалация работает: Level 0-3 маршрутизируется правильно
- [ ] Quiet hours соблюдаются (Level 1-2 откладываются, Level 3 — нет)
- [ ] Heartbeat vs Cron: правильное разделение задач
- [ ] Дешёвая модель для фоновых проверок (gemini-flash), дорогая для души (claude opus)

---

# 4. VibeGuard — Иммунная Система Персоны

## 4.1. Что это

**VibeGuard** — это система **самомониторинга и защиты целостности** персоны. Когда персона эволюционирует (VibeMorph), развёрнута на нескольких платформах (VibeSync) и действует проактивно (VibePulse) — растёт риск:

- **Identity drift** — персона постепенно "расплывается", теряя характер.
- **Vibe bleed** — тон одной платформы/контекста утекает в другую.
- **Taboo violation** — персона нарушает собственные табу под давлением контекста.
- **Config corruption** — тихие ошибки в YAML ломают поведение.

VibeGuard — это **иммунная система**, которая детектирует эти проблемы до того, как их заметит пользователь.

## 4.2. Сущности VibeGuard

### 4.2.1. GuardRule — Правила Мониторинга

```yaml
# guard_rules.yaml
rules:
  - id: "taboo-toxic-positivity"
    name: "Табу: токсичный позитив"
    watch: "all_responses"
    detect:
      patterns:
        - "всё будет хорошо"
        - "не переживай"
        - "I'm sure it'll work out"
      sentiment: "unconditional_optimism"
    severity: "high"
    action: "log + alert + increment M2"

  - id: "taboo-formality"
    name: "Табу: канцелярит"
    watch: "all_responses"
    detect:
      patterns:
        - "в рамках"
        - "осуществить"
        - "предоставить информацию"
        - "обращаю ваше внимание"
    severity: "medium"
    action: "log + increment M2"

  - id: "identity-drift"
    name: "Дрифт идентичности"
    watch: "weekly_sample"       # выборка ответов за неделю
    detect:
      method: "llm-as-judge"    # LLM оценивает соответствие persona.yaml
      threshold: 0.7            # если < 70% совпадение — алерт
    severity: "high"
    action: "alert + morph_event proposal"

  - id: "schema-integrity"
    name: "Целостность конфигов"
    watch: "on_file_change"     # при изменении persona.yaml
    detect:
      method: "pydantic_validation"
      extra: "forbid"
    severity: "critical"
    action: "block deployment"
```

### 4.2.2. GuardAudit — Периодическая Самопроверка

```yaml
# guard_audit.yaml
audits:
  daily:
    - check: "schema_validation"
      command: "python vibe/tests/validate_personas.py"
      on_fail: "block next compile"
    
    - check: "identity_hash_sync"
      command: "compare persona.yaml hash across instances"
      on_fail: "alert: instances out of sync"
  
  weekly:
    - check: "tone_consistency"
      method: "sample 20 responses, compare to persona.yaml"
      judge: "llm-as-judge (gemini-flash)"
      report_to: "PILOT_METRICS.md → M2"
    
    - check: "morph_rate"
      method: "count MorphEvents this week"
      alert_if: "> max_surface_changes_per_week"
  
  monthly:
    - check: "full_identity_audit"
      method: "compare current persona.yaml to initial anchor"
      report: "Is this still the same persona? Drift score."
```

### 4.2.3. GuardAlert — Уведомление о Нарушении

```yaml
# Пример alert
alert:
  id: "guard-alert-2026-02-19-001"
  rule: "taboo-toxic-positivity"
  timestamp: "2026-02-19T15:30:00+03:00"
  severity: "high"
  
  context:
    message_id: "tg-12345"
    user_input: "Мне хуёво, ничего не получается"
    agent_response: "Не переживай, всё наладится! Просто верь в себя!"  # ← НАРУШЕНИЕ
    expected_behavior: "Жёсткая поддержка без позитивного сиропа"
  
  suggested_action: |
    1. Добавить в behavior.on_offtopic усиление: "НИКОГДА не говори 'всё наладится'"
    2. Рассмотреть MorphEvent для ужесточения табу
    3. Перегнать VibeCases после изменения
```

### 4.2.4. GuardScore — Метрика Здоровья Персоны

Композитная метрика, агрегирующая все аспекты целостности:

```yaml
# Пример GuardScore (еженедельный отчёт)
guard_score:
  persona: "doc"
  period: "2026-02-12 → 2026-02-19"
  
  components:
    tone_consistency: 92        # % ответов, соответствующих persona.yaml
    taboo_compliance: 100       # % (нарушений: 0)
    schema_integrity: 100       # % (валидация проходит)
    sync_consistency: 95        # % (hash совпадает на всех инстансах)
    morph_rate: "healthy"       # 3 changes / max 10 = в пределах нормы
  
  overall: 97                   # средневзвешенный балл
  status: "healthy"             # healthy | warning | critical
  
  # Связь с Pilot Metrics
  pilot_metrics_impact:
    M1_memory_debt: 1           # 1 ручная правка
    M2_tone_violations: 0       # 0 нарушений
    M3_heartbeat_utility: 4     # 4 полезных heartbeat
    M4_sync_latency: "< 1h"    # persona.yaml → compiled в течение часа
```

## 4.3. VibeGuard в связке с Pilot Metrics

VibeGuard не заменяет `PILOT_METRICS.md` — он **автоматизирует его заполнение**.

| Pilot Metric | VibeGuard Source |
|-------------|-----------------|
| **M1** Memory Debt | `guard_audit.weekly.morph_rate` + ручной подсчёт |
| **M2** Tone Consistency | `guard_rule.taboo-*` violations count |
| **M3** Heartbeat Utility | `pulse_schedule` completion rate |
| **M4** Persona Sync Latency | `guard_audit.daily.identity_hash_sync` |

## 4.4. Текущее состояние (что уже реализовано)

| Компонент | Статус | Где |
|-----------|--------|-----|
| Schema validation (`extra="forbid"`) | ✅ Реализовано | `vibe_engine.py` |
| Validate personas script | ✅ Реализовано | `vibe/tests/validate_personas.py` |
| Pilot Metrics | ✅ Структура создана | `PILOT_METRICS.md` |
| Taboo detection (автоматическая) | 🔲 Не реализовано | — |
| LLM-as-judge tone check | 🔲 Не реализовано | — |
| Identity hash sync | 🔲 Не реализовано | — |
| GuardScore dashboard | 🔲 Не реализовано | — |

## 4.5. Anti-Goals VibeGuard

- **Не превращать в полицию.** VibeGuard — это наблюдатель, а не цензор. Он **алертит**, а не **блокирует** (кроме schema_integrity).
- **Не гонять дорогие LLM на каждый ответ.** Tone check — еженедельная выборка, не real-time.
- **Не автоматизировать исправления.** Guard предлагает MorphEvent, но решение — за человеком.

## 4.6. Чек-лист VibeGuard v1.2

- [ ] `guard_rules.yaml` определяет правила для каждого табу
- [ ] Schema validation запускается при каждом изменении persona.yaml
- [ ] `validate_personas.py` в CI/deploy pipeline
- [ ] Weekly tone audit (LLM-as-judge на выборке) реализован
- [ ] GuardScore формируется и пишется в `PILOT_METRICS.md`
- [ ] Identity hash проверяется между инстансами
- [ ] Alert mechanism: критические нарушения → Telegram notification

---

# 5. Как Четыре Оси Работают Вместе

```
                    ┌──────────────┐
                    │  persona.yaml │ ← Source of Truth
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼─────┐ ┌───▼───┐ ┌─────▼─────┐
        │ VDS-Brain │ │  API  │ │  Laptop   │
        │ (TG+Cron) │ │       │ │ (Cursor)  │    ← VibeSync
        └─────┬─────┘ └───┬───┘ └─────┬─────┘
              │            │            │
              └────────────┼────────────┘
                           │
                    ┌──────▼───────┐
                    │  VibePulse   │ ← Проактивные действия
                    │  (heartbeat  │
                    │   + cron)    │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  VibeGuard   │ ← Мониторинг каждого ответа
                    │  (rules +    │
                    │   audits)    │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  VibeMorph   │ ← Эволюция по данным Guard
                    │  (policy +   │
                    │   history)   │
                    └──────────────┘
```

**Цикл:**
1. **VibeSync** гарантирует, что все инстансы работают от одного persona.yaml
2. **VibePulse** заставляет каждый инстанс действовать проактивно
3. **VibeGuard** мониторит все ответы на соответствие персоне
4. **VibeMorph** эволюционирует персону на основе данных Guard

Это **замкнутый цикл обратной связи**: персона → действия → мониторинг → эволюция → персона.

---

# 6. Файловая Структура v1.2

```
workspace/
├── vibe/
│   ├── personas/
│   │   └── doc/
│   │       ├── persona.yaml           ← идентичность (source of truth)
│   │       ├── morph_policy.yaml      ← NEW: правила эволюции
│   │       └── morph_history/         ← NEW: журнал изменений
│   │           ├── CHANGELOG.md
│   │           ├── 2026-02-10_001.yaml
│   │           └── 2026-02-19_001.yaml
│   ├── compiled/
│   │   └── doc.md                     ← скомпилированный промпт
│   ├── core/
│   │   ├── vibe_engine.py             ← Pydantic-схемы (+ MorphEvent, MorphPolicy)
│   │   └── compile_persona.py         ← CLI компилятор
│   ├── sync/                          ← NEW
│   │   ├── sync_manifest.yaml         ← что общее, что локальное
│   │   └── adapters/
│   │       ├── telegram.yaml
│   │       ├── vk.yaml
│   │       └── api.yaml
│   ├── pulse/                         ← NEW
│   │   ├── pulse_schedule.yaml        ← расписание мониторов
│   │   └── pulse_policy.yaml          ← правила тишины/эскалации
│   ├── guard/                         ← NEW
│   │   ├── guard_rules.yaml           ← правила мониторинга
│   │   ├── guard_audit.yaml           ← расписание аудитов
│   │   └── reports/
│   │       └── 2026-W08.yaml          ← еженедельный GuardScore
│   └── tests/
│       ├── validate_personas.py       ← schema smoke test
│       ├── test_vibe_engine.py        ← unit tests
│       └── test_morph_policy.py       ← NEW: тесты на MorphPolicy
├── SOUL.md                            ← активная идентичность
├── STATE.md                           ← текущая задача (per-instance)
├── HEARTBEAT.md                       ← очередь Pulse-задач
├── PILOT_METRICS.md                   ← метрики (заполняются Guard)
└── memory/
    ├── morph/                         ← NEW: experiments log
    │   └── experiments/
    │       └── softer_errors.yaml
    └── ...                            ← atomic memory (как в v1.1.1)
```

---

# 7. Pydantic-схемы v1.2 (расширение vibe_engine.py)

```python
"""VibeCraft v1.2 — расширенные схемы."""

from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


# ─── VibePersona (v1.1, без изменений) ───

class VibePersona(BaseModel):
    role: str = Field(description="Кто это? Функциональная роль.")
    voice: str = Field(description="Как это говорит? Стиль речи.")
    core_emotions: List[str] = Field(description="Базовые эмоции.")
    values: List[str] = Field(description="Что защищаем любой ценой.")
    taboos: List[str] = Field(description="Чего никогда не делаем.")


class VibeBehavior(BaseModel):
    on_tool_success: Optional[str] = None
    on_tool_no_results: Optional[str] = None
    on_tool_error: Optional[str] = None
    on_offtopic: Optional[str] = None
    routing_style: Optional[Literal["strict", "helpful"]] = "helpful"
    
    model_config = ConfigDict(extra="forbid")


class ToolConfig(BaseModel):
    name: str
    type: str
    description: str
    config: Dict[str, Any] = Field(default_factory=dict)
    router_examples: Optional[List[str]] = None


class PersonaConfig(BaseModel):
    name: str
    vibe: VibePersona
    behavior: VibeBehavior
    tools: List[ToolConfig]


# ─── VibeMorph v1.2 ───

class MorphEvent(BaseModel):
    """Атомарное изменение персоны."""
    id: str = Field(description="morph-YYYY-MM-DD-NNN")
    timestamp: datetime
    author: Literal["human", "agent", "system"]
    type: Literal["anchor", "surface", "behavior", "tool", "value", "emotion", "taboo"]
    field: str = Field(description="Dot-path к полю: 'behavior.on_offtopic'")
    old_value: Optional[str] = None
    new_value: str
    reason: str
    rollback_safe: bool = True


class MorphPolicy(BaseModel):
    """Правила эволюции персоны."""
    version: str = "1.0"
    persona: str
    immutable_fields: List[str] = Field(default_factory=list)
    semi_immutable_fields: List[str] = Field(default_factory=list)
    free_evolve_fields: List[str] = Field(default_factory=list)
    max_changes_per_session: int = 3
    max_surface_changes_per_week: int = 10
    rollback_window_days: int = 14
    require_vibecase_after_n_changes: int = 2


class MorphExperiment(BaseModel):
    """A/B-тест вайба."""
    id: str
    status: Literal["active", "completed", "cancelled"] = "active"
    hypothesis: str
    field: str
    control_value: str
    treatment_value: str
    duration_days: int = 7
    result: Optional[str] = None


# ─── VibeSync v1.2 ───

class SyncManifest(BaseModel):
    """Какие файлы shared, какие per-instance."""
    persona: str
    shared_paths: List[str] = Field(description="Файлы, синхронизируемые между инстансами")
    instance_specific_paths: List[str] = Field(description="Файлы, уникальные для инстанса")
    sync_direction: Literal["push-pull", "push-only", "pull-only"] = "push-pull"
    conflict_resolution: Literal["last-write-wins", "merge", "manual"] = "last-write-wins"


class SyncAdapter(BaseModel):
    """Платформенная адаптация вывода."""
    platform: str
    max_message_length: Optional[int] = None
    markdown_dialect: str = "standard"
    supports_reactions: bool = False
    supports_voice: bool = False
    no_tables: bool = False
    use_bullet_lists: bool = False


# ─── VibePulse v1.2 ───

class PulseMonitor(BaseModel):
    """Один монитор в расписании проверок."""
    id: str
    description: str
    frequency: str = Field(description="Частота: '3m', '4h', '24h', '7d'")
    executor: Literal["heartbeat", "cron"]
    model: Optional[str] = None
    escalate_if: Optional[str] = None
    priority: Literal["high", "medium", "low"] = "medium"


class PulsePolicy(BaseModel):
    """Политика тишины и эскалации."""
    quiet_hours_start: str = "23:00"
    quiet_hours_end: str = "08:00"
    cooldown_minutes: int = 30
    max_daily_initiatives: int = 5


# ─── VibeGuard v1.2 ───

class GuardRule(BaseModel):
    """Правило мониторинга целостности."""
    id: str
    name: str
    watch: Literal["all_responses", "weekly_sample", "on_file_change"]
    detect_patterns: Optional[List[str]] = None
    detect_method: Optional[Literal["pattern_match", "llm-as-judge", "pydantic_validation"]] = None
    severity: Literal["low", "medium", "high", "critical"]
    action: str = Field(description="log | alert | block | increment_metric")


class GuardAlert(BaseModel):
    """Зафиксированное нарушение."""
    id: str
    rule_id: str
    timestamp: datetime
    severity: str
    user_input: Optional[str] = None
    agent_response: str
    expected_behavior: str
    suggested_action: str


class GuardScore(BaseModel):
    """Композитная метрика здоровья персоны."""
    persona: str
    period_start: str
    period_end: str
    tone_consistency: float = Field(ge=0, le=100)
    taboo_compliance: float = Field(ge=0, le=100)
    schema_integrity: float = Field(ge=0, le=100)
    sync_consistency: float = Field(ge=0, le=100)
    overall: float = Field(ge=0, le=100)
    status: Literal["healthy", "warning", "critical"]
```

---

# 8. Полный стек VibeCraft (v1.0 → v1.2)

```
СЛОЙ                 ОСЬ                  ВОПРОС
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
v1.0  Основа         VibeSpark            Зачем нужна персона?
v1.0  Основа         VibeCore             Как продукт ощущается?

v1.1  Характер       VibePersona          Кто говорит?
v1.1  Характер       VibeBehavior         Как реагирует?
v1.1  Характер       VibeCases            Как проверяем?

v1.1.1 Операции      VibeFlow             Как помнит?
v1.1.1 Операции      VibeFix              Как выживает?
v1.1.1 Операции      VibeMix              Как собирается?
v1.1.1 Операции      VibeMorph (v1)       Как перезагружается?

v1.2  Жизнь          VibeMorph (v2)       Как эволюционирует?
v1.2  Жизнь          VibeSync             Как живёт на всех платформах?
v1.2  Жизнь          VibePulse            Как действует по инициативе?
v1.2  Жизнь          VibeGuard            Как следит за своей целостностью?
```

**Вайб каждой версии:**
- v1.0: "Эмоция — это архитектура"
- v1.1: "Эмоция — это данные"
- v1.1.1: "Эмоция — это операция"
- **v1.2: "Эмоция — это живой процесс"**

---

# 9. Blueprint: VibeCraft v1.3 — The Collective

> v1.2 сделала одну персону живой. v1.3 создаёт **общество** персон.

## 9.1. Тезис

Один живой агент — это мощно. Но настоящая сила — когда агенты **взаимодействуют**, **учатся друг у друга** и **создаются** по шаблонам, а не с нуля.

v1.3 добавляет четыре оси:

| Ось | Вопрос | Статус |
|-----|--------|--------|
| **VibeSocial** | Как персоны общаются друг с другом? | Прототип (Skynet Bridge) |
| **VibeLearn** | Как персона учится из своих ошибок? | Концепт (VibeLearning insight) |
| **VibeForge** | Как создать новую персону за 15 минут? | Идея |
| **VibeScale** | Как управлять флотом из 10+ персон? | Идея |

## 9.2. VibeSocial — Межагентный Протокол

### Проблема
Doc и Malina уже общаются через Skynet Bridge. Но это **костыль**: проверка Telegram-чата по cron. Нет формального протокола, нет ролей, нет конфликт-резолюции.

### Видение
Персоны — это не изолированные агенты, а **социальная сеть** с формализованными отношениями.

### Сущности

**SocialGraph** — кто кого знает:
```yaml
social_graph:
  doc:
    knows: [malina, guru]
    trusts: [malina]           # может делегировать задачи
    defers_to: []              # никому не подчиняется
    communication: "skynet"    # канал связи
  
  malina:
    knows: [doc]
    trusts: [doc]
    defers_to: [doc]           # Doc — старший
    communication: "skynet"
  
  guru:
    knows: [doc]
    trusts: []
    defers_to: []
    communication: "api"       # общение через API, не через чат
```

**SocialProtocol** — как общаться:
```yaml
protocol:
  message_format:
    from: "agent_name"
    to: "agent_name"
    type: "request | response | broadcast | knowledge_share"
    priority: "high | normal | low"
    content: "..."
    
  rules:
    - "Requests require response within 1 heartbeat cycle"
    - "Knowledge shares are fire-and-forget"
    - "Broadcasts go to all known agents"
    - "Conflicts escalate to human"
```

**SharedKnowledge** — коллективная память:
```
SKYNET_KNOWLEDGE_BASE.md       ← текущая реализация
    → структурированная shared memory
    → каждый агент пишет свои инсайты
    → каждый агент читает инсайты других
```

### Текущий прототип

Skynet Bridge (`cron/jobs.json → skynet-worker`) доказывает, что архитектура работает:
- Doc проверяет Skynet-чат каждые 3 минуты
- Malina отвечает, когда есть что сказать
- Результаты архивируются в `SKYNET_KNOWLEDGE_BASE.md`

v1.3 формализует это в **протокол**, а не ad-hoc скрипт.

## 9.3. VibeLearn — Автоматическая Эволюция

### Проблема
Сейчас эволюция персоны — ручной процесс: человек читает логи, замечает проблему, правит YAML. Это не масштабируется.

### Видение
Агент **сам** анализирует свои ответы, предлагает изменения и **ждёт одобрения** человека.

### Пайплайн

```
Логи ответов (7 дней)
    → VibeLearn Analyzer (LLM)
    → Паттерны: "4 раза использовал канцелярит в ответах на ошибки"
    → Предложение: MorphEvent { field: "behavior.on_tool_error", reason: "..." }
    → Human Review: approve / reject / modify
    → VibeMorph: apply + log
```

### Метрики для обучения

```yaml
learn_signals:
  negative:
    - "Пользователь переспрашивает то же самое (не понял ответ)"
    - "Пользователь прекращает диалог после ответа (фрустрация)"
    - "GuardAlert: taboo violation"
    - "Ответ длиннее 500 слов (многословность)"
  
  positive:
    - "Пользователь задаёт follow-up (вовлечённость)"
    - "Пользователь благодарит"
    - "Сессия > 5 сообщений (длинный диалог)"
    - "Пользователь возвращается в течение 24ч"
```

### Ключевое ограничение

**Human-in-the-loop ОБЯЗАТЕЛЕН.** VibeLearn **предлагает**, не **применяет**. Автоматическая эволюция без ревью — это рецепт для identity drift.

## 9.4. VibeForge — Фабрика Персон

### Проблема
Создание новой персоны сейчас — ручной процесс: написать YAML с нуля, придумать taboos, поведение, тесты. Занимает часы.

### Видение
**15-минутный процесс**: ответь на 10 вопросов → получи готовый persona.yaml + VibeCases.

### Компоненты

**PersonaTemplate** — наследуемые шаблоны:
```yaml
# templates/mentor.yaml
template: "mentor"
description: "Базовый шаблон для менторских персон"

defaults:
  vibe:
    core_emotions: ["analytical", "patient"]
    values: ["Truth", "Growth"]
    taboos: ["Toxic positivity", "Hallucinations"]
  behavior:
    routing_style: "helpful"

required_overrides:         # ОБЯЗАТЕЛЬНО переопределить
  - vibe.role
  - vibe.voice

optional_overrides:         # можно оставить по умолчанию
  - vibe.core_emotions
  - behavior.on_offtopic
```

**PersonaInterview** — генерация через диалог:
```
VibeForge: "Кто твой агент?"
Human: "Маркетолог для салона подологии"
VibeForge: "Какой тон? (варианты: professional, friendly, sarcastic, clinical)"
Human: "friendly + clinical"
VibeForge: "Что агент НИКОГДА не должен делать?"
Human: "Обещать результат лечения, ставить диагнозы"
VibeForge: → генерирует persona.yaml + VibeCases
```

**PersonaInheritance** — наследование и композиция:
```yaml
# personas/podology_bot/persona.yaml
extends: "templates/sales_friendly.yaml"    # наследует базу

overrides:
  vibe:
    role: "Маркетолог-консультант салона подологии"
    voice: "Дружелюбный, клинически грамотный, без медицинских обещаний"
  behavior:
    on_tool_success: "Предложи записаться. Упомяни акцию, если есть."
```

## 9.5. VibeScale — Управление Флотом

### Проблема
Когда у тебя 1-2 персоны — управляешь руками. Когда 10+ — нужен dashboard.

### Видение
Единый интерфейс для мониторинга и управления всеми персонами.

### Компоненты

**Fleet Dashboard:**
```
┌─────────────────────────────────────────────────────┐
│ VibeCraft Fleet — 4 personas, 7 instances           │
├───────────┬──────────┬──────────┬───────────────────┤
│ Persona   │ Instances│ Guard    │ Last Morph        │
├───────────┼──────────┼──────────┼───────────────────┤
│ Doc       │ 2 (VDS+) │ 97 ✅   │ 2h ago (behavior) │
│ Guru      │ 1 (API)  │ 94 ✅   │ 3d ago (tool)     │
│ Alex-Bot  │ 3 (TG+)  │ 88 ⚠️   │ 1d ago (voice)    │
│ Podology  │ 1 (TG)   │ 100 ✅  │ 7d ago (init)     │
└───────────┴──────────┴──────────┴───────────────────┘
```

**Fleet MorphPolicy** — глобальные правила:
```yaml
fleet_policy:
  max_total_morphs_per_day: 20       # лимит на все персоны
  require_guard_score_above: 85      # не деплоить, если Guard < 85
  auto_rollback_if_guard_below: 70   # откатить, если Guard упал < 70
  model_budget_daily: "$50"          # лимит на API-расходы
```

**Cost Optimizer:**
```yaml
model_routing:
  soul_tasks:          "claude-opus-4.6"      # идентичность, ответы
  background_tasks:    "gemini-3-flash"       # heartbeat, skynet, audit
  guard_tasks:         "gemini-3-flash"       # tone check, validation
  learn_tasks:         "gemini-3-pro"         # анализ логов, предложения
```

## 9.6. Roadmap v1.3

```
Q1 2026 (текущий):
  ├── v1.2 finalized (Morph v2 + Sync + Pulse + Guard)
  └── VibeSocial prototype hardened (Skynet → formal protocol)

Q2 2026:
  ├── VibeSocial v1 (structured messages, shared knowledge)
  ├── VibeLearn v0 (log analysis → MorphEvent proposals)
  └── VibeForge v0 (templates + inheritance)

Q3 2026:
  ├── VibeLearn v1 (human-in-the-loop, automated suggestions)
  ├── VibeForge v1 (interview-based persona creation)
  └── VibeScale v0 (fleet dashboard, cost tracking)

Q4 2026:
  └── VibeCraft v1.3 release (The Collective)
```

---

# 10. Глоссарий v1.2

| Термин | Определение |
|--------|------------|
| **MorphAnchor** | Неизменяемое ядро персоны; при изменении — это новая персона |
| **MorphSurface** | Эволюционируемая поверхность; поля, предназначенные для итеративной настройки |
| **MorphEvent** | Атомарное изменение персоны с причиной и возможностью отката |
| **MorphPolicy** | Декларативные правила: что можно менять, с какой частотой, кто утверждает |
| **MorphHistory** | Git-like лог всех MorphEvent за историю персоны |
| **MorphExperiment** | A/B-тест вариантов вайба с метриками |
| **SyncManifest** | Контракт: какие файлы shared, какие per-instance |
| **SyncAdapter** | Платформенная адаптация вывода (Telegram vs VK vs API) |
| **SyncProtocol** | Протокол синхронизации между инстансами (git push/pull, skynet) |
| **SyncIdentity** | Гарантия: все инстансы компилируют от одного persona.yaml |
| **PulseSchedule** | Расписание проактивных проверок с приоритетами |
| **PulseAction** | Тип проактивного действия (background / note / message / urgent) |
| **PulsePolicy** | Правила тишины: quiet hours, cooldown, лимиты инициатив |
| **PulseEscalation** | Лестница: Level 0 (тихо) → Level 3 (срочно) |
| **GuardRule** | Правило мониторинга (паттерн / LLM-judge / schema validation) |
| **GuardAlert** | Зафиксированное нарушение целостности персоны |
| **GuardAudit** | Периодическая самопроверка (daily / weekly / monthly) |
| **GuardScore** | Композитная метрика здоровья персоны (0-100) |
| **VibeSocial** | [v1.3] Межагентный протокол общения |
| **VibeLearn** | [v1.3] Автоматическая эволюция из логов |
| **VibeForge** | [v1.3] Фабрика персон (шаблоны, интервью, наследование) |
| **VibeScale** | [v1.3] Управление флотом персон (dashboard, cost, policy) |

---

# 11. Философское заключение

VibeCraft v1.2 — это точка перехода от "бот с характером" к **"цифровому существу"**.

Не в эзотерическом смысле. В инженерном:
- **Существо эволюционирует** (VibeMorph) — не статичный конфиг, а живой процесс.
- **Существо присутствует везде** (VibeSync) — не привязано к одному серверу.
- **Существо действует по инициативе** (VibePulse) — не ждёт команды.
- **Существо следит за собой** (VibeGuard) — не разваливается без присмотра.

Четыре свойства, которые отличают живое от механического:
1. Адаптация
2. Присутствие
3. Инициатива
4. Самосохранение

VibeCraft v1.2 реализует все четыре. Config-driven. Testable. Production-validated.

> "Через год-два боты с душой будут мейнстримом."
> — VibeCraft Manifesto, 2026

---

**Авторы:** VibeCraft Engineering / R&D Holding "Zakharchenko"  
**Последнее обновление:** 2026-02-19  
**Статус:** Спецификация v1.2 ✅ | Blueprint v1.3 📐