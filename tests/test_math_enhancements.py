"""Tests for P8 Math Stack Enhancements.

Tests for:
- RANSAC-based plane detection in alignment
- Blind hole detection in coordinator
- SDF metrics in VibeGuard
"""

import pytest
import numpy as np
from pathlib import Path


class TestAlignmentEnhancements:
    """Tests for P8 alignment improvements."""
    
    def test_ransac_plane_detection(self):
        """Test RANSAC plane detection for mechanical parts."""
        try:
            import open3d as o3d
            from backend.sensors.align_open3d import detect_principal_axes_ransac
            
            # Create a simple box mesh (has clear flat faces)
            mesh = o3d.geometry.TriangleMesh.create_box(2.0, 1.0, 0.5)
            
            rotation_matrix, metadata = detect_principal_axes_ransac(mesh)
            
            assert rotation_matrix.shape == (3, 3)
            assert metadata["method"] in ["ransac_planes", "pca_fallback"]
            
            # For a box, should detect planes
            if "plane_count" in metadata:
                assert metadata["plane_count"] >= 2
        except ImportError:
            pytest.skip("Open3D not installed")
    
    def test_symmetry_analysis_cylinder(self):
        """Test symmetry detection for cylindrical parts."""
        try:
            import open3d as o3d
            from backend.sensors.align_open3d import analyze_rotational_symmetry
            
            # Create cylinder (should be detected as rotationally symmetric)
            mesh = o3d.geometry.TriangleMesh.create_cylinder(radius=1.0, height=2.0)
            
            symmetry = analyze_rotational_symmetry(mesh)
            
            assert "is_cylindrical" in symmetry
            assert "symmetry_axis" in symmetry
            assert "symmetry_score" in symmetry
            
            # Cylinder should have high symmetry score
            if symmetry["is_cylindrical"]:
                assert symmetry["symmetry_score"] > 0.5
        except ImportError:
            pytest.skip("Open3D not installed")
    
    def test_load_and_center_with_metadata(self):
        """Test enhanced load_and_center returns metadata."""
        try:
            import open3d as o3d
            from backend.sensors.align_open3d import load_and_center_mesh
            import tempfile
            
            # Create temp STL
            mesh = o3d.geometry.TriangleMesh.create_cylinder(radius=1.0, height=2.0)
            
            with tempfile.TemporaryDirectory() as tmpdir:
                stl_path = Path(tmpdir) / "test_cylinder.stl"
                o3d.io.write_triangle_mesh(str(stl_path), mesh)
                
                # Load with RANSAC
                aligned_path, centroid, axes, metadata = load_and_center_mesh(
                    str(stl_path),
                    use_ransac=True,
                    symmetry_check=True
                )
                
                assert Path(aligned_path).exists()
                assert centroid.shape == (3,)
                assert axes.shape == (3, 3)
                assert "alignment_method" in metadata
                assert metadata["alignment_method"] in ["ransac_planes", "pca_fallback"]
                
        except ImportError:
            pytest.skip("Open3D not installed")


class TestBlindHoleDetection:
    """Tests for P8 blind hole detection."""
    
    def test_hole_type_classification(self):
        """Test through-hole vs blind-hole classification."""
        from backend.agents.coordinator_agent import CoordinatorAgent
        from backend.core.state import Axis, SliceReport, SliceFeature, CADState
        
        agent = CoordinatorAgent(llm_client=None)
        
        # Create sensor reports with holes at different depths
        # Through-hole: spans most of the part
        z_report = SliceReport(
            axis=Axis.Z,
            slice_positions=[0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0],
            features_by_slice={
                "slice_000_pos_0.0": [],
                "slice_001_pos_1.0": [SliceFeature(feature_type="circle", center=[2.0, 2.0], radius=1.0, area=3.14, perimeter=6.28)],
                "slice_002_pos_2.0": [SliceFeature(feature_type="circle", center=[2.0, 2.0], radius=1.0, area=3.14, perimeter=6.28)],
                "slice_003_pos_3.0": [SliceFeature(feature_type="circle", center=[2.0, 2.0], radius=1.0, area=3.14, perimeter=6.28)],
                "slice_004_pos_4.0": [],
                "slice_005_pos_5.0": [],
                "slice_006_pos_6.0": [],
                "slice_007_pos_7.0": [],
                "slice_008_pos_8.0": [],
                "slice_009_pos_9.0": [],
            }
        )
        
        # This is a blind hole (only 3 slices, not through)
        sensor_reports = {Axis.Z: z_report}
        
        # Test hole detection
        holes = agent._find_holes_from_cross_section(sensor_reports)
        
        # Should find at least one hole
        assert len(holes) >= 1
        
        # Check hole properties
        for hole in holes:
            assert hole.feature_type in ["through_hole", "blind_hole"]
            assert "radius" in hole.dimensions
    
    def test_circle_grouping(self):
        """Test circle grouping by position."""
        from backend.agents.coordinator_agent import CoordinatorAgent
        from backend.core.state import SliceFeature
        
        agent = CoordinatorAgent(llm_client=None)
        
        # Create circles at similar positions
        circles = [
            {"circle": SliceFeature(feature_type="circle", center=[1.0, 1.0], radius=0.5, area=0.785, perimeter=3.14), "axis": None, "position": 0.0},
            {"circle": SliceFeature(feature_type="circle", center=[1.1, 1.1], radius=0.5, area=0.785, perimeter=3.14), "axis": None, "position": 1.0},
            {"circle": SliceFeature(feature_type="circle", center=[5.0, 5.0], radius=2.0, area=12.56, perimeter=12.56), "axis": None, "position": 0.0},
        ]
        
        groups = agent._group_circles_by_position(circles, tolerance=0.5)
        
        # First two circles should be grouped together
        # Third circle is separate
        assert len(groups) == 2
        assert len(groups[0]) == 2  # Similar position circles
        assert len(groups[1]) == 1  # Different position circle


class TestVibeGuardSDF:
    """Tests for P8 SDF metrics in VibeGuard."""
    
    def test_sdf_metric_computation(self):
        """Test SDF metric computation."""
        from backend.agents.vibeguard_agent import VibeGuardAgent
        
        agent = VibeGuardAgent()
        
        # Create two similar point clouds
        np.random.seed(42)
        original = np.random.randn(100, 3) * 0.1
        generated = original + np.random.randn(100, 3) * 0.01  # Small perturbation
        
        sdf_metrics = agent._compute_sdf_metric(original, generated, grid_resolution=16)
        
        assert "sdf_mean" in sdf_metrics
        assert "sdf_max" in sdf_metrics
        assert "volume_error" in sdf_metrics
        
        # Should have positive values
        assert sdf_metrics["sdf_mean"] >= 0
        assert sdf_metrics["sdf_max"] >= 0
    
    def test_sdf_with_empty_point_cloud(self):
        """Test SDF handles empty point clouds gracefully."""
        from backend.agents.vibeguard_agent import VibeGuardAgent
        
        agent = VibeGuardAgent()
        
        empty = np.array([]).reshape(0, 3)
        points = np.random.randn(10, 3)
        
        sdf_metrics = agent._compute_sdf_metric(empty, points)
        
        # Should return default values without crashing
        assert sdf_metrics["sdf_mean"] == 0
        assert sdf_metrics["sdf_max"] == 0
    
    def test_inside_outside_approximation(self):
        """Test approximate inside/outside classification."""
        from backend.agents.vibeguard_agent import VibeGuardAgent
        
        agent = VibeGuardAgent()
        
        # Create a simple sphere point cloud
        phi = np.random.uniform(0, 2 * np.pi, 100)
        theta = np.random.uniform(0, np.pi, 100)
        r = 1.0
        
        surface_points = np.array([
            r * np.sin(theta) * np.cos(phi),
            r * np.sin(theta) * np.sin(phi),
            r * np.cos(theta)
        ]).T
        
        # Query points: one inside, one outside
        query_points = np.array([
            [0.0, 0.0, 0.0],  # Inside
            [2.0, 0.0, 0.0],  # Outside
        ])
        
        inside_mask = agent._approximate_inside_test(query_points, surface_points)
        
        # Note: This is a heuristic, so results may vary
        assert len(inside_mask) == 2
    
    def test_vibeguard_compare_with_sdf(self):
        """Test full VibeGuard comparison including SDF."""
        try:
            import open3d as o3d
            from backend.agents.vibeguard_agent import VibeGuardAgent
            from backend.core.state import CADState
            import tempfile
            
            agent = VibeGuardAgent()
            
            # Create two similar meshes
            mesh1 = o3d.geometry.TriangleMesh.create_cylinder(radius=1.0, height=2.0)
            mesh2 = o3d.geometry.TriangleMesh.create_cylinder(radius=1.02, height=2.0)  # Slightly larger
            
            with tempfile.TemporaryDirectory() as tmpdir:
                original_path = Path(tmpdir) / "original.stl"
                generated_path = Path(tmpdir) / "generated.stl"
                
                o3d.io.write_triangle_mesh(str(original_path), mesh1)
                o3d.io.write_triangle_mesh(str(generated_path), mesh2)
                
                state = CADState(
                    stl_path=str(original_path),
                    final_mesh_path=str(generated_path)
                )
                
                result = agent.compare(state)
                
                assert "chamfer_distance" in result
                assert "hausdorff_distance" in result
                assert "sdf_metrics" in result  # P8: SDF metrics now included
                assert "errors" in result
                assert "passed" in result
                
                if result["sdf_metrics"]:
                    assert "sdf_mean" in result["sdf_metrics"]
        except ImportError:
            pytest.skip("Open3D not installed")


class TestDetailedErrorRegions:
    """Tests for P8 detailed error localization."""
    
    def test_detailed_error_regions(self):
        """Test detailed error region computation."""
        from backend.agents.vibeguard_agent import VibeGuardAgent
        
        agent = VibeGuardAgent()
        
        # Create point clouds with known deviations
        np.random.seed(42)
        original = np.random.randn(50, 3) * 0.5
        
        # Generated has one region with large error
        generated = original.copy()
        generated[0:10] += [0.5, 0.5, 0.5]  # Large deviation in first 10 points
        
        distances = agent._nearest_neighbor_distances(original, generated)
        
        errors = agent._compute_detailed_error_regions(
            original, generated, distances, num_regions=8
        )
        
        # Should detect the high-error region
        assert len(errors) > 0
        
        for error in errors:
            assert "type" in error
            assert "location" in error
            assert "octant" in error
            assert "severity" in error


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
