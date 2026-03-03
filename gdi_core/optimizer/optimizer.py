"""Optimizer - Refactorer Node.

Transforms raw LLM-generated code to engineering standards:
- Extracts hardcoded values into named parameters
- Beautifies dimensions (rounds to engineering standards)
- Adds proper documentation
"""

import re
import ast
from typing import Tuple, List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


def beautify_dimension(value: float) -> float:
    """Beautify a dimension value to engineering standards.
    
    Rounds to appropriate precision based on magnitude:
    - Values < 1mm: round to 0.1mm
    - Values < 10mm: round to 0.1mm or nearest 0.5mm
    - Values < 100mm: round to nearest 0.5mm or integer
    - Values >= 100mm: round to nearest integer
    
    Args:
        value: Raw dimension value
        
    Returns:
        Beautified value
    """
    abs_val = abs(value)
    
    if abs_val < 1.0:
        # Very small: keep 1 decimal
        return round(value, 1)
    elif abs_val < 10.0:
        # Small: round to 0.5 or nearest 0.1
        rounded_05 = round(value * 2) / 2
        if abs(rounded_05 - value) < 0.15:
            return rounded_05
        return round(value, 1)
    elif abs_val < 100.0:
        # Medium: round to nearest 0.5 or integer
        rounded_05 = round(value * 2) / 2
        if abs(rounded_05 - value) < 0.3:
            return rounded_05
        return round(value)
    else:
        # Large: round to integer
        return round(value)


def parametrize_code(code: str) -> Tuple[str, List[str]]:
    """Extract hardcoded values into named parameters.
    
    Args:
        code: Raw build123d code
        
    Returns:
        (refactored_code, parameter_names)
    """
    # Find all numeric literals in the code
    # Pattern: function calls with numeric arguments
    
    param_names = []
    param_counter = {}
    
    def replace_with_param(match: re.Match) -> str:
        """Replace a numeric literal with a parameter reference."""
        nonlocal param_counter, param_names
        
        prefix = match.group(1)
        value_str = match.group(2)
        suffix = match.group(3)
        
        try:
            value = float(value_str)
        except ValueError:
            return match.group(0)
        
        # Determine parameter name based on context
        param_name = "param"
        
        if "radius=" in prefix or "r=" in prefix:
            param_name = "RADIUS"
        elif "height=" in prefix or "h=" in prefix:
            param_name = "HEIGHT"
        elif "width=" in prefix:
            param_name = "WIDTH"
        elif "diameter=" in prefix or "d=" in prefix:
            param_name = "DIAMETER"
        elif "length=" in prefix:
            param_name = "LENGTH"
        
        # Add counter for uniqueness
        if param_name in param_counter:
            param_counter[param_name] += 1
            full_name = f"{param_name}_{param_counter[param_name]}"
        else:
            param_counter[param_name] = 1
            full_name = param_name
        
        param_names.append(full_name)
        
        return f"{prefix}{full_name}{suffix}"
    
    # Pattern to find numeric literals in function calls
    # Matches: function(value, ...) or function(param=value, ...)
    pattern = r'(\w+\s*=\s*)(\d+\.?\d*)(\s*[\),])'
    
    refactored = re.sub(pattern, replace_with_param, code)
    
    # Now add parameter definitions at the top
    if param_names:
        param_lines = ["# Extracted Parameters"]
        seen = set()
        for name in param_names:
            if name not in seen:
                seen.add(name)
                # Find the value from the original code
                # This is a simplified approach
                param_lines.append(f"{name} = 10.0  # TODO: Extract actual value")
        
        refactored = "\n".join(param_lines) + "\n\n" + refactored
    
    return refactored, param_names


def beautify_code(code: str) -> str:
    """Beautify code dimensions to engineering standards.
    
    Args:
        code: Raw build123d code
        
    Returns:
        Beautified code
    """
    # Find all numeric literals and beautify them
    
    def beautify_match(match: re.Match) -> str:
        """Replace a numeric literal with beautified version."""
        prefix = match.group(1)
        value_str = match.group(2)
        suffix = match.group(3)
        
        try:
            value = float(value_str)
        except ValueError:
            return match.group(0)
        
        beautified = beautify_dimension(value)
        
        return f"{prefix}{beautified}{suffix}"
    
    # Pattern to find numeric literals
    pattern = r'(\D)(\d+\.?\d*)(\D)'
    
    # Apply beautification (multiple passes for nested values)
    for _ in range(3):
        code = re.sub(pattern, beautify_match, code)
    
    return code


class Optimizer:
    """Optimize generated code to engineering standards."""
    
    def __init__(
        self,
        extract_parameters: bool = True,
        beautify: bool = True,
        add_comments: bool = True
    ):
        """Initialize optimizer.
        
        Args:
            extract_parameters: Whether to extract hardcoded values
            beautify: Whether to beautify dimensions
            add_comments: Whether to add explanatory comments
        """
        self.extract_parameters = extract_parameters
        self.beautify = beautify
        self.add_comments = add_comments
    
    def optimize(self, code: str) -> str:
        """Optimize code to engineering standards.
        
        Args:
            code: Raw LLM-generated code
            
        Returns:
            Optimized code
        """
        logger.info("Starting code optimization")
        
        # Step 1: Parametrize
        if self.extract_parameters:
            code, params = parametrize_code(code)
            logger.info(f"Extracted {len(params)} parameters")
        
        # Step 2: Beautify
        if self.beautify:
            code = beautify_code(code)
            logger.info("Beautified dimensions")
        
        # Step 3: Add header
        if self.add_comments:
            header = """# Optimized build123d Code
# Auto-generated by GDI Optimizer
# 
# Engineering standards applied:
# - Dimensions rounded to appropriate precision
# - Hardcoded values extracted as parameters
# - Parametric design pattern enforced
# 
"""
            code = header + code
        
        logger.info("Optimization complete")
        return code
    
    def validate(self, code: str) -> Tuple[bool, List[str]]:
        """Validate optimized code.
        
        Args:
            code: Optimized code
            
        Returns:
            (is_valid, warnings)
        """
        warnings = []
        
        # Check for hardcoded values still present
        hardcoded_pattern = r'\b\d+\.?\d*\b'
        hardcoded_count = len(re.findall(hardcoded_pattern, code))
        
        if hardcoded_count > 5:  # Allow some small constants
            warnings.append(f"Still has {hardcoded_count} numeric literals - consider more parameter extraction")
        
        # Check for magic numbers
        magic_numbers = ["3.14", "6.28", "1.41", "1.73"]  # pi, 2pi, sqrt(2), sqrt(3)
        for magic in magic_numbers:
            if magic in code:
                warnings.append(f"Magic number {magic} found - should be named constant")
        
        # Check syntax
        try:
            ast.parse(code)
        except SyntaxError as e:
            return False, [f"Syntax error: {e}"]
        
        return len(warnings) == 0, warnings
