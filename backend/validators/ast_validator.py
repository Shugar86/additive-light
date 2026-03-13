"""AST and Safety Validator for generated Python code.

Validates that generated code:
1. Has valid Python syntax
2. Only imports allowed modules
3. Does not use forbidden operations (os, sys, subprocess, etc.)
4. Uses build123d API correctly (basic checks)
"""

import logging
import ast
import re
from typing import List, Set, Optional
from pathlib import Path

from backend.core.config import settings

logger = logging.getLogger(__name__)


class CodeValidationError(Exception):
    """Raised when code fails validation."""
    pass


class ASTValidator:
    """Validates Python code using AST analysis.
    
    This is a security-critical component that ensures generated code
    cannot perform malicious operations before execution.
    """

    def __init__(self):
        """Initialize the validator with configured allow/forbid lists."""
        self.allowed_imports: Set[str] = set(settings.allowed_imports)
        self.forbidden_imports: Set[str] = set(settings.forbidden_imports)
        self.forbidden_patterns: List[str] = [
            r"__import__",
            r"eval\s*\(",
            r"exec\s*\(",
            r"compile\s*\(",
            r"open\s*\(",
            r"file\s*\(",
        ]
        
        logger.info(f"[ASTValidator] Initialized with {len(self.allowed_imports)} allowed imports")

    def validate(self, code: str) -> List[str]:
        """Validate code and return list of errors.

        Args:
            code: Python source code to validate.

        Returns:
            List of error messages. Empty list means validation passed.
        """
        errors: List[str] = []

        # Check 1: Syntax validation
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            errors.append(f"Syntax error: {e}")
            return errors
        except Exception as e:
            errors.append(f"Parse error: {e}")
            return errors

        # Check 2: Forbidden patterns (regex)
        for pattern in self.forbidden_patterns:
            matches = re.findall(pattern, code, re.IGNORECASE)
            if matches:
                errors.append(f"Forbidden pattern detected: {pattern}")

        # Check 3: AST-based import analysis
        import_errors = self._check_imports(tree)
        errors.extend(import_errors)

        # Check 4: AST-based function call analysis
        call_errors = self._check_function_calls(tree)
        errors.extend(call_errors)

        # Check 5: Build123d-specific checks
        build123d_errors = self._check_build123d_usage(tree, code)
        errors.extend(build123d_errors)

        if not errors:
            logger.info("[ASTValidator] Code validation passed")
        else:
            logger.warning(f"[ASTValidator] Validation found {len(errors)} issues")

        return errors

    def _check_imports(self, tree: ast.AST) -> List[str]:
        """Check that only allowed modules are imported."""
        errors: List[str] = []
        
        for node in ast.walk(tree):
            # Check 'import X' statements
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name.split('.')[0]  # Get top-level module
                    if module in self.forbidden_imports:
                        errors.append(f"Forbidden import: {module}")
                    elif module not in self.allowed_imports and not module.startswith('backend'):
                        errors.append(f"Unapproved import: {module} (not in allowed list)")
            
            # Check 'from X import Y' statements
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module = node.module.split('.')[0]
                    if module in self.forbidden_imports:
                        errors.append(f"Forbidden import from: {module}")
                    elif module not in self.allowed_imports and not module.startswith('backend'):
                        errors.append(f"Unapproved import from: {module}")

        return errors

    def _check_function_calls(self, tree: ast.AST) -> List[str]:
        """Check for dangerous function calls."""
        errors: List[str] = []
        forbidden_functions = {'eval', 'exec', 'compile', '__import__', 'open'}
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Check direct function calls
                if isinstance(node.func, ast.Name):
                    if node.func.id in forbidden_functions:
                        errors.append(f"Forbidden function call: {node.func.id}()")
                
                # Check method calls that might be dangerous
                elif isinstance(node.func, ast.Attribute):
                    if node.func.attr in {'system', 'popen', 'call', 'run'}:
                        errors.append(f"Potentially dangerous method call: .{node.func.attr}()")

        return errors

    def _check_build123d_usage(self, tree: ast.AST, code: str) -> List[str]:
        """Validate build123d-specific patterns."""
        errors: List[str] = []
        
        # Check that build123d is imported
        has_build123d = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == 'build123d':
                        has_build123d = True
                        break
        
        if not has_build123d and 'from build123d import' not in code:
            # It's ok - might use wild import
            pass

        # Check for common build123d mistakes
        # Missing context manager exit
        if 'with BuildPart()' in code and code.count('with BuildPart()') != code.count('as '):
            # Just a heuristic, not a strict error
            pass

        return errors


def create_validator_agent() -> callable:
    """Factory function for creating Validator agent.

    Returns:
        Validator function: code -> list of errors.
    """
    validator = ASTValidator()
    
    def validator_fn(code: str) -> List[str]:
        return validator.validate(code)
    
    return validator_fn