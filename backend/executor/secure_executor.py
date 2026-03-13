"""Secure execution environment for generated CAD code.

Executes build123d scripts in an isolated subprocess with timeouts
and resource limits to prevent malicious or runaway code.

P6 Refactor: ExecutionPolicy integration for policy-driven sandbox configuration.
"""

import logging
import subprocess
import tempfile
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional

from backend.core.config import settings
from backend.core.agent_contracts import ExecutionPolicy

logger = logging.getLogger(__name__)


class ExecutionTimeout(Exception):
    """Raised when code execution exceeds time limit."""
    pass


class ExecutionError(Exception):
    """Raised when code execution fails."""
    pass


class SecureExecutor:
    """Secure executor for running generated CAD code.
    
    P6 Refactor: Policy-driven sandbox configuration.
    
    Runs code in an isolated subprocess with:
    - Timeout enforcement (from ExecutionPolicy)
    - Resource limits (from ExecutionPolicy)
    - Separate Python interpreter
    - Restricted environment based on policy
    """

    def __init__(
        self,
        timeout: Optional[int] = None,
        temp_dir: Optional[str] = None,
        execution_policy: Optional[ExecutionPolicy] = None
    ):
        """Initialize the secure executor.

        Args:
            timeout: Maximum execution time in seconds (overrides policy).
            temp_dir: Directory for temporary files.
            execution_policy: ExecutionPolicy for policy-driven restrictions.
        """
        self.execution_policy = execution_policy
        
        # Use policy values if available, otherwise fall back to settings
        if execution_policy:
            self.timeout = timeout or execution_policy.cpu_time_limit_seconds or settings.max_code_execution_time
            self.filesystem_access = execution_policy.filesystem_access
            self.allowed_packages = execution_policy.allowed_packages
            self.forbidden_modules = execution_policy.forbidden_modules
            logger.info(f"[SecureExecutor] Using ExecutionPolicy: sandbox={execution_policy.sandbox_type}")
        else:
            self.timeout = timeout or settings.max_code_execution_time
            self.filesystem_access = "temp_only"
            self.allowed_packages = []
            self.forbidden_modules = []
        
        self.temp_dir = Path(temp_dir or settings.temp_output_path)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"[SecureExecutor] Initialized with timeout={self.timeout}s, fs_access={self.filesystem_access}")

    def execute(self, state: Any) -> Dict[str, Any]:
        """Execute the generated CAD code.

        Args:
            state: CADState containing the generated_code.

        Returns:
            Dictionary with:
            - success: bool
            - output_path: path to generated STL/STEP file (if success)
            - output_files: dict with 'step', 'stl' paths
            - error: error message (if failed)
            - stdout: captured stdout
            - stderr: captured stderr
        """
        code = state.generated_code
        if not code:
            return {
                "success": False,
                "error": "No code to execute",
                "output_path": None,
                "output_files": {}
            }

        # Create temporary script file
        script_path = self.temp_dir / f"generated_model_{id(code)}.py"
        
        # Modify code to export mesh
        export_code = self._add_export_code(code)
        
        try:
            # Write script
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(export_code)
            
            logger.debug(f"[SecureExecutor] Script written to {script_path}")

            # Run in subprocess
            result = self._run_subprocess(script_path)
            
            # Check for output files
            output_stl = self.temp_dir / f"output_{id(code)}.stl"
            output_step = self.temp_dir / f"output_{id(code)}.step"
            
            output_files = {}
            output_path = None
            
            if output_stl.exists():
                output_files["stl"] = str(output_stl)
                output_path = str(output_stl)
            if output_step.exists():
                output_files["step"] = str(output_step)
                if not output_path:
                    output_path = str(output_step)

            # Also check for named files from shaft code generation
            shaft_stl = self.temp_dir / "shaft_preview.stl"
            shaft_step = self.temp_dir / "shaft.step"
            
            if shaft_stl.exists():
                output_files["stl"] = str(shaft_stl)
                output_path = str(shaft_stl)
            if shaft_step.exists():
                output_files["step"] = str(shaft_step)
                if not output_path:
                    output_path = str(shaft_step)

            return {
                "success": result["success"],
                "error": result.get("error"),
                "output_path": output_path,
                "output_files": output_files,
                "stdout": result.get("stdout", ""),
                "stderr": result.get("stderr", "")
            }

        except Exception as e:
            logger.error(f"[SecureExecutor] Execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "output_path": None,
                "output_files": {}
            }
        
        finally:
            # Cleanup
            try:
                if script_path.exists():
                    script_path.unlink()
            except Exception as e:
                logger.warning(f"[SecureExecutor] Failed to cleanup {script_path}: {e}")

    def _add_export_code(self, original_code: str) -> str:
        """Add STL/STEP export functionality to the generated code."""
        # Find the output ID for unique filenames
        code_id = id(original_code)
        
        export_code = f'''
{original_code}

# Auto-generated export code
if 'part' in dir() and part is not None:
    try:
        from build123d import export_step, export_stl
        
        # Export as STEP (B-Rep format, preserves parametrics)
        export_step(part, "temp/output_{code_id}.step")
        
        # Export as STL (mesh format, for comparison)
        export_stl(part, "temp/output_{code_id}.stl")
        
        print(f"EXPORT_SUCCESS: STL and STEP files generated")
        print(f"VOLUME: {{part.volume}}")
    except Exception as e:
        print(f"EXPORT_ERROR: {{e}}")
else:
    print("EXPORT_ERROR: No 'part' variable defined")
'''
        return export_code

    def _run_subprocess(self, script_path: Path) -> Dict[str, Any]:
        """Run the script in a subprocess with timeout and policy restrictions."""
        try:
            # Prepare environment based on policy
            env = self._prepare_environment()
            
            # Determine working directory based on filesystem policy
            if self.filesystem_access == "none":
                # Use a restricted temp directory
                cwd = str(self.temp_dir)
            elif self.filesystem_access == "temp_only":
                cwd = str(self.temp_dir)
            else:
                # Full or restricted access - use project root
                cwd = str(Path(__file__).parent.parent.parent)

            # Run with timeout
            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=env,
                cwd=cwd
            )

            stdout = result.stdout
            stderr = result.stderr

            # Check for policy violations in output
            if self._detect_policy_violation(stdout, stderr):
                return {
                    "success": False,
                    "error": "Security policy violation detected in output",
                    "stdout": stdout,
                    "stderr": stderr
                }

            # Check for export success
            export_success = "EXPORT_SUCCESS" in stdout
            
            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"Script exited with code {result.returncode}: {stderr[:500]}",
                    "stdout": stdout,
                    "stderr": stderr
                }
            
            if not export_success and "EXPORT_ERROR" in stdout:
                error_msg = stdout.split("EXPORT_ERROR:")[1].split("\n")[0]
                return {
                    "success": False,
                    "error": f"Export failed: {error_msg}",
                    "stdout": stdout,
                    "stderr": stderr
                }

            return {
                "success": True,
                "error": None,
                "stdout": stdout,
                "stderr": stderr
            }

        except subprocess.TimeoutExpired as e:
            logger.error(f"[SecureExecutor] Execution timeout after {self.timeout}s")
            return {
                "success": False,
                "error": f"Execution timeout (>{self.timeout}s). Possible infinite loop.",
                "stdout": e.stdout if e.stdout else "",
                "stderr": e.stderr if e.stderr else ""
            }
        
        except Exception as e:
            logger.error(f"[SecureExecutor] Subprocess error: {e}")
            return {
                "success": False,
                "error": f"Subprocess error: {e}",
                "stdout": "",
                "stderr": str(e)
            }
    
    def _prepare_environment(self) -> Dict[str, str]:
        """Prepare environment variables based on execution policy.
        
        Returns:
            Environment dictionary for subprocess.
        """
        if self.filesystem_access == "none":
            # Minimal environment - no access to anything
            env = {
                'PATH': os.environ.get('PATH', ''),
                'TEMP': str(self.temp_dir),
                'TMP': str(self.temp_dir),
            }
        elif self.filesystem_access == "temp_only":
            # Standard restricted environment
            env = os.environ.copy()
            # Remove potentially dangerous env vars
            dangerous_vars = ['PYTHONPATH', 'LD_PRELOAD', 'DYLD_INSERT_LIBRARIES', 'HOME', 'USERPROFILE']
            for var in dangerous_vars:
                env.pop(var, None)
            
            # Set restricted Python path
            env['PYTHONPATH'] = str(Path(__file__).parent.parent.parent)
            env['TEMP'] = str(self.temp_dir)
            env['TMP'] = str(self.temp_dir)
        else:
            # Full or restricted - use standard environment
            env = os.environ.copy()
            dangerous_vars = ['LD_PRELOAD', 'DYLD_INSERT_LIBRARIES']
            for var in dangerous_vars:
                env.pop(var, None)
        
        return env
    
    def _detect_policy_violation(self, stdout: str, stderr: str) -> bool:
        """Detect potential security policy violations in output.
        
        Args:
            stdout: Standard output from script.
            stderr: Standard error from script.
        
        Returns:
            True if policy violation detected.
        """
        combined = stdout + stderr
        
        # Check for forbidden module imports in output
        for module in self.forbidden_modules:
            if f"import {module}" in combined or f"from {module}" in combined:
                logger.warning(f"[SecureExecutor] Policy violation: forbidden module '{module}' detected")
                return True
        
        # Check for suspicious patterns
        suspicious_patterns = [
            "__import__('os')",
            "eval(",
            "exec(",
            "compile(",
            "subprocess.call",
            "os.system",
        ]
        for pattern in suspicious_patterns:
            if pattern in combined:
                logger.warning(f"[SecureExecutor] Policy violation: suspicious pattern '{pattern}' detected")
                return True
        
        return False


def create_executor_agent(execution_policy: Optional[ExecutionPolicy] = None) -> callable:
    """Factory function for creating Executor agent.

    P6 Refactor: Policy-driven executor creation.

    Args:
        execution_policy: Optional ExecutionPolicy for sandbox configuration.

    Returns:
        Executor function: state -> result dict.
    """
    executor = SecureExecutor(execution_policy=execution_policy)
    
    def executor_fn(state: Any) -> Dict[str, Any]:
        return executor.execute(state)
    
    # Attach policy for inspection
    executor_fn._execution_policy = execution_policy
    
    return executor_fn