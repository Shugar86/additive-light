#!/usr/bin/env python3
"""Sandbox execution script for build123d code.

This script runs in an isolated Docker container and executes
LLM-generated code safely. It:
1. Reads code from stdin or file
2. Executes in controlled environment
3. Outputs STEP file or error
4. Returns JSON result
"""

import sys
import json
import traceback
from pathlib import Path
from io import StringIO
import contextlib


def execute_code(code: str, output_step: str) -> dict:
    """Execute build123d code safely.
    
    Args:
        code: Python code to execute
        output_step: Path for output STEP file
        
    Returns:
        Result dict with success status and output
    """
    # Capture stdout/stderr
    stdout_capture = StringIO()
    stderr_capture = StringIO()
    
    result = {
        "success": False,
        "output_step": None,
        "stdout": "",
        "stderr": "",
        "error": None
    }
    
    try:
        # Create restricted globals
        safe_globals = {
            "__builtins__": {
                "len": len,
                "range": range,
                "enumerate": enumerate,
                "zip": zip,
                "map": map,
                "filter": filter,
                "abs": abs,
                "round": round,
                "min": min,
                "max": max,
                "sum": sum,
                "float": float,
                "int": int,
                "str": str,
                "list": list,
                "dict": dict,
                "tuple": tuple,
                "set": set,
                "print": lambda *args: stdout_capture.write(" ".join(map(str, args)) + "\n"),
                "Exception": Exception,
            }
        }
        
        # Add build123d imports
        try:
            from build123d import *
            from ocp_vscode import *
            
            # Add common build123d classes to globals
            safe_globals.update({
                "BuildPart": BuildPart,
                "BuildSketch": BuildSketch,
                "BuildLine": BuildLine,
                "Cylinder": Cylinder,
                "Sphere": Sphere,
                "Box": Box,
                "Cone": Cone,
                "Torus": Torus,
                "Circle": Circle,
                "Rectangle": Rectangle,
                "Polygon": Polygon,
                "Polyline": Polyline,
                "Line": Line,
                "Arc": Arc,
                "Spline": Spline,
                "Plane": Plane,
                "Locations": Locations,
                "GridLocations": GridLocations,
                "PolarLocations": PolarLocations,
                "add": add,
                "subtract": subtract,
                "intersect": intersect,
                "extrude": extrude,
                "revolve": revolve,
                "sweep": sweep,
                "loft": loft,
                "fuse": fuse,
                "cut": cut,
                "fillet": fillet,
                "chamfer": chamfer,
                "hollow": hollow,
                "shell": shell,
                "show": show,
                "export_step": export_step,
            })
        except ImportError as e:
            result["error"] = f"Failed to import build123d: {e}"
            return result
        
        # Execute code with captured output
        with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
            exec(code, safe_globals)
        
        # Check if a part was created
        part = None
        for name, obj in safe_globals.items():
            if hasattr(obj, 'wrapped') or 'Part' in type(obj).__name__:
                part = obj
                break
        
        if part is None:
            result["error"] = "No valid Part object created"
            return result
        
        # Export to STEP
        if output_step:
            export_step(part, output_step)
            result["output_step"] = output_step
        
        result["success"] = True
        result["stdout"] = stdout_capture.getvalue()
        result["stderr"] = stderr_capture.getvalue()
        
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {str(e)}"
        result["traceback"] = traceback.format_exc()
        result["stderr"] = stderr_capture.getvalue()
    
    return result


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Execute build123d code in sandbox")
    parser.add_argument("--code-file", "-c", help="Path to code file")
    parser.add_argument("--code-stdin", action="store_true", help="Read code from stdin")
    parser.add_argument("--output", "-o", required=True, help="Output STEP file path")
    parser.add_argument("--json", "-j", action="store_true", help="Output JSON result")
    
    args = parser.parse_args()
    
    # Read code
    if args.code_stdin:
        code = sys.stdin.read()
    elif args.code_file:
        with open(args.code_file) as f:
            code = f.read()
    else:
        print("Error: Must specify --code-file or --code-stdin", file=sys.stderr)
        sys.exit(1)
    
    # Execute
    result = execute_code(code, args.output)
    
    # Output
    if args.json:
        print(json.dumps(result))
    else:
        if result["success"]:
            print(f"Success: {result['output_step']}")
        else:
            print(f"Error: {result['error']}", file=sys.stderr)
            if result.get("traceback"):
                print(result["traceback"], file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
