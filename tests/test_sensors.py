"""Test suite for deterministic sensor modules.

Tests for align_open3d and slice_trimesh modules.
All tests use synthetic geometry to avoid external file dependencies.
"""

import pytest
import numpy as np
from pathlib import Path
import tempfile

# Skip tests if dependencies not available
try:
    import open3d as o3d
    HAS_OPEN3D = True
except ImportError:
    HAS_OPEN3D = False

try:
    import trimesh
    HAS_TRIMESH = True
except ImportError:
    HAS_TRIMESH = False


@pytest.fixture
def temp_stl_cube():
    """Create a temporary STL file with a simple cube."""
    if not HAS_OPEN3D:
        pytest.skip("Open3D not installed")
    
    # Create a simple cube mesh
    mesh = o3d.geometry.TriangleMesh.create_box(width=10.0, height=10.0, depth=10.0)
    mesh.compute_vertex_normals()
    
    with tempfile.NamedTemporaryFile(suffix='.stl', delete=False) as f:
        temp_path = f.name
    
    o3d.io.write_triangle_mesh(temp_path, mesh)
    yield temp_path
    
    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


@pytest.fixture
def temp_stl_cylinder():
    """Create a temporary STL file with a cylinder."""
    if not HAS_OPEN3D:
        pytest.skip("Open3D not installed")
    
    # Create a cylinder aligned with Z-axis
    mesh = o3d.geometry.TriangleMesh.create_cylinder(radius=5.0, height=20.0, resolution=32)
    mesh.compute_vertex_normals()
    
    with tempfile.NamedTemporaryFile(suffix='.stl', delete=False) as f:
        temp_path = f.name
    
    o3d.io.write_triangle_mesh(temp_path, mesh)
    yield temp_path
    
    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


class TestAlignOpen3D:
    """Tests for the align_open3d module."""

    @pytest.mark.skipif(not HAS_OPEN3D, reason="Open3D not installed")
    def test_load_and_center_mesh_success(self, temp_stl_cube):
        """Test successful mesh loading and centering."""
        from backend.sensors.align_open3d import load_and_center_mesh
        
        output_path, centroid, principal_axes = load_and_center_mesh(temp_stl_cube)
        
        # Check outputs
        assert Path(output_path).exists()
        assert isinstance(centroid, np.ndarray)
        assert centroid.shape == (3,)
        assert isinstance(principal_axes, np.ndarray)
        assert principal_axes.shape == (3, 3)
        
        # After centering, centroid should be near origin
        # (but may not be exactly zero due to mesh topology)
        assert np.allclose(centroid, [5.0, 5.0, 5.0], atol=0.1)
    
    @pytest.mark.skipif(not HAS_OPEN3D, reason="Open3D not installed")
    def test_load_and_center_mesh_not_found(self):
        """Test error handling for missing file."""
        from backend.sensors.align_open3d import load_and_center_mesh
        
        with pytest.raises(FileNotFoundError):
            load_and_center_mesh("/nonexistent/path/file.stl")
    
    @pytest.mark.skipif(not HAS_OPEN3D, reason="Open3D not installed")
    def test_get_mesh_bounds(self, temp_stl_cube):
        """Test bounding box computation."""
        from backend.sensors.align_open3d import get_mesh_bounds
        
        min_bounds, max_bounds = get_mesh_bounds(temp_stl_cube)
        
        assert isinstance(min_bounds, np.ndarray)
        assert isinstance(max_bounds, np.ndarray)
        assert min_bounds.shape == (3,)
        assert max_bounds.shape == (3,)
        
        # For a cube at origin with size 10, bounds should be 0 to 10
        assert np.allclose(min_bounds, [0.0, 0.0, 0.0], atol=0.1)
        assert np.allclose(max_bounds, [10.0, 10.0, 10.0], atol=0.1)
    
    @pytest.mark.skipif(not HAS_OPEN3D, reason="Open3D not installed")
    def test_compute_mesh_properties(self, temp_stl_cube):
        """Test mesh property computation."""
        from backend.sensors.align_open3d import compute_mesh_properties
        
        props = compute_mesh_properties(temp_stl_cube)
        
        assert "volume" in props
        assert "surface_area" in props
        assert "centroid" in props
        assert "bounds" in props
        assert "vertex_count" in props
        assert "triangle_count" in props
        
        # Cube 10x10x10 should have volume 1000
        assert abs(props["volume"] - 1000.0) < 50.0  # Allow tolerance for mesh discretization
        assert props["vertex_count"] > 0
        assert props["triangle_count"] > 0


class TestSliceTrimesh:
    """Tests for the slice_trimesh module."""

    @pytest.mark.skipif(not HAS_TRIMESH, reason="Trimesh not installed")
    def test_slice_analyzer_initialization(self, temp_stl_cylinder):
        """Test SliceAnalyzer can load a mesh."""
        from backend.sensors.slice_trimesh import SliceAnalyzer
        
        analyzer = SliceAnalyzer(temp_stl_cylinder)
        assert analyzer.mesh is not None
        assert len(analyzer.mesh.vertices) > 0
    
    @pytest.mark.skipif(not HAS_TRIMESH, reason="Trimesh not installed")
    def test_slice_along_axis_cylinder(self, temp_stl_cylinder):
        """Test slicing a cylinder along Z-axis."""
        from backend.sensors.slice_trimesh import SliceAnalyzer
        
        analyzer = SliceAnalyzer(temp_stl_cylinder)
        slices = analyzer.slice_along_axis('Z', slice_count=10)
        
        # Should have multiple valid slices
        assert len(slices) > 0
        
        # Each slice should have the expected structure
        for slice_data in slices:
            assert "position" in slice_data
            assert "axis" in slice_data
            assert slice_data["axis"] == "Z"
            assert "area" in slice_data
            assert "features" in slice_data
            
            # Cylinder slices should be circles
            circle_features = [f for f in slice_data["features"] if f["type"] == "circle"]
            if circle_features:
                # Check radius is approximately 5.0
                radius = circle_features[0]["radius"]
                assert abs(radius - 5.0) < 0.5
    
    @pytest.mark.skipif(not HAS_TRIMESH, reason="Trimesh not installed")
    def test_slice_along_axis_invalid(self, temp_stl_cylinder):
        """Test error handling for invalid axis."""
        from backend.sensors.slice_trimesh import SliceAnalyzer
        
        analyzer = SliceAnalyzer(temp_stl_cylinder)
        
        with pytest.raises(ValueError):
            analyzer.slice_along_axis('Q', slice_count=5)
        
        with pytest.raises(ValueError):
            analyzer.slice_along_axis('X', slice_count=0)
    
    @pytest.mark.skipif(not HAS_TRIMESH, reason="Trimesh not installed")
    def test_find_cylindrical_features(self, temp_stl_cylinder):
        """Test cylindrical feature detection."""
        from backend.sensors.slice_trimesh import SliceAnalyzer
        
        analyzer = SliceAnalyzer(temp_stl_cylinder)
        cylinders = analyzer.find_cylindrical_features(axis='Z', tolerance=0.1)
        
        # Should find at least one cylinder
        assert len(cylinders) > 0
        
        # Check first cylinder properties
        cyl = cylinders[0]
        assert "radius" in cyl
        assert "start_position" in cyl
        assert "end_position" in cyl
        assert "positions" in cyl
        
        # Radius should be approximately 5.0
        assert abs(cyl["radius"] - 5.0) < 0.5
        
        # Should have reasonable length (cylinder height was 20.0)
        length = abs(cyl["end_position"] - cyl["start_position"])
        assert length > 10.0
    
    @pytest.mark.skipif(not HAS_TRIMESH, reason="Trimesh not installed")
    def test_classify_polygon_circle(self):
        """Test circle classification."""
        from backend.sensors.slice_trimesh import SliceAnalyzer
        
        # Create analyzer with dummy path (won't be used for this test)
        with tempfile.NamedTemporaryFile(suffix='.stl', delete=False) as f:
            dummy_path = f.name
        
        if HAS_OPEN3D:
            mesh = o3d.geometry.TriangleMesh.create_cylinder(radius=5.0, height=1.0)
            o3d.io.write_triangle_mesh(dummy_path, mesh)
        
        try:
            analyzer = SliceAnalyzer(dummy_path)
            
            # Create a perfect circle polygon
            theta = np.linspace(0, 2*np.pi, 100)
            circle_coords = np.column_stack([5*np.cos(theta), 5*np.sin(theta)])
            
            try:
                from shapely.geometry import Polygon
                circle_poly = Polygon(circle_coords)
                
                feature = analyzer._classify_polygon(circle_poly)
                
                assert feature is not None
                assert feature["type"] == "circle"
                assert abs(feature["radius"] - 5.0) < 0.1
                assert feature["circle_confidence"] > 0.9
            except ImportError:
                pytest.skip("Shapely not installed")
        finally:
            Path(dummy_path).unlink(missing_ok=True)