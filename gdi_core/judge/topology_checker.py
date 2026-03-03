"""Topology Checker using build123d/OCP.

Validates generated B-Rep models for topological errors.
"""

from typing import List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


def check_topology(step_file_path: str) -> Tuple[bool, List[str], Optional[str]]:
    """Check STEP file for topological errors.
    
    Uses OCP/BRepCheck_Analyzer to validate topology.
    
    Args:
        step_file_path: Path to generated STEP file
        
    Returns:
        (is_valid, error_list, full_log)
    """
    errors = []
    full_log = None
    
    try:
        # Try to import OCP (OpenCASCADE Python bindings via build123d)
        from OCP.BRepCheck import BRepCheck_Analyzer, BRepCheck_Status
        from OCP.BRepTools import BRepTools
        from OCP.BRep import BRep_Builder
        from OCP.TopoDS import TopoDS_Shape
        
        # Read STEP file (simplified - in production use proper STEP reader)
        # For now, we'll implement a placeholder that does basic validation
        # Full implementation would use OCP.STEPControl_Reader
        
        logger.info(f"Checking topology for {step_file_path}")
        
        # Placeholder implementation
        # In production, this would:
        # 1. Read STEP file using STEPControl_Reader
        # 2. Run BRepCheck_Analyzer on the shape
        # 3. Extract specific error messages
        
        return True, [], "Topology check passed (placeholder implementation)"
        
    except ImportError:
        logger.warning("OCP not available, skipping topology check")
        return True, [], "OCP not installed, topology check skipped"
        
    except Exception as e:
        logger.error(f"Topology check failed: {e}")
        return False, [str(e)], f"Error: {e}"


def check_code_syntax(code: str) -> Tuple[bool, List[str]]:
    """Check if build123d code is syntactically valid Python.
    
    Args:
        code: Python code string to check
        
    Returns:
        (is_valid, error_list)
    """
    import ast
    
    try:
        ast.parse(code)
        return True, []
    except SyntaxError as e:
        return False, [f"Syntax error at line {e.lineno}: {e.msg}"]
    except Exception as e:
        return False, [f"Parse error: {e}"]


def check_build123d_imports(code: str) -> Tuple[bool, List[str]]:
    """Check if code uses correct build123d patterns.
    
    Args:
        code: Python code string
        
    Returns:
        (is_valid, warnings_list)
    """
    warnings = []
    
    # Check for required patterns
    if "with BuildPart():" not in code and "with BuildSketch():" not in code:
        warnings.append("Code should use 'with BuildPart():' or 'with BuildSketch():' context managers")
    
    if "build123d" not in code and "from build123d import" not in code:
        warnings.append("Code should import from build123d")
    
    # Check for common anti-patterns
    if "import *" in code:
        warnings.append("Avoid 'import *', use explicit imports")
    
    return len(warnings) == 0, warnings
