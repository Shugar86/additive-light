"""Synthesizer - Real LLM Code Generation via OpenRouter.

Generates build123d code from YAML telemetry using LangChain + OpenRouter.
Supports retry with structured Judge feedback.
"""

import os
import logging
import yaml
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

from ..models.yaml_contract import SensorTelemetry

logger = logging.getLogger(__name__)

# Load .env from project root (or use already set env vars)
_env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=_env_path, override=False)

# Available models on OpenRouter (for reference)
MODELS = {
    "gemini-2.5-pro": "google/gemini-2.5-pro",
    "gemini-3-pro": "google/gemini-3-pro-preview",
    "claude-sonnet": "anthropic/claude-sonnet-4.6",
    "deepseek-v3": "deepseek/deepseek-v3",
    "kimi-k2": "moonshotai/kimi-k2-instruct",
}

SYSTEM_PROMPT = """You are an expert mechanical engineer and CAD programmer specializing in build123d.
Your task is to generate parametric Python code from sensor telemetry data.

MANDATORY RULES:
1. Do NOT use visual assumptions. Rely ONLY on the Parameters in the YAML.
2. Use 'with BuildPart() as part:' context manager. Always name the variable 'part'.
3. Round all floats to 1 decimal place (e.g., 12.3, not 12.345).
4. If cross_section == "Rectangle": use Box(width, depth, height), NOT Cylinder.
5. If cross_section == "Circle": use Cylinder(radius=R, height=H).
6. For holes in CONSTANT_PROFILE_WITH_HOLES: use PolarLocations + Cylinder with mode=Mode.SUBTRACT.
7. Export: add `part.export_step("output.step")` as the LAST line.
8. Output ONLY valid Python code — no markdown, no triple backticks.

STRUCTURE your response as:
# Thought_Process:
# [step-by-step CAD reasoning — required before code]

from build123d import *
[code here]
part.export_step("output.step")
"""


class Synthesizer:
    """Generate build123d code from sensor telemetry via a real LLM."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        temperature: float = 0.1,
        api_key: Optional[str] = None,
    ):
        """Initialize synthesizer.

        Args:
            model_name: OpenRouter model ID (e.g. 'google/gemini-2.5-pro').
                        Falls back to GDI_DEFAULT_MODEL env var, then gemini-2.5-pro.
            temperature: Sampling temperature (low = more deterministic).
            api_key: OpenRouter API key. Falls back to OPENROUTER_API_KEY env var.
        """
        self.model_name = (
            model_name
            or os.environ.get("GDI_DEFAULT_MODEL", "google/gemini-2.5-pro")
        )
        self.temperature = temperature
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")

        if not self.api_key:
            logger.warning(
                "No OPENROUTER_API_KEY found. LLM synthesis will fail. "
                "Set it in .env or as an environment variable."
            )

        logger.info(f"Synthesizer initialized: model={self.model_name}")

    def _build_llm(self):
        """Lazily create the LangChain LLM client."""
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            raise ImportError(
                "langchain-openai is required: pip install langchain-openai"
            )

        return ChatOpenAI(
            model=self.model_name,
            openai_api_key=self.api_key,
            openai_api_base="https://openrouter.ai/api/v1",
            temperature=self.temperature,
            default_headers={
                "HTTP-Referer": "https://github.com/additive-light",
                "X-Title": "GDI Core Pipeline",
            },
        )

    def generate_code(
        self,
        telemetry: SensorTelemetry,
        previous_attempt: Optional[str] = None,
        feedback: Optional[str] = None,
    ) -> str:
        """Generate build123d code from telemetry.

        Args:
            telemetry: Sensor telemetry with zones and parameters.
            previous_attempt: Previous code attempt (for retry).
            feedback: Judge feedback string (for retry).

        Returns:
            Generated Python code string.
        """
        from langchain_core.messages import HumanMessage, SystemMessage

        # Serialize telemetry to YAML for the prompt
        telemetry_yaml = yaml.dump(
            telemetry.to_yaml_dict(),
            default_flow_style=False,
            allow_unicode=True,
        )

        # Build user message
        if previous_attempt and feedback:
            user_content = (
                f"SENSOR TELEMETRY:\n```yaml\n{telemetry_yaml}\n```\n\n"
                f"PREVIOUS ATTEMPT (FAILED):\n```python\n{previous_attempt}\n```\n\n"
                f"JUDGE FEEDBACK:\n{feedback}\n\n"
                f"Fix the issues and generate corrected build123d code now:"
            )
        else:
            user_content = (
                f"SENSOR TELEMETRY:\n```yaml\n{telemetry_yaml}\n```\n\n"
                f"Generate build123d code now:"
            )

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_content),
        ]

        try:
            llm = self._build_llm()
            logger.info(f"Calling LLM ({self.model_name}) for synthesis...")
            response = llm.invoke(messages)
            raw_code = response.content

            # Strip markdown code fences if model ignores the instructions
            code = _strip_markdown(raw_code)

            logger.info(
                f"LLM synthesis complete — {len(code.splitlines())} lines generated"
            )
            return code

        except Exception as e:
            logger.error(f"LLM synthesis failed: {e}")
            raise

    def generate_thought_process(self, telemetry: SensorTelemetry) -> str:
        """Generate thought process string for SCoT logging.

        Args:
            telemetry: Sensor telemetry.

        Returns:
            Human-readable thought process string.
        """
        lines = ["# Thought Process:"]
        for zone in telemetry.topological_zones:
            lines.append(f"# Zone {zone.zone_id}: {zone.geometry.value} / {zone.cross_section.value}")
            lines.append(f"#   Hint: {zone.sensor_hint}")
            lines.append(f"#   Confidence: {zone.confidence:.2f}")
        lines.append("#")
        lines.append("# Build strategy will be generated by LLM based on these zones.")
        return "\n".join(lines)


def _strip_markdown(text: str) -> str:
    """Remove markdown code fences from LLM output."""
    text = text.strip()
    # Remove ```python ... ``` or ``` ... ``` wrappers
    if text.startswith("```"):
        lines = text.splitlines()
        # Drop first line (``` or ```python) and last ``` if present
        if lines[-1].strip() == "```":
            lines = lines[1:-1]
        else:
            lines = lines[1:]
        text = "\n".join(lines)
    return text.strip()
