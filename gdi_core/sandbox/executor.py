"""Build123d Code Executor — Sandbox.

Executes generated build123d Python code in a subprocess,
captures output/errors, and returns the path to the generated STEP file.
"""

import os
import sys
import subprocess
import tempfile
import logging
import textwrap
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Timeout for code execution (seconds)
DEFAULT_TIMEOUT = 90


def execute_build123d_code(
    code: str,
    output_dir: str,
    output_filename: str = "generated.step",
    timeout: int = DEFAULT_TIMEOUT,
) -> Optional[str]:
    """Execute build123d Python code in a subprocess and return path to STEP file.

    The sandbox:
    - Runs code in a fresh Python subprocess (safe isolation).
    - Patches `export_step` calls to use our managed output path.
    - Captures stderr for error reporting.
    - Enforces a timeout to prevent runaway executions.

    Args:
        code: Valid Python code using build123d.
        output_dir: Directory where the STEP file will be written.
        output_filename: Name for the output STEP file.
        timeout: Execution timeout in seconds.

    Returns:
        Absolute path to generated STEP file, or None on failure.
    """
    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)
    step_path = str((output_dir_path / output_filename).resolve())

    # Normalize line endings and strip markdown fences just in case
    code = code.replace("\\r\\n", "\\n").strip()

    # Inject STEP output path — replace any existing export_step call
    # or append it at the end if 'part' variable exists
    patched_code = _inject_step_export(code, step_path)

    # Write to a temp file
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        prefix="gdi_sandbox_",
        dir=output_dir,
        delete=False,
        encoding="utf-8",
    ) as tmp:
        tmp.write(patched_code)
        tmp_path = tmp.name

    logger.info(f"Executing build123d code: {tmp_path} → {step_path}")

    try:
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(output_dir_path),
        )

        if result.returncode != 0:
            logger.error(
                f"Execution failed (returncode={result.returncode}):\\n"
                f"STDOUT: {result.stdout[:500]}\\n"
                f"STDERR: {result.stderr[:1000]}"
            )
            return None

        # Verify STEP file was actually created
        if not Path(step_path).exists():
            logger.error(
                f"Code ran successfully but STEP file not created at {step_path}.\\n"
                f"STDOUT: {result.stdout[:500]}"
            )
            return None

        logger.info(
            f"Execution succeeded. STEP file: {step_path} "
            f"({Path(step_path).stat().st_size} bytes)"
        )
        return step_path

    except subprocess.TimeoutExpired:
        logger.error(f"Execution timed out after {timeout}s: {tmp_path}")
        return None

    except Exception as e:
        logger.error(f"Unexpected execution error: {e}")
        return None

    finally:
        # Clean up temp script
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _inject_step_export(code: str, step_path: str) -> str:
    """Inject or replace the STEP export call in generated code.

    Ensures the output always goes to our managed path.

    Args:
        code: Original generated code.
        step_path: Absolute path for the STEP output.

    Returns:
        Modified code with correct export call.
    """
    # Escape backslashes for Windows paths in Python string
    safe_path = step_path.replace("\\\\", "/").replace("\\", "/")
    export_line = f'part.export_step("{safe_path}")'

    lines = code.splitlines()
    new_lines = []
    export_injected = False

    for line in lines:
        stripped = line.strip()
        # Replace any existing export_step call regardless of path
        if "export_step(" in stripped:
            new_lines.append(export_line)
            export_injected = True
        else:
            new_lines.append(line)

    if not export_injected:
        # Append at end — build123d context manager should have 'part'
        new_lines.append("")
        new_lines.append(f"# GDI: export STEP for IoU validation")
        new_lines.append(export_line)

    return "\\n".join(new_lines)
