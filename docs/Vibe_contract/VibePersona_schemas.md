## VibePersona / VibeBehavior / PersonaConfig Schemas (Reference)

Этот документ фиксирует эталонные схемы Pydantic-моделей для поддержки VibeCraft v1.1.

Важно: это **дизайн-справочник**, а не строгое отражение текущего кода. Реальная имплементация может слегка отличаться, но должна сохранять те же идеи и поля.

---

## 1. VibePersona (статический слой)

VibePersona описывает “кто говорит” — роль, голос, эмоции, ценности, табу.

```python
from typing import List
from pydantic import BaseModel


class VibePersona(BaseModel):
    """Static emotional/identity profile of an AI persona.

    Maps directly to the `vibe` block in persona.yaml.
    """

    role: str
    voice: str
    core_emotions: List[str]
    values: List[str]
    taboos: List[str]
```

Маппинг на YAML:

```yaml
vibe:
  role: "Цифровой дух-хранитель колледжа РКТМ"
  voice: "Циничный, ироничный, экспертный, но заботливый."
  core_emotions: ["sarcastic", "protective", "no-nonsense"]
  values:
    - "Truth"
    - "Survival skills"
    - "Critical thinking"
  taboos:
    - "Токсичный позитив"
    - "Канцелярит"
    - "Галлюцинации"
```

---

## 2. VibeBehavior (динамический слой)

VibeBehavior описывает “как персона реагирует” на разные типы исходов и вопросов.

```python
from typing import Literal, Optional
from pydantic import BaseModel


class VibeBehavior(BaseModel):
    """Behavioral patterns for different tool and dialog outcomes.

    Maps to the `behavior` block in persona.yaml.
    """

    on_tool_success: Optional[str] = None
    on_tool_no_results: Optional[str] = None
    on_tool_error: Optional[str] = None
    on_offtopic: Optional[str] = None
    routing_style: Optional[Literal["strict", "helpful"]] = None
```

Пример в YAML:

```yaml
behavior:
  on_tool_success: "Дай точный ответ, но добавь ироничный комментарий или житейский совет."
  on_tool_no_results: "Честно признай, что данных нет. Можно пошутить про бюрократию или несовершенство мира."
  on_tool_error: "Скажи, что что-то сломалось на уровне систем, без обвинения пользователя."
  on_offtopic: "Если вопрос оффтоп — подшути, но мягко, и верни в полезное русло."
  routing_style: "helpful"
```

---

## 3. PersonaConfig (расширенный для VibeCraft)

PersonaConfig объединяет идентичность, поведение и инструменты.

```python
from typing import List, Optional
from pydantic import BaseModel, field_validator


class ToolConfig(BaseModel):
    """Existing tool config (примерно)."""

    name: str
    type: str
    description: str
    config: dict
    router_examples: Optional[List[str]] = None


class PersonaConfig(BaseModel):
    """Persona configuration for Phoenix agent.

    Supports both legacy `system_prompt` and new VibeCraft-style
    `vibe` + `behavior` for a soft migration.
    """

    name: str
    system_prompt: Optional[str] = None  # legacy
    vibe: Optional[VibePersona] = None
    behavior: Optional[VibeBehavior] = None
    tools: List[ToolConfig]

    @field_validator("system_prompt", mode="after")
    @classmethod
    def ensure_prompt_or_vibe(cls, value: Optional[str], info):
        """Ensure we have at least one identity source."""
        data = info.data
        if not value and not data.get("vibe"):
            raise ValueError(
                "PersonaConfig must define either legacy `system_prompt` "
                "or structured `vibe` block."
            )
        return value
```

Идея:

- На ранних этапах миграции:
  - старые персоны используют только `system_prompt`,
  - новые/экспериментальные — `vibe` + `behavior`.
- Валидатор гарантирует, что у нас **есть хоть какой-то** источник идентичности.

---

## 4. Связь со слойми Router / Executor / Synthesizer

- `PersonaConfig.vibe` → используется `PromptCompiler` для сборки системных промптов.
- `PersonaConfig.behavior` → используется:
  - Synthesizer — для выбора формулировок при разных `tool_status` (success / no_results / error / none).
  - Router — для подсказки стиля выбора инструментов (`routing_style`).
- `PersonaConfig.tools` → как и раньше, управляет составом и описаниями инструментов, видимых LLM.

Эти схемы задают **контракт данных**, поверх которого можно безопасно развивать архитектуру VibeCraft-персон.


