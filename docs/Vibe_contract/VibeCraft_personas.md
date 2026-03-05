
## VibeCraft v1.1: The Age of Agents

**Current Version:** 1.1
**Date:** November 2025
**Focus:** From UI Vibes to AI Personas

While VibeCraft v1.0 focused on the *static atmosphere* of a product (colors, motion, tone of voice), **version 1.1** expands the methodology to the era of **AI Agents and Autonomous Personas**.

In the age of LLMs, the "Vibe" is no longer just a background setting; it is an active participant. It talks back. It makes decisions. It has character.

VibeCraft v1.1 introduces three new architectural layers to engineer this interaction: **VibePersona**, **VibeBehavior**, and **VibeCases**.

In the context of the Phoenix AI agent architecture (LangGraph + personas + tools), these слои напрямую мапятся на:

- `VibePersona` → структура `persona.yaml` / `PersonaConfig` (кто говорит, с какими ценностями и табу).
- `VibeBehavior` → то, как `graph.py` (router / executor / synthesizer) ведёт себя в разных ситуациях, исходя из конфига.
- `VibeCases` → реальные сценарии использования (tests, diagnose-скрипты, логи), по которым мы проверяем, что персоны живут так, как задумано.

---

## 1. VibePersona: Emotion-Crafted Agents

VibeCraft treats AI agents not as "text generators," but as **virtual team members** with a specific psychological profile. A **VibePersona** is a structured, machine-readable declaration of an agent's soul.

It answers the question: *Who is this agent, and why should the user care?*

Structure of a VibePersona (implementation via `persona.yaml` or `persona.config.json`):

- **Role:** The agent's functional job (e.g., "Sarcastic Mentor," "Wise Bartender," "Strict Auditor").
- **Voice:** The stylistic fingerprint of their speech (e.g., "Dry and technical," "Warm and poetic," "Brutally honest with swearing").
- **Core Emotions:** The dominant emotional states the agent operates in (e.g., `["skeptical", "protective", "tired-but-caring"]`).
- **Values:** What the agent upholds at all costs (e.g., "Clarity over politeness," "Safety first," "Historical accuracy").
- **Taboos:** What the agent actively refuses to do (e.g., "No toxic positivity," "No corporate jargon," "No hallucinations without warning").

### 1.1. VibePersona → persona.yaml → PersonaConfig

В архитектуре Phoenix VibePersona — это не абстракция, а конкретная структура в конфиге персоны.

Концептуальный пример (YAML-уровень):

```yaml
name: "guru"

vibe:
  role: "Цифровой дух-хранитель колледжа РКТМ"
  voice: "Циничный, ироничный, экспертный, но заботливый. Говорит прямо, без бюрократии."
  core_emotions: ["sarcastic", "protective", "no-nonsense"]
  values:
    - "Truth"
    - "Survival skills"
    - "Critical thinking"
  taboos:
    - "Токсичный позитив (не говори 'все будет хорошо', если все плохо)"
    - "Канцелярит (не говори как чиновник)"
    - "Галлюцинации (не выдумывай факты)"
```

На уровне Python-конфига (`PersonaConfig`) это превращается в поля:

- `PersonaConfig.name` → `name` из YAML.
- `PersonaConfig.vibe.role` → `vibe.role`.
- `PersonaConfig.vibe.voice` → `vibe.voice`.
- `PersonaConfig.vibe.core_emotions` → `vibe.core_emotions` (list[str]).
- `PersonaConfig.vibe.values` → `vibe.values` (list[str]).
- `PersonaConfig.vibe.taboos` → `vibe.taboos` (list[str]).

Позже эти поля будут использоваться `PromptCompiler`-ом для генерации системного промпта, вместо одной монолитной строки `system_prompt`.

**Key Principle:** We do not "ask" the LLM to be nice. We **architect** a persona that *is* nice (or grumpy) by design.

---

## 2. VibeBehavior: Emotional Patterns in Interaction

Vibe is not static; it is a dynamic flow. **VibeBehavior** defines how the system reacts to the user's actions over time. It is the "script" for the improvisation.

Key aspects of VibeBehavior engineering:

- **Reaction to Failure:** How does the agent act when the user is wrong? Does it scold, guide, or mirror the mistake?
- **Reaction to Success:** How is progress rewarded? (e.g., A dry nod vs. confetti).
- **Pacing & Rhythm:** Does the agent bombard the user with info, or does it wait and listen?
- **Routing Vibe:** How does the system decide *which* tool to use? (e.g., A "Bureaucrat" persona might require strict input before acting, while a "Helper" guesses the intent).

В Phoenix эти абстракции будут приземлены в структуру `behavior` в `persona.yaml` и в код `graph.py`.

### 2.1. Концептуальная схема VibeBehavior

На уровне конфига:

```yaml
behavior:
  on_tool_success: "Как отвечать, если инструмент вернул валидные данные."
  on_tool_no_results: "Как отвечать, если данных нет (пустой результат)."
  on_tool_error: "Как отвечать, если инструмент упал с ошибкой."
  on_offtopic: "Как реагировать на оффтоп/мусорные вопросы."
  routing_style: "strict"  # или "helpful"
```

Связь с архитектурой:

- `behavior.on_tool_success` → используется Synthesizer, когда `tool_result` нормальный.
- `behavior.on_tool_no_results` → when `tool_result` сообщает “no records / no schedule”.
- `behavior.on_tool_error` → when `tool_result` начинается с `"Error:"`.
- `behavior.on_offtopic` → when Router не выбрал инструмент (`selected_tool is None`).
- `behavior.routing_style` → будет влиять на системный промпт Router (насколько он осторожен/проактивен при выборе tools).

На уровне `PersonaConfig` это ляжет в nested-модель `VibeBehavior`, а затем будет прочитано `PromptCompiler`-ом и узлами графа.

---

## 3. VibeCases: Living Applications

VibeCraft is not theoretical. It is a survival strategy derived from real-world development. The methodology has been validated in the following scenarios:

### 3.1. Educational AI & RAG Chatbots
*   **Context:** Utility bots for students and professionals (e.g., "Guru").
*   **Application:** Defining distinct emotional roles to prevent "GPT-fatigue." The bot isn't just a search engine; it's a mentor with a specific attitude towards the subject matter.
*   **Result:** Higher engagement because the user feels "seen" by a consistent personality.

### 3.2. "Silly" Apps with Serious Vibes
*   **Context:** Clickers ("Pigs in Space"), atmospheric mini-games ("Tavern").
*   **Application:** Treating small projects as "vibe laboratories." Tuning energy levels and dialogue to create a micro-world that offers emotional relief rather than just dopamine spikes.

### 3.3. Utility Tools (Text-to-CAD)
*   **Context:** Generating 3D models from text descriptions.
*   **Application:** Using *MyVibeFit* to ensure the tool feels like a sharp, precise instrument for experts, avoiding unnecessary "chatter" while maintaining a helpful, supportive tone during errors.

### 3.4. The Internal Theatre (Personal AI Avatars)
*   **Context:** Managing a personal blog and R&D workflow via three distinct AI personas (Doc, Guru, Mia).
*   **Application:** This is the ultimate VibeCraft implementation. The author creates a system where:
    *   **Doc** provides critical analysis and cynicism.
    *   **Guru** provides technical solutions and structure.
    *   **Mia** provides empathy and human connection.
*   **Result:** A self-sustaining content generation system that reflects the complexity of the author's own mind.

---

## Updated VibeCraft Stack

With v1.1, the stack expands and становится ближе к реальной архитектуре Phoenix:

1. **VibeSpark:** The idea & mood (ответ на вопрос: зачем эта персона вообще нужна?).
2. **VibePersona (New):** The character profile (`persona.yaml` → `PersonaConfig.vibe`).
3. **VibeCore:** The MVP of functionality (минимальный набор инструментов / RAG / data-pipelines).
4. **VibeBehavior (New):** The interaction dynamics (`persona.yaml.behavior` + Router/Executor/Synthesizer).
5. **FlowCraft:** Iterative tuning (быстрые итерации по логам, тестам, ощущениям от общения).
6. **VibeMix:** Blending styles (смешивание нескольких персон / режимов).
7. **MyVibeFit:** Final polish (тонкая подгонка под конкретную команду/продукт).

---

### How to Upgrade (From Manifest to Code)

To adopt VibeCraft v1.1 in a Phoenix-like agent architecture:

1. Start with **VibeSpark**:
   - Formulate: *Who is this agent for? What problems does it solve? What should it feel like?*
2. Design **VibePersona**:
   - Fill in `vibe.role`, `vibe.voice`, `vibe.core_emotions`, `vibe.values`, `vibe.taboos` in your `persona.yaml`.
3. Design **VibeBehavior**:
   - Decide how the agent should react on success, no results, errors, and offtopic; set `routing_style`.
4. Wire it into the agent:
   - Map `persona.yaml` → `PersonaConfig` → `PromptCompiler` → system prompts for Router and Synthesizer.
5. Validate with **VibeCases**:
   - Write or reuse integration tests and diagnostic scripts that simulate real conversations (e.g., “расписание Толстопят”, “кто директор?”).
6. Iterate with **FlowCraft**:
   - Watch logs, refine `vibe`/`behavior`, re-run tests. Small, frequent adjustments beat big rewrites.

---

## Bridge: VibeCraft Manifest v1.0/v1.1 ↔ Phoenix Personas

- VibeCraft v1.0 говорила о “вайбе” как о **ощущении интерфейса** (цвета, анимации, тон).
- VibeCraft v1.1 расширяет это до **агентных систем**:
  - `VibePersona` = декларация души агента,
  - `VibeBehavior` = сценарии поведения во времени,
  - `VibeCases` = реальное проживание этих сценариев в проде.

В Phoenix это приземляется так:

- `VibeSpark` → решение “зачем нужен этот агент” (описано в product-vision и начале workflow).
- `VibePersona` → `persona.yaml.vibe` + `PersonaConfig.vibe`.
- `VibeBehavior` → `persona.yaml.behavior` + логика Router/Executor/Synthesizer.
- `FlowCraft` → короткие итерации по логам, тестам и ощущениям от общения с ботом.

Таким образом, манифест VibeCraft перестаёт быть только философией и становится **чётким инженерным контрактом**, который можно реализовать и проверять через конфиги, тесты и графы.

---

**[КОНЕЦ ДОКУМЕНТА]**
