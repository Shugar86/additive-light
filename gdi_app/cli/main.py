"""GDI CLI - Command-line interface for Generative Design Intelligence.

Usage:
    gdi process <stl_file> [options]
    gdi batch <directory> [options]
    gdi validate <yaml_file>
"""

import typer
from pathlib import Path
from typing import Optional, List
import json
import yaml
import logging

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

# Import GDI core
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from gdi_core.sensors import Sensor, align_mesh_to_origin
from gdi_core.approximator import Approximator
from gdi_core.models import SensorTelemetry
from gdi_core.utils import setup_logging, ManifestWriter

# Setup
app = typer.Typer(
    name="gdi",
    help="Generative Design Intelligence - 3D scan to CAD pipeline",
    rich_markup_mode="rich"
)
console = Console()


@app.command()
def process(
    stl_file: str = typer.Argument(..., help="Path to input STL file"),
    output_dir: str = typer.Option("output", "--output", "-o", help="Output directory"),
    axis: str = typer.Option("Z", "--axis", "-a", help="Build axis (X/Y/Z)"),
    slice_step: float = typer.Option(0.1, "--step", "-s", help="Slice step in mm"),
    confidence_threshold: float = typer.Option(0.7, "--confidence", "-c", help="Confidence threshold"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Process a single STL file through the GDI pipeline."""
    
    # Setup logging
    log_level = logging.DEBUG if verbose else logging.INFO
    logger = setup_logging(level=log_level)
    
    console.print(f"[bold blue]GDI Pipeline[/bold blue] - Processing {stl_file}")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        
        # Step 1: Load and align
        task = progress.add_task("Loading STL...", total=None)
        try:
            import trimesh
            mesh = trimesh.load(stl_file)
            mesh = align_mesh_to_origin(mesh)
            progress.update(task, description="STL loaded and aligned", completed=True)
        except Exception as e:
            console.print(f"[red]Error loading STL: {e}[/red]")
            raise typer.Exit(1)
        
        # Step 2: Sensor - Multi-axis slicing
        task = progress.add_task("Slicing mesh...", total=None)
        try:
            sensor = Sensor(slice_step=slice_step)
            slices = sensor.slice_mesh(mesh, axis=axis)
            progress.update(task, description=f"Generated {len(slices)} slices", completed=True)
        except Exception as e:
            console.print(f"[red]Error slicing mesh: {e}[/red]")
            raise typer.Exit(1)
        
        # Step 3: Approximator - Zone detection
        task = progress.add_task("Analyzing geometry...", total=None)
        try:
            approximator = Approximator(confidence_threshold=confidence_threshold)
            result = approximator.approximate(slices, stl_file, base_axis=axis)
            progress.update(task, description="Zones detected", completed=True)
        except Exception as e:
            console.print(f"[red]Error in approximation: {e}[/red]")
            raise typer.Exit(1)
        
        # Step 4: Output results
        task = progress.add_task("Saving results...", total=None)
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Write YAML telemetry
        yaml_file = output_path / f"{Path(stl_file).stem}_telemetry.yaml"
        with open(yaml_file, "w") as f:
            yaml.dump(result.telemetry.to_yaml_dict(), f, default_flow_style=False)
        
        # Write manifest
        manifest_writer = ManifestWriter(str(output_path / "manifests"))
        from gdi_core.models import RunManifest
        import uuid
        from datetime import datetime
        
        manifest = RunManifest(
            run_id=str(uuid.uuid4()),
            prompt_version="1.0",
            yaml_schema_version="1.0",
            source_stl=stl_file,
            output_yaml=str(yaml_file),
            approximation_result=result,
            status="success" if not result.fallback_required else "manual_review_required",
        )
        manifest_path = manifest_writer.write(manifest)
        
        progress.update(task, description="Results saved", completed=True)
    
    # Print summary
    console.print()
    console.print("[bold green]Processing Complete![/bold green]")
    console.print()
    
    # Results table
    table = Table(title="Detected Zones")
    table.add_column("Zone", style="cyan")
    table.add_column("Geometry", style="magenta")
    table.add_column("Cross-Section", style="green")
    table.add_column("Confidence", style="yellow")
    
    for zone in result.telemetry.topological_zones:
        conf_color = "green" if zone.confidence > 0.8 else "yellow" if zone.confidence > 0.6 else "red"
        table.add_row(
            str(zone.zone_id),
            zone.geometry.value,
            zone.cross_section.value,
            f"[{conf_color}]{zone.confidence:.2f}[/{conf_color}]"
        )
    
    console.print(table)
    console.print()
    
    # Global confidence
    conf_color = "green" if result.global_confidence > 0.8 else "yellow" if result.global_confidence > 0.6 else "red"
    console.print(f"Global Confidence: [{conf_color}]{result.global_confidence:.2f}[/{conf_color}]")
    
    if result.fallback_required:
        console.print(f"[yellow]⚠ Manual review required: {result.fallback_reason}[/yellow]")
    
    console.print()
    console.print(f"[dim]YAML telemetry: {yaml_file}[/dim]")
    console.print(f"[dim]Run manifest: {manifest_path}[/dim]")


@app.command()
def batch(
    directory: str = typer.Argument(..., help="Directory containing STL files"),
    output_dir: str = typer.Option("output", "--output", "-o", help="Output directory"),
    pattern: str = typer.Option("*.stl", "--pattern", "-p", help="File pattern"),
    confidence_threshold: float = typer.Option(0.7, "--confidence", "-c", help="Confidence threshold"),
):
    """Process all STL files in a directory."""
    
    console.print(f"[bold blue]GDI Batch Processing[/bold blue]")
    console.print(f"Directory: {directory}")
    console.print(f"Pattern: {pattern}")
    
    import glob
    import trimesh
    
    stl_files = glob.glob(str(Path(directory) / pattern))
    
    if not stl_files:
        console.print(f"[yellow]No STL files found in {directory}[/yellow]")
        raise typer.Exit(1)
    
    console.print(f"Found {len(stl_files)} STL files")
    console.print()
    
    # Results summary table
    results_table = Table(title="Batch Processing Results")
    results_table.add_column("File", style="cyan")
    results_table.add_column("Zones", style="magenta")
    results_table.add_column("Confidence", style="green")
    results_table.add_column("Status", style="yellow")
    
    success_count = 0
    fallback_count = 0
    
    for stl_file in stl_files:
        try:
            # Process file
            mesh = trimesh.load(stl_file)
            mesh = align_mesh_to_origin(mesh)
            
            sensor = Sensor(slice_step=0.1)
            slices = sensor.slice_mesh(mesh, axis="Z")
            
            approximator = Approximator(confidence_threshold=confidence_threshold)
            result = approximator.approximate(slices, stl_file, base_axis="Z")
            
            status = "✓" if not result.fallback_required else "⚠ review"
            status_color = "green" if not result.fallback_required else "yellow"
            
            results_table.add_row(
                Path(stl_file).name,
                str(len(result.telemetry.topological_zones)),
                f"{result.global_confidence:.2f}",
                f"[{status_color}]{status}[/{status_color}]"
            )
            
            if result.fallback_required:
                fallback_count += 1
            else:
                success_count += 1
                
        except Exception as e:
            results_table.add_row(
                Path(stl_file).name,
                "-",
                "-",
                f"[red]✗ error[/red]"
            )
    
    console.print(results_table)
    console.print()
    console.print(f"[green]Success: {success_count}[/green] | [yellow]Review needed: {fallback_count}[/yellow]")


@app.command()
def validate(
    yaml_file: str = typer.Argument(..., help="Path to YAML telemetry file"),
):
    """Validate a YAML telemetry file against schema."""
    
    console.print(f"[bold blue]Validating[/bold blue] {yaml_file}")
    
    try:
        with open(yaml_file) as f:
            data = yaml.safe_load(f)
        
        # Validate against model
        telemetry = SensorTelemetry(**data)
        
        console.print("[green]✓ YAML is valid[/green]")
        console.print()
        
        # Print summary
        table = Table(title="Telemetry Summary")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="magenta")
        
        table.add_row("Source", telemetry.source_file or "N/A")
        table.add_row("Total Height", f"{telemetry.global_state.total_height:.2f} mm")
        table.add_row("Base Axis", telemetry.global_state.base_axis)
        table.add_row("Zones", str(len(telemetry.topological_zones)))
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]✗ Validation failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def info():
    """Show GDI version and system info."""
    
    console.print("[bold blue]Generative Design Intelligence (GDI)[/bold blue]")
    console.print("Version: 1.0.0 (Desktop MVP)")
    console.print()
    
    table = Table(title="System Information")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    
    # Check dependencies
    try:
        import trimesh
        table.add_row("trimesh", f"✓ {trimesh.__version__}")
    except ImportError:
        table.add_row("trimesh", "✗ not installed")
    
    try:
        import shapely
        table.add_row("shapely", f"✓ {shapely.__version__}")
    except ImportError:
        table.add_row("shapely", "✗ not installed")
    
    try:
        import scipy
        table.add_row("scipy", f"✓ {scipy.__version__}")
    except ImportError:
        table.add_row("scipy", "✗ not installed")
    
    try:
        import pydantic
        table.add_row("pydantic", f"✓ {pydantic.__version__}")
    except ImportError:
        table.add_row("pydantic", "✗ not installed")
    
    try:
        import langgraph
        table.add_row("langgraph", "✓ installed")
    except ImportError:
        table.add_row("langgraph", "✗ not installed")
    
    console.print(table)


if __name__ == "__main__":
    app()
