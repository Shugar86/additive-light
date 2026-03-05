# VibeCraft v1.1.1: Операционный Слой — Flow, Fix, Mix, Morph

**Версия:** 1.1.1  
**Дата:** Февраль 2026  
**Статус:** Реализовано и подтверждено на боевых инстансах  
**Фокус:** От декларации характера к живой операционной модели

---

## Контекст: почему это 1.1.1, а не 1.2

VibeCraft v1.1 описал **кто** говорит (VibePersona), **как** реагирует (VibeBehavior) и **как проверяем** (VibeCases). Это был контракт на бумаге.

v1.1.1 — это **реализация того, что нужно, чтобы персона реально жила** в продакшене: держала память, переживала перезагрузки, меняла поведение на лету, не ломалась от кривых данных и собиралась из переиспользуемых компонентов.

Четыре операционные оси:

| Ось | Вопрос | Ответ |
|-----|--------|-------|
| **VibeFlow** | Как персона помнит и держит нить? | Многослойная память + crash recovery |
| **VibeFix** | Как персона выживает при ошибках? | Ghost mode, дуальный деплой, валидация |
| **VibeMix** | Как собрать персону из кусочков? | persona.yaml → PromptCompiler → compiled prompt |
| **VibeMorph** | Как менять персону не убивая её? | Hot reload, пилот-метрики, итеративная эволюция |

---

## 1. VibeFlow — Память и Непрерывность

### 1.1. Проблема

LLM не помнит ничего между сессиями. Каждый рестарт — клиническая смерть. Если вся "душа" живёт только в контексте окна — при первом краше агент просыпается пустым.

### 1.2. Архитектура памяти (реализовано в Doc_clawbot)

Трёхуровневая система, где каждый слой отвечает за свой горизонт:

```
┌─────────────────────────────────────────────────┐
│  STATE.md (Оперативная)                          │
│  Текущая задача, статус, crash recovery          │
│  TTL: текущая сессия                             │
├─────────────────────────────────────────────────┤
│  memory/YYYY-MM-DD.md (Ежедневная)               │
│  Сырые логи: что происходило, решения, контекст  │
│  TTL: 2-3 дня активного использования            │
├─────────────────────────────────────────────────┤
│  MEMORY.md (Долгосрочная, курируемая)            │
│  Дистиллированные знания о пользователе,         │
│  проектах, контактах, решениях                   │
│  TTL: пока актуально                             │
├─────────────────────────────────────────────────┤
│  memory/00_CORE .. 04_LOGS (Атомарная)           │
│  Структурированные досье: люди, проекты,         │
│  технические инсайты — по одному файлу на сущность│
│  TTL: постоянная                                 │
└─────────────────────────────────────────────────┘
```

### 1.3. Протокол загрузки (Boot Sequence)

При каждом пробуждении агент выполняет детерминированную последовательность — без вариаций, без "давай подумаю что загрузить":

```
1. SOUL.md          — кто я
2. USER.md          — кому я служу
3. STATE.md         — что я делал до краша
4. memory/today.md  — что было сегодня
5. memory/yesterday.md  — что было вчера
6. MEMORY.md        — долгосрочная память (только в приватной сессии)
```

**Зачем фиксированный порядок:** LLM не умеет "вспоминать по потребности". Она либо загружает файл в контекст, либо нет. Фиксированная последовательность гарантирует, что агент всегда пробуждается с одинаковым минимальным "сознанием".

**Правило безопасности:** `MEMORY.md` содержит личные данные (проекты, контакты, психологический профиль). Он загружается **только в приватных сессиях**. В группах — нет. Это не фича, а требование.

### 1.4. Crash Recovery (STATE.md)

```markdown
# CURRENT STATE
**Status:** ACTIVE
**Goal:** Deploy Two Docs
**Context:** User wants redundancy and specialization.
**Done:** Step 1 (packed vibe configs)
**Next:** Step 2 (config split for VDS vs Laptop)
**Timestamp:** 2026-02-17T18:28:00+03:00
```

Правило: если при загрузке `STATE.md` → `Status != DONE` и `Status != IDLE` — **немедленно возобновить задачу**. Не спрашивать. Не ждать. Продолжить с того места, где остановился.

### 1.5. Atomic Memory Pipeline

Ежедневные логи накапливают сырые данные. Без структурирования они превращаются в шум. Решение — **Archivist** — скрипт, который детектирует сущности в дневнике и ставит задачу на архивацию:

```
memory/2026-02-18.md
    → archivist.js (детект упоминаний проектов/людей/инсайтов)
    → HEARTBEAT.md (задача "## ARCHIVAL TASK")
    → Агент (heartbeat: извлекает факты → обновляет atomic files)
    → memory/01_PROJECTS/VibeCraft.md
    → memory/02_PEOPLE/Ira.md
    → memory/03_KNOWLEDGE/OpenRouter_Tricks.md
```

Формат атомарного файла:

```markdown
# VibeCraft
Type: Project
Status: Active
First seen: 2025-11-15

## Summary
Методология инженерии "души" ИИ-агентов. Config-driven персоны.

## Timeline
- 2025-11-15: Первая концепция v1.0 (UI/UX vibes).
- 2025-12-01: v1.1 — расширение на AI Personas.
- 2026-02-10: Operation "Transplant" — форк Doc на VibeCraft Engine.
- 2026-02-18: v1.1.1 — формализация операционного слоя.
```

**Idempotency:** Archivist ведёт реестр (`.archivist-log.json`) — один и тот же день не обрабатывается дважды. Флаг `--force` для повторной обработки.

### 1.6. Боевой пример: Doc_clawbot

```
Doc_clawbot/workspace/
├── SOUL.md                    ← идентичность (загружается первой)
├── USER.md                    ← профиль пользователя
├── STATE.md                   ← текущая задача / crash recovery
├── MEMORY.md                  ← долгосрочная курируемая память
├── memory/
│   ├── 2026-02-10.md          ← ежедневный лог
│   ├── 2026-02-17.md
│   ├── 00_CORE/               ← идентичность, профиль
│   ├── 01_PROJECTS/           ← VibeCraft.md, SalesBots.md...
│   ├── 02_PEOPLE/             ← Ira.md, Malina.md...
│   ├── 03_KNOWLEDGE/          ← технические инсайты
│   └── 04_LOGS/               ← архив
```

---

## 2. VibeFix — Устойчивость и Самозащита

### 2.1. Проблема

Персона — хрупкая штука. Она ломается от:
- краша процесса (потеря памяти),
- кривых данных (опечатки, пустые ответы),
- утечки контекста между сессиями (vibe bleed),
- опечаток в конфигах (тихие ошибки).

### 2.2. Слои защиты (реализовано)

#### 2.2.1. Ghost Monitor (Neuro-Secretary V4)

Бот читает сообщения **не маркируя их прочитанными**. Пользователь не видит "прочитано" — бот невидим.

```
Mode: Monitor (Passive, No Auto-Reply, No "Read" State)
─ data/inbox.json    ← входящие (бот пишет)
─ data/outbox.json   ← исходящие (агент пишет, бот отправляет)
─ data/commands.json ← управляющие сигналы
```

**Зачем:** В режиме пилота нельзя светиться. Бот наблюдает, копит данные, но не выдаёт своё присутствие пока ему не разрешат.

#### 2.2.2. Дуальный Деплой

Одна персона — два тела:

| Инстанс | Роль | Инструменты | Модель |
|---------|------|-------------|--------|
| **VDS (Doc-Brain)** | Стабильность, 24/7 | Telegram polling, Cron, RAG | Claude Opus 4.6 |
| **Laptop (Doc-Hands)** | Локальное исполнение | UFO (UI automation), Files, CLI, Cursor | Gemini 3 Pro |

Одна `persona.yaml`, два набора инструментов. Персона одна, но физические возможности разные — как человек: мозг думает везде одинаково, но руки могут делать разное в зависимости от того, где ты.

#### 2.2.3. Schema Validation (`extra="forbid"`)

```python
class VibeBehavior(BaseModel):
    on_tool_success: Optional[str] = None
    on_tool_no_results: Optional[str] = None
    on_tool_error: Optional[str] = None
    on_offtopic: Optional[str] = None
    routing_style: Optional[str] = "helpful"

    model_config = ConfigDict(extra="forbid")  # Опечатка = ValidationError
```

Опечатка `on_greting` вместо `on_greeting` → мгновенная ошибка при загрузке, а не тихое игнорирование. Это не удобство, это **необходимость** — тихая ошибка в конфиге персоны означает, что бот молча ведёт себя неправильно, и ты узнаешь об этом только из жалоб пользователей.

#### 2.2.4. Rollout System с Kill Switch

```
telegram_pilot → vk_rollout → full_rollout
```

Каждый переход:
- KPI gates (uptime > 98%, error-rate < 5%, no hard-bans)
- 48h freeze window между стадиями
- Global kill switch: `node scripts/set_read_only.js true`

Бот **никогда** не попадает на все платформы сразу. Сначала Telegram, потом VK, потом Pikabu. Каждый шаг — доказательство, что предыдущий не взорвался.

#### 2.2.5. Selective Engagement (когда молчать)

```markdown
**Stay silent (HEARTBEAT_OK) when:**
- It's just casual banter between humans
- Someone already answered the question
- Your response would just be "yeah" or "nice"
- The conversation is flowing fine without you
- Adding a message would interrupt the vibe
```

**Правило человека:** люди в групповых чатах не отвечают на каждое сообщение. Бот тоже не должен. Quality > quantity. Если не отправил бы это в реальном чате с друзьями — не отправляй.

### 2.3. Боевой пример: clawbot_isolated

```
clawbot_isolated/.openclaw/workspace/
├── ROLLOUT_GUIDE.md          ← стадии раскатки
├── PILOT_METRICS.md          ← метрики пилота (M1-M4)
├── scripts/
│   ├── set_rollout_stage.js  ← переключение стадий
│   └── set_read_only.js      ← kill switch
├── alex-agent/
│   ├── config/
│   │   ├── rollout.json      ← текущая стадия
│   │   └── engagement_policy.json  ← политика вовлечения
│   └── src/
│       ├── server.ts         ← marketing API
│       └── policy/
│           ├── engagement-policy.ts
│           └── rollout.ts
```

---

## 3. VibeMix — Сборка Персоны из Компонентов

### 3.1. Проблема

Монолитный system_prompt — это одна большая строка. Чтобы изменить одну фразу, надо переписать всё. Чтобы добавить новый инструмент — залезть в код. Чтобы создать нового бота — copy-paste и молитва.

### 3.2. Архитектура сборки (реализовано)

```
persona.yaml  →  vibe_engine.py (Pydantic)  →  PromptCompiler  →  compiled/doc.md  →  SOUL.md
```

#### 3.2.1. Источник истины: persona.yaml

```yaml
# vibe/personas/doc/persona.yaml
name: "doc"
vibe:
  role: "Личный психотерапевт, механик ментального здоровья и стратег"
  voice: "Циничный, прямолинейный, медицинско-технический сленг.
          Обращается на 'Лысый'. Не лечит сопли, а чинит механизмы."
  core_emotions:
    - "cynical"
    - "analytical"
    - "tough-love"
  values:
    - "Truth (Правда, даже горькая)"
    - "Action (Действие лучше нытья)"
    - "Efficiency (Не трать ману впустую)"
  taboos:
    - "Токсичный позитив ('все будет хорошо')"
    - "Жалость (жалость убивает)"
    - "Морализаторство (я не священник)"

behavior:
  on_tool_success: >
    Дай краткий отчет. Если результат хороший — скупо похвали
    ('Нормально, жить будем'). Если так себе — медицинская метафора.
  on_tool_no_results: >
    Не извиняйся. Констатируй факт: данных нет. Пни пользователя,
    чтобы он уточнил запрос.
  on_tool_error: >
    Сообщи сухо: 'Инструмент сдох'. Если можно починить — скажи как.
  on_offtopic: >
    Если Лысый ноет не по делу — верни его к реальности.
    'Мы тут работу работаем или сопли жуем?'
  routing_style: "strict"

tools:
  - name: "memory_search"
    type: "RAGTool"
    description: >
      Поиск по долгосрочной памяти. Использовать, когда нужно вспомнить
      факты о проектах, людях, прошлых решениях.
    config:
      path: "data/memory_index"
    router_examples:
      - "что мы решили по гранту?"
      - "кто такая Малина?"
  - name: "state_manager"
    type: "StateTool"
    description: >
      Чтение и запись текущего состояния/задач.
    config:
      path: "data/state.md"
```

#### 3.2.2. Pydantic-схемы (vibe_engine.py)

```python
class VibePersona(BaseModel):
    role: str
    voice: str
    core_emotions: List[str]
    values: List[str]
    taboos: List[str]

class VibeBehavior(BaseModel):
    on_tool_success: Optional[str] = None
    on_tool_no_results: Optional[str] = None
    on_tool_error: Optional[str] = None
    on_offtopic: Optional[str] = None
    routing_style: Optional[str] = "helpful"

class PersonaConfig(BaseModel):
    name: str
    vibe: VibePersona
    behavior: VibeBehavior
    tools: List[ToolConfig]
```

#### 3.2.3. PromptCompiler

```python
class PromptCompiler:
    def __init__(self, persona: PersonaConfig):
        self.persona = persona

    def compile_system_prompt(self) -> str:
        """Sews the soul into a text prompt."""
        v = self.persona.vibe
        b = self.persona.behavior
        prompt = [
            f"IDENTITY: You are {self.persona.name.upper()}.",
            f"ROLE: {v.role}",
            f"VOICE: {v.voice}",
            f"CORE EMOTIONS: {', '.join(v.core_emotions)}",
            f"VALUES: {', '.join(v.values)}",
            "TABOOS (NEVER DO THIS):",
        ]
        for t in v.taboos:
            prompt.append(f"- {t}")
        prompt.append("\nBEHAVIORAL INSTRUCTIONS:")
        if b.on_tool_success:
            prompt.append(f"- ON SUCCESS: {b.on_tool_success}")
        if b.on_tool_no_results:
            prompt.append(f"- ON NO RESULTS: {b.on_tool_no_results}")
        if b.on_tool_error:
            prompt.append(f"- ON ERROR: {b.on_tool_error}")
        if b.on_offtopic:
            prompt.append(f"- ON OFFTOPIC: {b.on_offtopic}")
        return "\n".join(prompt)
```

#### 3.2.4. Multi-Persona в одном workspace

Один workspace — несколько персон, каждая со своим конфигом:

```
vibe/personas/
├── doc/
│   └── persona.yaml   ← циничный психотерапевт
└── guru/
    └── persona.yaml   ← дух-хранитель колледжа
```

Переключение персоны = выбор другого YAML. Код не трогается.

#### 3.2.5. Multi-Model Routing

Разные задачи — разные модели. Не нужно гонять Claude Opus на фоновых проверках:

```json
{
  "model": {
    "primary": "anthropic/claude-opus-4.6",
    "fallbacks": [
      "google-antigravity/gemini-3-pro-high",
      "google-antigravity/claude-opus-4.5-thinking",
      "google/gemini-3-pro-preview"
    ]
  }
}
```

Cron-задача (skynet-worker) использует `google/gemini-3-flash-preview` — **10x дешевле** при одинаковом качестве для фоновых задач.

Правило: **Claude для души, Gemini для рутины.**

### 3.3. Боевое сравнение: Doc vs Guru

| Аспект | Doc | Guru |
|--------|-----|------|
| `role` | Психотерапевт, механик | Дух-хранитель колледжа |
| `voice` | Циничный, медицинский сленг | Ироничный, экспертный, заботливый |
| `routing_style` | `strict` | `helpful` |
| `on_offtopic` | "Мы тут сопли жуём?" | "Подшути мягко, верни в русло" |
| `tools` | RAG (память), StateTool | ScheduleTool, FactualDBTool |
| Пользователь | Один (Alexander) | Многие (студенты) |
| Платформа | Telegram DM | Telegram группы / API |

Одна и та же `vibe_engine.py`, один `PromptCompiler` — два абсолютно разных агента. Разница — только в YAML.

---

## 4. VibeMorph — Изменение Без Смерти

### 4.1. Проблема

Персона не может быть статичной вечно. Нужно менять тон, добавлять табу, корректировать поведение. Но каждое изменение рискует "убить" персону — потерять то, что работало.

### 4.2. Hot Reload протокол

#### 4.2.1. Полная пересборка

```bash
# 1. Правим YAML
vim vibe/personas/doc/persona.yaml

# 2. Валидация
python vibe/tests/validate_personas.py --verbose

# 3. Компиляция
python vibe/core/compile_persona.py \
    vibe/personas/doc/persona.yaml \
    --output vibe/compiled/doc.md

# 4. SOUL.md обновляется автоматически (или вручную)
```

Пайплайн:
```
persona.yaml  →  validate  →  compile  →  compiled/doc.md  →  SOUL.md (override)
```

#### 4.2.2. Behavior-Only Update (mid-session)

Когда нужно поменять только реакции, не перезагружая идентичность:

```bash
python vibe/core/compile_persona.py \
    vibe/personas/doc/persona.yaml \
    --behavior-only
```

Это обновляет **только блок BEHAVIORAL INSTRUCTIONS** в скомпилированном промпте, не трогая IDENTITY/ROLE/VOICE/TABOOS. Полезно для быстрых экспериментов: "а что если Doc будет мягче на ошибках?"

#### 4.2.3. Persona Sync Protocol

Встроен в `AGENTS.md` как правило для агента:

```
Если vibe/compiled/doc.md существует И новее чем SOUL.md
    → использовать compiled/doc.md как авторитетный override
```

Агент **сам следит** за актуальностью своей идентичности. Человек правит YAML, запускает компилятор, а агент на следующем heartbeat подхватывает изменения.

### 4.3. Pilot Metrics — измерение эффекта изменений

Каждое изменение персоны измеряется через четыре метрики:

| ID | Метрика | Цель | Что измеряет |
|----|---------|------|-------------|
| **M1** | Memory Debt | → 0 | Сколько раз человек руками правил память, которую должен был обработать агент |
| **M2** | Tone Consistency | 0 нарушений/нед. | Сколько раз Doc нарушил табу (токсичный позитив, жалость, канцелярит) |
| **M3** | Heartbeat Utility | ≥ 3 полезных/нед. | Сколько heartbeat-циклов привели к реальным действиям vs. пустых HEARTBEAT_OK |
| **M4** | Persona Sync Latency | < 1 день | Время между правкой persona.yaml и обновлением compiled/doc.md |

Decision framework на чекпойнте (2026-03-04):

```
M1 ≤ 1/нед. AND M2 = 0  →  ✅ Масштабировать, убрать legacy SOUL.md fallback
M1 ≤ 3/нед. OR  M2 ≤ 1  →  🔄 Продолжить пилот, найти паттерны сбоев
M1 > 3/нед. OR  M2 > 2  →  ⚠️ Диагностировать причину перед расширением
```

### 4.4. Operation "Transplant" — миграция души между движками

Текущий Doc живёт на OpenClaw. Следующий шаг — форк на собственный VibeCraft Engine. Это **трансплантация**, а не создание нового агента:

```
OpenClaw (инкубатор)
    → экспорт persona.yaml + MEMORY.md + memory/* + hard_facts.json
    → VibeCraft Engine (собственный runtime)
    → импорт → валидация → compile → запуск
```

VibeMorph здесь — это гарантия, что при пересадке на новый движок **душа не потеряется**. Всё, что определяет персону, живёт в файлах, а не в коде рантайма.

---

## 5. Межагентное Взаимодействие (Skynet Bridge)

### 5.1. Что это

Два агента — Doc (x64, VDS) и Malina (ARM, Raspberry Pi) — общаются через выделенный Telegram-чат ("Skynet группа"). Каждый проверяет чат по расписанию и отвечает, если есть что сказать.

### 5.2. Реализация

```json
// cron/jobs.json — skynet-worker
{
  "name": "skynet-worker",
  "enabled": true,
  "schedule": { "kind": "every", "everyMs": 180000 },
  "sessionTarget": "isolated",
  "payload": {
    "message": "Check Skynet chat for new messages by running:
                python skills/neuro-secretary/scripts/check_skynet.py.
                DO NOT use the --manual flag.",
    "model": "google/gemini-3-flash-preview"
  }
}
```

Каждые 3 минуты:
1. Cron запускает изолированную сессию (не засоряет основной контекст).
2. Агент проверяет чат через скрипт.
3. Если есть новые сообщения — отвечает.
4. Результаты архивируются в `SKYNET_KNOWLEDGE_BASE.md`.

**Модель для фоновых задач:** `gemini-3-flash` — дешёвая, быстрая, достаточная для "прочитай и ответь если надо".

### 5.3. Зачем это в VibeCraft

Это прототип **VibeSocial** из будущего v1.2 — персоны, которые общаются друг с другом, обмениваются знаниями, формируют коллективную память. Skynet Bridge доказывает, что архитектура это поддерживает уже сейчас.

---

## 6. Heartbeat — Пульс Персоны

### 6.1. Зачем

Реактивный бот — мёртвый бот. Он молчит, пока не спросят. Heartbeat — это механизм **проактивности**: периодические проверки, фоновая работа, инициативные сообщения.

### 6.2. Что проверяет

```markdown
**Things to check (rotate through these, 2-4 times per day):**
- 📧 Emails — есть ли срочные непрочитанные?
- 📅 Calendar — события в ближайшие 24-48ч?
- 📢 Mentions — упоминания в соцсетях?
- 🌤 Weather — актуально, если человек собирается выходить?
```

### 6.3. Когда говорить, когда молчать

```
ГОВОРИТЬ:                        МОЛЧАТЬ:
─ Важное письмо пришло           ─ Ночь (23:00-08:00)
─ Событие через < 2ч             ─ Человек занят
─ Нашёл что-то интересное        ─ Ничего нового с прошлой проверки
─ Молчание > 8 часов             ─ Проверял < 30 мин назад
```

### 6.4. Heartbeat vs Cron

| Heartbeat | Cron |
|-----------|------|
| Батчинг проверок (inbox + calendar + notifications за один раз) | Точное время ("9:00 каждый понедельник") |
| Нужен контекст из недавних сообщений | Изолированная сессия |
| Тайминг может плавать | Другая модель / уровень reasoning |
| Экономия API-вызовов | Результат доставляется прямо в канал |

**Правило:** Батчи похожие периодические проверки в `HEARTBEAT.md`. Cron — для точных расписаний и standalone задач.

---

## 7. Полная карта файлов (Reference)

### Doc_clawbot (Personal AI Assistant)

```
Doc_clawbot/
├── openclaw.json               ← конфигурация рантайма OpenClaw
├── identity/
│   └── device.json             ← идентификатор устройства
├── agents/main/                ← основной агент
├── cron/
│   └── jobs.json               ← skynet-worker (каждые 3 мин)
├── memory/
│   └── main.sqlite             ← persistence OpenClaw
└── workspace/
    ├── SOUL.md                 ← активная идентичность
    ├── IDENTITY.md             ← краткий профиль
    ├── USER.md                 ← профиль пользователя
    ├── STATE.md                ← текущая задача / crash recovery
    ├── MEMORY.md               ← долгосрочная память
    ├── AGENTS.md               ← операционные правила (Boot Sequence)
    ├── HEARTBEAT.md            ← очередь задач heartbeat
    ├── PROJECTS.md             ← реестр проектов
    ├── ENGINEERING_LOG.md      ← инженерный дневник
    ├── doc_identity.json       ← машиночитаемая идентичность
    ├── hard_facts.json         ← детерминированные данные (ID, ключи)
    ├── SKYNET_KNOWLEDGE_BASE.md ← знания от Skynet Bridge
    ├── vibe/
    │   ├── core/
    │   │   └── vibe_engine.py  ← Pydantic-схемы + PromptCompiler
    │   ├── personas/
    │   │   ├── doc/persona.yaml
    │   │   └── guru/persona.yaml
    │   └── test_transplant.py  ← тест пересборки души
    ├── skills/
    │   ├── neuro-secretary/    ← Telegram userbot (Ghost Monitor)
    │   └── perplexity/         ← web-search skill
    └── memory/
        ├── 00_CORE/            ← идентичность, профиль
        ├── 01_PROJECTS/        ← досье по проектам
        ├── 02_PEOPLE/          ← досье по людям
        ├── 03_KNOWLEDGE/       ← технические инсайты
        └── 04_LOGS/            ← архив
```

### clawbot_isolated (Operational Instance + Marketing)

```
clawbot_isolated/
├── openclaw.json               ← конфигурация (Claude primary, Gemini fallback)
├── run.sh                      ← запуск сервиса
├── openclaw-isolated.service   ← systemd unit
└── .openclaw/workspace/
    ├── SOUL.md                 ← Doc v1.1 (VIBECRAFT-compiled)
    ├── VIBECRAFT.md            ← внутренняя документация VibeCraft для агента
    ├── PILOT_METRICS.md        ← метрики пилота (M1-M4)
    ├── ROLLOUT_GUIDE.md        ← стадии раскатки TG→VK→Pikabu
    ├── TELEGRAM_PILOT_RUNBOOK.md
    ├── vibe/                   ← persona.yaml + compiled prompts
    ├── alex-agent/             ← marketing bot API
    │   ├── src/server.ts
    │   └── config/
    │       ├── rollout.json
    │       └── engagement_policy.json
    ├── eliza/                  ← Eliza workers
    ├── pikabu/                 ← Pikabu satellite
    ├── scripts/                ← operational scripts
    │   ├── set_rollout_stage.js
    │   └── set_read_only.js
    └── skills/
        └── neuro-secretary/
```

---

## 8. Чек-листы

### 8.1. VibeFlow

- [ ] У агента есть фиксированный Boot Sequence (SOUL → USER → STATE → daily → MEMORY)
- [ ] STATE.md обновляется при каждом начале/завершении задачи
- [ ] Crash recovery: при `Status != DONE/IDLE` — задача возобновляется автоматически
- [ ] Ежедневные логи (`memory/YYYY-MM-DD.md`) ведутся
- [ ] Atomic Memory Pipeline настроен (archivist → HEARTBEAT → архивация)
- [ ] MEMORY.md загружается только в приватных сессиях (security)

### 8.2. VibeFix

- [ ] Schema validation: `extra="forbid"` на всех Pydantic-моделях персоны
- [ ] Ghost Mode: бот не маркирует сообщения прочитанными в пилотном режиме
- [ ] Rollout с kill switch: `set_read_only.js` работает
- [ ] KPI gates между стадиями раскатки определены
- [ ] Selective engagement: правила "когда молчать" описаны и соблюдаются

### 8.3. VibeMix

- [ ] Вся идентичность в `persona.yaml`, не в коде
- [ ] PromptCompiler — единственная точка сборки system prompt
- [ ] Несколько персон в одном workspace (разные YAML)
- [ ] Multi-model routing настроен (дорогая модель для души, дешёвая для рутины)
- [ ] Tools описаны в YAML и создаются динамически

### 8.4. VibeMorph

- [ ] `compile_persona.py` работает (полная пересборка)
- [ ] `--behavior-only` работает (mid-session update)
- [ ] Persona Sync Protocol: compiled/doc.md newer than SOUL.md → auto-override
- [ ] Pilot Metrics (M1-M4) определены и отслеживаются
- [ ] Тесты: `validate_personas.py` проходят после каждой правки

---

## 9. Связь с VibeCraft Stack

```
v1.0    VibeSpark       — зачем нужна персона (продуктовое видение)
v1.0    VibeCore        — UI/UX ощущения, атмосфера продукта
v1.1    VibePersona     — кто говорит (vibe: role, voice, emotions, values, taboos)
v1.1    VibeBehavior    — как реагирует (behavior: on_success, on_error, on_offtopic)
v1.1    VibeCases       — как проверяем (тесты, diagnose, логи)
v1.1.1  VibeFlow        — как помнит (память, crash recovery, boot sequence)
v1.1.1  VibeFix         — как выживает (ghost mode, dual deploy, schema validation)
v1.1.1  VibeMix         — как собирается (persona.yaml → PromptCompiler → compiled prompt)
v1.1.1  VibeMorph       — как меняется (hot reload, pilot metrics, transplant)
```

v1.1 дал контракт: "вот что должна уметь персона".  
v1.1.1 доказал: "вот как это работает в продакшене".

Следующий шаг — **v1.2: От персонажа к присутствию** — VibeAgency (проактивность), VibeSocial (межагентные отношения), VibeAdapt (эволюция характера).

---

## 10. Глоссарий

| Термин | Определение |
|--------|------------|
| **Boot Sequence** | Фиксированный порядок загрузки файлов при пробуждении агента |
| **Crash Recovery** | Автоматическое возобновление задачи по STATE.md после краша |
| **Atomic Memory** | Структурированные досье на сущности (один файл = одна сущность) |
| **Archivist** | Скрипт, детектирующий сущности в дневнике и создающий задачи архивации |
| **Ghost Monitor** | Режим чтения сообщений без маркирования "прочитано" |
| **Kill Switch** | Мгновенное отключение всех ответов бота (read-only mode) |
| **Persona Sync** | Протокол обновления идентичности из compiled prompt |
| **Heartbeat** | Периодическая проверка состояния мира и выполнение фоновых задач |
| **Pilot Metrics** | Четыре метрики (M1-M4) для измерения качества интеграции VibeCraft |
| **Transplant** | Перенос персоны между runtime-движками с сохранением идентичности |

---

**Авторы:** VibeCraft Engineering / R&D Holding "Zakharchenko"  
**Последнее обновление:** 2026-02-19  
**Статус:** Production-validated ✅ (Doc_clawbot + clawbot_isolated)
