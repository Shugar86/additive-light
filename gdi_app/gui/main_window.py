"""GDI Desktop GUI - Professional Engineering Interface.

Professional "calm" vibe for engineering workflow.
STL -> Analysis -> CAD Intelligence
"""

import sys
import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QProgressBar, QTextEdit,
    QMessageBox, QComboBox, QGroupBox, QSpinBox, QDoubleSpinBox,
    QFrame, QSplitter, QTreeWidget, QTreeWidgetItem, QHeaderView,
    QStatusBar, QToolBar, QMenuBar, QMenu
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QIcon, QAction

# Import GDI core
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from gdi_core.sensors import Sensor, align_mesh_to_origin
from gdi_core.approximator import Approximator
from gdi_core.utils import setup_logging, ManifestWriter
from gdi_core.models import RunManifest
import trimesh
import uuid
from datetime import datetime

logger = setup_logging(level=logging.INFO)

# Professional color scheme
COLORS = {
    "bg_dark": "#1e1e1e",
    "bg_card": "#252526",
    "bg_input": "#3c3c3c",
    "text_primary": "#cccccc",
    "text_secondary": "#858585",
    "accent": "#007acc",  # Engineering blue
    "accent_hover": "#0098ff",
    "success": "#4ec9b0",
    "warning": "#cca700",
    "error": "#f48771",
    "border": "#3c3c3c"
}


class WorkerThread(QThread):
    """Background worker for pipeline execution."""
    
    progress = pyqtSignal(str, int)  # message, percent
    zone_detected = pyqtSignal(int, str, float)  # zone_id, geometry, confidence
    finished_signal = pyqtSignal(object, object)  # result, error
    
    def __init__(self, stl_file: str, axis: str, slice_step: float, confidence: float):
        super().__init__()
        self.stl_file = stl_file
        self.axis = axis
        self.slice_step = slice_step
        self.confidence = confidence
        self.result = None
        self.error = None
    
    def run(self):
        """Execute pipeline in background thread."""
        try:
            self.progress.emit("Loading STL file...", 10)
            mesh = trimesh.load(self.stl_file)
            mesh = align_mesh_to_origin(mesh)
            
            self.progress.emit("Slicing mesh...", 25)
            sensor = Sensor(slice_step=self.slice_step)
            slices = sensor.slice_mesh(mesh, axis=self.axis)
            
            self.progress.emit(f"Analyzing {len(slices)} slices...", 50)
            approximator = Approximator(confidence_threshold=self.confidence)
            result = approximator.approximate(slices, self.stl_file, base_axis=self.axis)
            
            # Emit zone detections
            for zone in result.telemetry.topological_zones:
                self.zone_detected.emit(
                    zone.zone_id,
                    f"{zone.geometry.value} ({zone.cross_section.value})",
                    zone.confidence
                )
            
            self.progress.emit("Saving results...", 85)
            
            # Save outputs
            output_dir = Path("output")
            output_dir.mkdir(exist_ok=True)
            
            import yaml
            yaml_file = output_dir / f"{Path(self.stl_file).stem}_telemetry.yaml"
            with open(yaml_file, "w") as f:
                yaml.dump(result.telemetry.to_yaml_dict(), f, default_flow_style=False)
            
            # Create manifest
            manifest_writer = ManifestWriter(str(output_dir / "manifests"))
            manifest = RunManifest(
                run_id=str(uuid.uuid4()),
                prompt_version="1.0",
                yaml_schema_version="1.0",
                source_stl=self.stl_file,
                output_yaml=str(yaml_file),
                approximation_result=result,
                status="success" if not result.fallback_required else "manual_review_required",
            )
            manifest_path = manifest_writer.write(manifest)
            
            self.result = (result, str(yaml_file), manifest_path)
            self.progress.emit("Complete", 100)
            
        except Exception as e:
            logger.exception("Pipeline failed")
            self.error = str(e)
        
        self.finished_signal.emit(self.result, self.error)


class ZoneTreeItem(QTreeWidgetItem):
    """Tree item for detected zone."""
    
    def __init__(self, zone_id: int, geometry: str, confidence: float, parent=None):
        super().__init__(parent)
        self.setText(0, f"Zone {zone_id}")
        self.setText(1, geometry)
        self.setText(2, f"{confidence:.1%}")
        
        # Color code confidence
        if confidence >= 0.9:
            self.setForeground(2, Qt.GlobalColor.green)
        elif confidence >= 0.7:
            self.setForeground(2, Qt.GlobalColor.yellow)
        else:
            self.setForeground(2, Qt.GlobalColor.red)


class GDI_GUI(QMainWindow):
    """Professional GDI Desktop GUI."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GDI - Generative Design Intelligence")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)
        
        self.current_file: Optional[str] = None
        self.worker: Optional[WorkerThread] = None
        
        self._setup_styles()
        self._setup_ui()
        self._setup_menu()
    
    def _setup_styles(self):
        """Apply professional dark theme."""
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {COLORS["bg_dark"]};
            }}
            QWidget {{
                background-color: {COLORS["bg_dark"]};
                color: {COLORS["text_primary"]};
                font-family: 'Segoe UI', Arial;
                font-size: 12px;
            }}
            QGroupBox {{
                background-color: {COLORS["bg_card"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 10px;
                font-weight: bold;
                font-size: 13px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: {COLORS["text_primary"]};
            }}
            QPushButton {{
                background-color: {COLORS["accent"]};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {COLORS["accent_hover"]};
            }}
            QPushButton:disabled {{
                background-color: {COLORS["bg_input"]};
                color: {COLORS["text_secondary"]};
            }}
            QPushButton#secondary {{
                background-color: {COLORS["bg_input"]};
                color: {COLORS["text_primary"]};
                border: 1px solid {COLORS["border"]};
            }}
            QPushButton#secondary:hover {{
                background-color: {COLORS["border"]};
            }}
            QTextEdit {{
                background-color: {COLORS["bg_card"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 4px;
                padding: 10px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
            }}
            QComboBox, QSpinBox, QDoubleSpinBox {{
                background-color: {COLORS["bg_input"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 4px;
                padding: 5px;
                min-height: 28px;
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: {COLORS["bg_input"]};
                color: {COLORS["text_primary"]};
                selection-background-color: {COLORS["accent"]};
            }}
            QProgressBar {{
                border: 1px solid {COLORS["border"]};
                border-radius: 4px;
                text-align: center;
                height: 24px;
            }}
            QProgressBar::chunk {{
                background-color: {COLORS["accent"]};
                border-radius: 3px;
            }}
            QTreeWidget {{
                background-color: {COLORS["bg_card"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 4px;
                alternate-background-color: {COLORS["bg_dark"]};
            }}
            QTreeWidget::header {{
                background-color: {COLORS["bg_input"]};
                padding: 5px;
                font-weight: bold;
            }}
            QTreeWidget::item {{
                padding: 5px;
            }}
            QTreeWidget::item:selected {{
                background-color: {COLORS["accent"]};
            }}
            QLabel {{
                color: {COLORS["text_primary"]};
            }}
            QLabel#title {{
                font-size: 24px;
                font-weight: bold;
                color: white;
            }}
            QLabel#subtitle {{
                font-size: 14px;
                color: {COLORS["text_secondary"]};
            }}
            QLabel#status {{
                font-size: 13px;
                padding: 5px;
            }}
            QFrame#card {{
                background-color: {COLORS["bg_card"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 6px;
            }}
            QFrame#dropzone {{
                background-color: {COLORS["bg_card"]};
                border: 2px dashed {COLORS["border"]};
                border-radius: 8px;
            }}
            QFrame#dropzone:hover {{
                border-color: {COLORS["accent"]};
                background-color: {COLORS["bg_input"]};
            }}
            QStatusBar {{
                background-color: {COLORS["bg_card"]};
                border-top: 1px solid {COLORS["border"]};
            }}
            QMenuBar {{
                background-color: {COLORS["bg_card"]};
                border-bottom: 1px solid {COLORS["border"]};
            }}
            QMenuBar::item:selected {{
                background-color: {COLORS["accent"]};
            }}
            QMenu {{
                background-color: {COLORS["bg_card"]};
                border: 1px solid {COLORS["border"]};
            }}
            QMenu::item:selected {{
                background-color: {COLORS["accent"]};
            }}
        """)
    
    def _setup_menu(self):
        """Setup menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        open_action = QAction("Open STL...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._browse_file)
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        about_action = QAction("About GDI", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
    
    def _setup_ui(self):
        """Setup the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # Left panel - Input & Settings
        left_panel = self._create_left_panel()
        main_layout.addWidget(left_panel, 1)
        
        # Right panel - Results
        right_panel = self._create_right_panel()
        main_layout.addWidget(right_panel, 2)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready - Load an STL file to begin")
    
    def _create_left_panel(self) -> QWidget:
        """Create left panel with file selection and settings."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(15)
        
        # Header
        header = QLabel("GDI Desktop")
        header.setObjectName("title")
        layout.addWidget(header)
        
        subtitle = QLabel("Generative Design Intelligence")
        subtitle.setObjectName("subtitle")
        layout.addWidget(subtitle)
        
        layout.addSpacing(20)
        
        # File Selection Group
        file_group = QGroupBox("1. Select Model")
        file_layout = QVBoxLayout(file_group)
        
        # Drop zone / File display
        self.file_frame = QFrame()
        self.file_frame.setObjectName("dropzone")
        self.file_frame.setMinimumHeight(120)
        file_inner = QVBoxLayout(self.file_frame)
        
        self.file_label = QLabel("Drop STL file here\nor click to browse")
        self.file_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.file_label.setStyleSheet("font-size: 14px; color: #858585;")
        file_inner.addWidget(self.file_label)
        
        self.file_frame.mousePressEvent = lambda e: self._browse_file()
        file_layout.addWidget(self.file_frame)
        
        # Browse button
        browse_btn = QPushButton("Browse...")
        browse_btn.setObjectName("secondary")
        browse_btn.clicked.connect(self._browse_file)
        file_layout.addWidget(browse_btn)
        
        layout.addWidget(file_group)
        
        # Settings Group
        settings_group = QGroupBox("2. Processing Settings")
        settings_layout = QVBoxLayout(settings_group)
        
        # Axis selection
        axis_layout = QHBoxLayout()
        axis_layout.addWidget(QLabel("Build Axis:"))
        self.axis_combo = QComboBox()
        self.axis_combo.addItems(["Z (Vertical)", "Y", "X"])
        self.axis_combo.setCurrentText("Z (Vertical)")
        axis_layout.addWidget(self.axis_combo)
        axis_layout.addStretch()
        settings_layout.addLayout(axis_layout)
        
        # Slice step
        step_layout = QHBoxLayout()
        step_layout.addWidget(QLabel("Slice Step:"))
        self.step_spin = QDoubleSpinBox()
        self.step_spin.setRange(0.01, 1.0)
        self.step_spin.setValue(0.1)
        self.step_spin.setDecimals(2)
        self.step_spin.setSuffix(" mm")
        step_layout.addWidget(self.step_spin)
        step_layout.addStretch()
        settings_layout.addLayout(step_layout)
        
        # Confidence threshold
        conf_layout = QHBoxLayout()
        conf_layout.addWidget(QLabel("Min Confidence:"))
        self.conf_spin = QDoubleSpinBox()
        self.conf_spin.setRange(0.0, 1.0)
        self.conf_spin.setValue(0.7)
        self.conf_spin.setDecimals(2)
        conf_layout.addWidget(self.conf_spin)
        conf_layout.addStretch()
        settings_layout.addLayout(conf_layout)
        
        layout.addWidget(settings_group)
        
        # Run Button
        layout.addSpacing(20)
        
        self.run_btn = QPushButton("▶  Analyze Geometry")
        self.run_btn.setMinimumHeight(50)
        self.run_btn.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.run_btn.clicked.connect(self._run_pipeline)
        self.run_btn.setEnabled(False)
        layout.addWidget(self.run_btn)
        
        # Progress
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        
        self.status_label = QLabel("")
        self.status_label.setObjectName("status")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        
        # Version
        version = QLabel("GDI v1.0.0 - Desktop MVP")
        version.setStyleSheet("color: #858585; font-size: 11px;")
        layout.addWidget(version)
        
        return panel
    
    def _create_right_panel(self) -> QWidget:
        """Create right panel with results display."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(15)
        
        # Results Group
        results_group = QGroupBox("3. Analysis Results")
        results_layout = QVBoxLayout(results_group)
        
        # Global confidence display
        conf_frame = QFrame()
        conf_frame.setObjectName("card")
        conf_layout = QHBoxLayout(conf_frame)
        
        conf_layout.addWidget(QLabel("Global Confidence:"))
        self.global_conf_label = QLabel("--")
        self.global_conf_label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        conf_layout.addWidget(self.global_conf_label)
        conf_layout.addStretch()
        
        self.fallback_label = QLabel("")
        self.fallback_label.setStyleSheet("color: #cca700; font-weight: bold;")
        conf_layout.addWidget(self.fallback_label)
        
        results_layout.addWidget(conf_frame)
        
        # Detected Zones Tree
        results_layout.addWidget(QLabel("Detected Zones:"))
        
        self.zones_tree = QTreeWidget()
        self.zones_tree.setHeaderLabels(["Zone", "Geometry", "Confidence"])
        self.zones_tree.setColumnWidth(0, 80)
        self.zones_tree.setColumnWidth(1, 200)
        self.zones_tree.setColumnWidth(2, 100)
        self.zones_tree.setMinimumHeight(150)
        results_layout.addWidget(self.zones_tree)
        
        # Details text
        results_layout.addWidget(QLabel("Details:"))
        
        self.details_text = QTextEdit()
        self.details_text.setPlaceholderText("Analysis details will appear here...")
        self.details_text.setMaximumHeight(150)
        results_layout.addWidget(self.details_text)
        
        # YAML preview
        results_layout.addWidget(QLabel("YAML Telemetry:"))
        
        self.yaml_preview = QTextEdit()
        self.yaml_preview.setPlaceholderText("YAML output will appear here...")
        results_layout.addWidget(self.yaml_preview)
        
        layout.addWidget(results_group)
        
        return panel
    
    def _browse_file(self):
        """Open file browser dialog."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select STL File",
            "",
            "STL Files (*.stl);;All Files (*.*)"
        )
        
        if file_path:
            self.current_file = file_path
            filename = Path(file_path).name
            self.file_label.setText(f"Selected:\n<b>{filename}</b>")
            self.file_label.setStyleSheet("font-size: 14px; color: #cccccc;")
            self.file_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {COLORS["bg_card"]};
                    border: 2px solid {COLORS["accent"]};
                    border-radius: 8px;
                }}
            """)
            self.run_btn.setEnabled(True)
            self.status_bar.showMessage(f"Loaded: {file_path}")
            
            # Clear previous results
            self._clear_results()
    
    def _clear_results(self):
        """Clear previous results."""
        self.zones_tree.clear()
        self.global_conf_label.setText("--")
        self.global_conf_label.setStyleSheet("color: #cccccc;")
        self.fallback_label.setText("")
        self.details_text.clear()
        self.yaml_preview.clear()
    
    def _run_pipeline(self):
        """Execute the GDI pipeline."""
        if not self.current_file:
            QMessageBox.warning(self, "No File", "Please select an STL file first.")
            return
        
        # Disable UI
        self.run_btn.setEnabled(False)
        self.run_btn.setText("Processing...")
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self._clear_results()
        
        # Get settings
        axis_text = self.axis_combo.currentText()
        axis = axis_text[0]  # Z, Y, or X
        step = self.step_spin.value()
        confidence = self.conf_spin.value()
        
        # Start worker
        self.worker = WorkerThread(self.current_file, axis, step, confidence)
        self.worker.progress.connect(self._update_progress)
        self.worker.zone_detected.connect(self._add_zone)
        self.worker.finished_signal.connect(self._pipeline_finished)
        self.worker.start()
    
    def _update_progress(self, message: str, percent: int):
        """Update progress display."""
        self.status_label.setText(message)
        self.progress.setValue(percent)
        self.status_bar.showMessage(message)
    
    def _add_zone(self, zone_id: int, geometry: str, confidence: float):
        """Add detected zone to tree."""
        item = ZoneTreeItem(zone_id, geometry, confidence)
        self.zones_tree.addTopLevelItem(item)
    
    def _pipeline_finished(self, result, error):
        """Handle pipeline completion."""
        # Re-enable UI
        self.run_btn.setEnabled(True)
        self.run_btn.setText("▶  Analyze Geometry")
        self.progress.setVisible(False)
        
        if error:
            self.status_label.setText(f"Error: {error}")
            self.status_label.setStyleSheet("color: #f48771;")
            QMessageBox.critical(self, "Processing Error", f"Analysis failed:\n{error}")
            self.status_bar.showMessage(f"Error: {error}")
            return
        
        approx_result, yaml_path, manifest_path = result
        
        # Display results
        self.status_label.setText("Analysis complete")
        self.status_label.setStyleSheet("color: #4ec9b0;")
        
        # Global confidence
        conf = approx_result.global_confidence
        self.global_conf_label.setText(f"{conf:.1%}")
        
        if conf >= 0.9:
            self.global_conf_label.setStyleSheet("color: #4ec9b0;")
        elif conf >= 0.7:
            self.global_conf_label.setStyleSheet("color: #cca700;")
        else:
            self.global_conf_label.setStyleSheet("color: #f48771;")
        
        # Fallback warning
        if approx_result.fallback_required:
            self.fallback_label.setText("⚠ Manual review required")
            self.details_text.append(f"<b>Fallback Reason:</b> {approx_result.fallback_reason}")
        
        # Details
        details = []
        details.append(f"<b>Source:</b> {approx_result.telemetry.source_file}")
        details.append(f"<b>Total Height:</b> {approx_result.telemetry.global_state.total_height:.2f} mm")
        details.append(f"<b>Zones Detected:</b> {len(approx_result.telemetry.topological_zones)}")
        details.append(f"<b>YAML Schema:</b> {approx_result.telemetry.global_state.yaml_version}")
        self.details_text.setHtml("<br>".join(details))
        
        # YAML preview
        import yaml
        try:
            with open(yaml_path) as f:
                yaml_content = f.read()
            self.yaml_preview.setText(yaml_content)
        except Exception:
            self.yaml_preview.setText("Failed to load YAML preview")
        
        # Status bar
        self.status_bar.showMessage(f"Results saved: {yaml_path}")
    
    def _show_about(self):
        """Show about dialog."""
        QMessageBox.about(self, "About GDI",
            "<h2>GDI - Generative Design Intelligence</h2>"
            "<p><b>Version:</b> 1.0.0 (Desktop MVP)</p>"
            "<p>3D Scan → Parametric CAD → G-code</p>"
            "<p>Neurosymbolic AI for reverse engineering</p>"
            "<p><b>Architecture:</b> Python + PyQt6 + Trimesh</p>"
        )


def main():
    """Entry point for GUI application."""
    app = QApplication(sys.argv)
    app.setApplicationName("GDI Desktop")
    app.setApplicationVersion("1.0.0")
    
    window = GDI_GUI()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
