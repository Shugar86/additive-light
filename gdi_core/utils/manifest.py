"""Run Manifest utilities.

Handles persistence and retrieval of run manifests.
"""

import json
import yaml
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from ..models.yaml_contract import RunManifest


class ManifestWriter:
    """Write run manifests to disk."""
    
    def __init__(self, output_dir: str = "runs"):
        """Initialize writer.
        
        Args:
            output_dir: Directory to write manifests
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def write(self, manifest: RunManifest, format: str = "json") -> str:
        """Write manifest to file.
        
        Args:
            manifest: Run manifest to write
            format: Output format ("json" or "yaml")
            
        Returns:
            Path to written file
        """
        # Create subdirectory based on date
        date_dir = self.output_dir / datetime.now().strftime("%Y-%m-%d")
        date_dir.mkdir(exist_ok=True)
        
        # Generate filename
        base_name = f"{manifest.run_id}"
        
        if format == "json":
            file_path = date_dir / f"{base_name}.json"
            with open(file_path, "w") as f:
                json.dump(manifest.model_dump(), f, indent=2, default=str)
        else:
            file_path = date_dir / f"{base_name}.yaml"
            with open(file_path, "w") as f:
                yaml.dump(manifest.model_dump(), f, default_flow_style=False)
        
        return str(file_path)
    
    def write_latest(self, manifest: RunManifest) -> str:
        """Write manifest and update 'latest' symlink/file.
        
        Args:
            manifest: Run manifest to write
            
        Returns:
            Path to written file
        """
        path = self.write(manifest, format="json")
        
        # Create/update latest.json
        latest_path = self.output_dir / "latest.json"
        with open(latest_path, "w") as f:
            json.dump(manifest.model_dump(), f, indent=2, default=str)
        
        return path


class ManifestReader:
    """Read run manifests from disk."""
    
    def __init__(self, output_dir: str = "runs"):
        """Initialize reader.
        
        Args:
            output_dir: Directory to read manifests from
        """
        self.output_dir = Path(output_dir)
    
    def read(self, run_id: str) -> Optional[RunManifest]:
        """Read manifest by run ID.
        
        Args:
            run_id: Run identifier
            
        Returns:
            RunManifest or None if not found
        """
        # Search for manifest
        for date_dir in self.output_dir.iterdir():
            if date_dir.is_dir():
                for file in date_dir.iterdir():
                    if file.stem == run_id:
                        with open(file) as f:
                            if file.suffix == ".json":
                                data = json.load(f)
                            else:
                                data = yaml.safe_load(f)
                        return RunManifest(**data)
        
        return None
    
    def read_latest(self) -> Optional[RunManifest]:
        """Read the latest manifest.
        
        Returns:
            Latest RunManifest or None
        """
        latest_path = self.output_dir / "latest.json"
        if not latest_path.exists():
            return None
        
        with open(latest_path) as f:
            data = json.load(f)
        
        return RunManifest(**data)
    
    def list_runs(
        self,
        status: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List runs with optional filtering.
        
        Args:
            status: Filter by status
            start_date: Filter by start date (YYYY-MM-DD)
            end_date: Filter by end date (YYYY-MM-DD)
            
        Returns:
            List of run summaries
        """
        runs = []
        
        for date_dir in self.output_dir.iterdir():
            if not date_dir.is_dir():
                continue
            
            # Check date range
            dir_date = date_dir.name
            if start_date and dir_date < start_date:
                continue
            if end_date and dir_date > end_date:
                continue
            
            for file in date_dir.iterdir():
                if file.suffix not in [".json", ".yaml"]:
                    continue
                
                try:
                    with open(file) as f:
                        if file.suffix == ".json":
                            data = json.load(f)
                        else:
                            data = yaml.safe_load(f)
                    
                    # Filter by status
                    if status and data.get("status") != status:
                        continue
                    
                    runs.append({
                        "run_id": data.get("run_id"),
                        "timestamp": data.get("timestamp"),
                        "status": data.get("status"),
                        "source_stl": data.get("source_stl"),
                        "final_iou": data.get("final_iou"),
                        "retry_count": data.get("retry_count"),
                    })
                except Exception:
                    continue
        
        # Sort by timestamp (newest first)
        runs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        return runs
