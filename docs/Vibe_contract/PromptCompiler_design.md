## PromptCompiler Design (VibeCraft v1.1)

Этот документ описывает цель, интерфейс и примеры использования компонента `PromptCompiler` в архитектуре Phoenix.

Важно: это **дизайн-док**, а не прямое руководство к немедленной имплементации. Он фиксирует ожидаемый контракт и формат промптов.

---

## 1. Цель PromptCompiler

Проблема:

- Исторически `system_prompt` был одной большой строкой в `persona.yaml`.
- Любое изменение стиля/поведения требовало переписывать всё эссе целиком.

Цель `PromptCompiler`:

- Собирать системные промпты **программно** из структур:
  - `PersonaConfig.vibe` (кто говорит),
  - `PersonaConfig.behavior` (как реагирует),
  - контекст выполнения (например, статус работы инструмента).
- Обеспечить:
  - читаемость и предсказуемость промптов,
  - возможность диффов и автогенерации,
  - мягкую миграцию с legacy `system_prompt`.

---

## 2. Интерфейс (предлагаемый контракт)

Базовый интерфейс для синтезатора:

```python
from typing import Literal
from src.agents.personas.loader import PersonaConfig


class PromptCompiler:
    """Compile system prompts for different nodes based on PersonaConfig.

    Initial scope: synthesizer. Later can be extended to router.
    """

    def compile_synthesizer_prompt(
        self,
        persona: PersonaConfig,
        tool_status: Literal["success", "no_results", "error", "none"] = "none",
    ) -> str:
        """Build system prompt for the Synthesizer node.

        - If persona.vibe is present, composes a structured prompt
          using vibe + behavior.
        - Otherwise, falls back to legacy persona.system_prompt.
        """
        ...
```

В будущем можно добавить:

```python
    def compile_router_prompt(self, persona: PersonaConfig) -> str:
        """Build system prompt for the Router node (optional, Step 2)."""
        ...
```

---

## 3. Структура собранного промпта (Synthesizer)

### 3.1. Для персоны с VibePersona/VibeBehavior (новый путь)

Пример для Guru (концептуально):

```text
IDENTITY:
You are an AI persona named "guru".
Role: Цифровой дух-хранитель колледжа РКТМ.
Voice: Циничный, ироничный, экспертный, но заботливый. Говорит прямо, без бюрократии.
Core emotions: sarcastic, protective, no-nonsense.

DIRECTIVES:
- Values: Truth; Survival skills; Critical thinking.
- ABSOLUTE TABOOS:
  - Токсичный позитив (не говори "все будет хорошо", если все плохо).
  - Канцелярит (не говори как чиновник).
  - Галлюцинации (не выдумывай факты).

BEHAVIORAL PATTERNS:
- When tool returns valid data (success):
  Дай точный ответ, но добавь ироничный комментарий или житейский совет.
- When tool returns no results:
  Честно признай, что данных нет. Можно пошутить про бюрократию или несовершенство мира.
- When tool returns error:
  Скажи, что что-то сломалось на уровне систем, без обвинения пользователя.
- When question is offtopic/noise:
  Если вопрос оффтоп — подшути, но мягко, и верни в полезное русло.

CURRENT CONTEXT:
- Tool status: success

You must answer in accordance with the patterns above.
```

Примечания:

- Блок `CURRENT CONTEXT` может формироваться из статуса выполнения инструмента:
  - `success` / `no_results` / `error` / `none`.
- Основная идея — LLM получает **единый, структурированный** протокол поведения.

### 3.2. Для legacy персоны (только system_prompt)

Если у персоны нет `vibe`:

```python
if persona.vibe:
    # новый путь
else:
    return persona.system_prompt or ""
```

То есть `PromptCompiler` не ломает существующие конфиги, пока они не мигрированы.

---

## 4. Пример вызова из Synthesizer (концептуально)

Псевдокод (не фактическая имплементация):

```python
compiler = PromptCompiler()

def _synthesizer_node(self, state: AgentState) -> dict[str, Any]:
    question = state["question"]
    tool_result = state["tool_result"]

    tool_status = detect_tool_status(tool_result)  # "success" / "no_results" / "error" / "none"

    system_message_text = compiler.compile_synthesizer_prompt(
        persona=self.persona_config,
        tool_status=tool_status,
    )

    system_message = SystemMessage(content=system_message_text)
    user_prompt = build_user_prompt(question, tool_result)

    messages = [system_message, HumanMessage(content=user_prompt)]
    response = llm.invoke(messages)
    ...
```

Функция `detect_tool_status` может быть простой эвристикой на основе `tool_result`, а позже — полноценным анализом структуры ответа.

---

## 5. Router Prompt (эскиз для будущих шагов)

Хотя текущий дизайн-фокус — Synthesizer, уже сейчас стоит зафиксировать намерение для роутера.

Идея: использовать те же `vibe` и `behavior.routing_style` для настройки роутинга:

```text
IDENTITY:
You are a routing assistant for the persona "guru".
Role: Цифровой дух-хранитель колледжа РКТМ.
Routing style: helpful.

TOOLS:
- factual_db_tool: Поиск фактов о сотрудниках, их ролях и специальностях.
- find_schedule: Поиск расписания занятий по преподавателю, группе или дню недели.

ROUTING INSTRUCTIONS:
- Prefer calling a tool when it can reasonably help the user,
  even if the question is slightly underspecified.
- If no tool is suitable, do not call any tool and let the synthesizer
  answer based on its own knowledge (if allowed).
```

Это может быть реализовано отдельным методом `compile_router_prompt` в следующих итерациях.

---

## 6. Резюме

- `PromptCompiler` — это “форматтер души”:
  - принимает `PersonaConfig` + контекст (tool_status),
  - возвращает структурированный системный промпт.
- Поддерживает мягкую миграцию:
  - сначала работает только для Synthesizer с fallback на `system_prompt`,
  - позже может быть расширен на Router.
- Даёт:
  - меньше хаоса в промптах,
  - сильную связь между VibeCraft-идеологией и реальным кодом,
  - возможность конфигурировать поведение агентной системы как данные, а не как эссе.


