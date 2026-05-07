#!/usr/bin/env python3
"""
GP Bikes Telemetry Viewer
"""

import sys
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from functools import partial
import traceback


# ========== STYLES ==========
DARK_STYLE = """
QMainWindow, QWidget {
    background-color: #1a1a1a;
    color: #c0c0c0;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 12px;
}

QPushButton {
    background-color: #2d2d2d;
    border: 1px solid #3a3a3a;
    border-radius: 3px;
    padding: 6px 12px;
    color: #c0c0c0;
}
QPushButton:hover { background-color: #3a3a3a; border-color: #ff6b00; }
QPushButton:pressed { background-color: #404040; }
QPushButton:checked { background-color: #ff6b00; color: white; }

QToolBar {
    background-color: #252525;
    border-bottom: 1px solid #3a3a3a;
    spacing: 4px;
    padding: 2px;
}

QToolBar QToolButton {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 3px;
    padding: 4px 8px;
    color: #c0c0c0;
}
QToolBar QToolButton:hover { background-color: #3a3a3a; border-color: #3a3a3a; }
QToolBar QToolButton:checked { background-color: #ff6b00; color: white; }

QLineEdit {
    background-color: #2d2d2d;
    border: 1px solid #3a3a3a;
    border-radius: 3px;
    padding: 4px 8px;
    color: #c0c0c0;
}
QLineEdit:focus { border-color: #ff6b00; }

QListWidget {
    background-color: #222;
    border: 1px solid #3a3a3a;
    border-radius: 3px;
    outline: none;
}
QListWidget::item { padding: 3px 8px; border-bottom: 1px solid #2a2a2a; }
QListWidget::item:selected { background-color: #ff6b00; color: white; }

QComboBox {
    background-color: #2d2d2d;
    border: 1px solid #3a3a3a;
    border-radius: 3px;
    padding: 4px 8px;
    color: #c0c0c0;
}
QComboBox::drop-down { border: none; }
QComboBox QAbstractItemView {
    background-color: #2d2d2d;
    selection-background-color: #ff6b00;
    color: #c0c0c0;
}

QSplitter::handle {
    background-color: #3a3a3a;
    width: 2px;
}

QScrollBar:vertical {
    background: #1a1a1a;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #3a3a3a;
    border-radius: 5px;
    min-height: 20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QLabel { color: #c0c0c0; }

QGroupBox {
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 16px;
    font-weight: bold;
    color: #ff6b00;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
}
"""


# ========== CSV READER ==========
def read_gpbikes_csv(file_path):
    """Legge i CSV di GP Bikes con auto-detection del formato"""
    
    # Prova lettura diretta con vari skiprows
    for skip in range(0, 20):
        try:
            df = pd.read_csv(file_path, skiprows=skip, encoding='latin1')
            if len(df) > 10 and any(df.dtypes.apply(lambda x: x in ['float64', 'int64'])):
                # Rimuovi colonne/vuote duplicate
                df = df.loc[:, ~df.columns.duplicated()]
                return df
        except:
            continue
    
    # Prova engine python
    try:
        df = pd.read_csv(file_path, engine='python', encoding='latin1')
        if len(df) > 10:
            df = df.loc[:, ~df.columns.duplicated()]
            return df
    except:
        pass
    
    # Metodo manuale
    with open(file_path, 'r', encoding='latin1', errors='ignore') as f:
        lines = f.readlines()
    
    max_commas = 0
    header_idx = 0
    for i, line in enumerate(lines[:50]):
        if line.count(',') > max_commas and line.count(',') > 5:
            max_commas = line.count(',')
            header_idx = i
    
    temp_path = file_path + '.tmp.csv'
    with open(temp_path, 'w', encoding='latin1') as f:
        f.writelines(lines[header_idx:])
    
    df = pd.read_csv(temp_path, encoding='latin1')
    os.remove(temp_path)
    df = df.loc[:, ~df.columns.duplicated()]
    return df


# ========== VARIABLE CATEGORIES ==========
VARIABLE_CATEGORIES = {
    "Speed/Distance": ["Speed", "Distance", "GPS_Speed", "GPS_LatAcc", "GPS_LonAcc", "PosX", "PosY"],
    "Engine": ["Engine", "RPM", "EngineSpeed", "Gear", "CylHeadTemp", "WaterTemp", "OilTemp", "OilPress"],
    "Throttle/Brake": ["Throttle", "InputThrottle", "FrontBrake", "RearBrake", "BrakePressFront", "BrakePressRear"],
    "Suspension": ["FrontSusp", "RearSusp", "FrontSuspVel", "RearSuspVel", "SuspPotFront", "SuspPotRear"],
    "Wheels": ["FrontWheel", "RearWheel", "WheelSpeedFL", "WheelSpeedFR", "WheelSpeedRL", "WheelSpeedRR"],
    "Acceleration": ["LatAcc", "LonAcc", "VertAcc", "CombinedAcc", "YawVel", "RollVel", "PitchVel"],
    "Steering": ["Steer", "SteeringAngle", "SteerTorque", "SteerDamper"],
    "Driver": ["Clutch", "InputSteer", "InputThrottle", "InputBrake", "InputClutch"],
    "Position": ["PosX", "PosY", "PosZ", "Latitude", "Longitude", "Altitude"],
}

def categorize_variable(var_name):
    """Categorize a variable name"""
    var_lower = var_name.lower().replace(" ", "").replace("_", "")
    for category, patterns in VARIABLE_CATEGORIES.items():
        for pattern in patterns:
            if pattern.lower().replace(" ", "").replace("_", "") in var_lower:
                return category
    return "Other"


# ========== TELEMETRY PLOT WIDGET ==========
class TelemetryPlot(FigureCanvas):
    """Single telemetry graph"""
    
    def __init__(self, parent=None, title="", ylabel="", color='#ff6b00'):
        self.fig = Figure(figsize=(12, 2.5), dpi=100, facecolor='#1a1a1a')
        super().__init__(self.fig)
        self.setParent(parent)
        
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor('#1e1e1e')
        self.ax.set_title(title, color='#c0c0c0', fontsize=10, fontweight='bold', pad=2)
        self.ax.set_ylabel(ylabel, color='#888', fontsize=8)
        self.ax.set_xlabel("")
        self.ax.tick_params(colors='#666', labelsize=8)
        self.ax.grid(True, alpha=0.2, color='#444', linewidth=0.5)
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)
        self.ax.spines['bottom'].set_color('#444')
        self.ax.spines['left'].set_color('#444')
        
        self.lines = []
        self.cursor_lines = []
        self.cursor_texts = []
        self.color = color
        self.stat_text = None
        
        self.fig.tight_layout(pad=0.5)
        self.mpl_connect('motion_notify_event', self.on_mouse_move)
    
    def plot(self, x, y, name, color=None):
        if color is None:
            color = self.color
        line, = self.ax.plot(x, y, color=color, linewidth=1.2, alpha=0.9)
        self.lines.append({'line': line, 'name': name, 'x': x.values, 'y': y.values})
        self._update_stats(x.values, y.values, name)
        self.fig.tight_layout(pad=0.5)
        self.draw()
    
    def clear(self):
        self.ax.clear()
        self.lines = []
        self.cursor_lines = []
        self.cursor_texts = []
        self.stat_text = None
        self.ax.grid(True, alpha=0.2, color='#444', linewidth=0.5)
        self.ax.tick_params(colors='#666', labelsize=8)
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)
        self.ax.spines['bottom'].set_color('#444')
        self.ax.spines['left'].set_color('#444')
    
    def _update_stats(self, x, y, name):
        """Mostra min/max/avg"""
        if self.stat_text:
            self.stat_text.remove()
        valid_y = y[~np.isnan(y)]
        if len(valid_y) > 0:
            y_min, y_max = np.min(valid_y), np.max(valid_y)
            y_avg = np.mean(valid_y)
            text = f"Min:{y_min:.1f}  Avg:{y_avg:.1f}  Max:{y_max:.1f}"
            self.stat_text = self.ax.text(0.99, 0.01, text, transform=self.ax.transAxes,
                                         fontsize=7, color='#666', ha='right', va='bottom')
    
    def on_mouse_move(self, event):
        # Rimuovi cursori precedenti
        for cl in self.cursor_lines:
            cl.remove()
        for ct in self.cursor_texts:
            ct.remove()
        self.cursor_lines.clear()
        self.cursor_texts.clear()
        
        if event.inaxes != self.ax or event.xdata is None:
            self.draw()
            return
        
        x = event.xdata
        self.cursor_lines.append(self.ax.axvline(x=x, color='#ff6b00', linestyle='-', 
                                                   alpha=0.6, linewidth=1))
        
        text = f"Time: {x:.3f}s"
        for item in self.lines:
            idx = np.argmin(np.abs(item['x'] - x))
            if idx < len(item['y']):
                val = item['y'][idx]
                text += f"\n{item['name']}: {val:.2f}"
        
        ct = self.ax.text(0.02, 0.98, text, transform=self.ax.transAxes,
                         fontsize=8, color='#c0c0c0', va='top',
                         bbox=dict(boxstyle='round,pad=0.5', facecolor='#1a1a1a', 
                                 edgecolor='#444', alpha=0.9))
        self.cursor_texts.append(ct)
        self.draw()


# ========== TRACK MAP WIDGET ==========
class TrackMapWidget(FigureCanvas):
    """Mini track map widget"""
    
    def __init__(self, parent=None):
        self.fig = Figure(figsize=(3, 3), dpi=100, facecolor='#1a1a1a')
        super().__init__(self.fig)
        self.setParent(parent)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor('#1e1e1e')
        self.ax.set_aspect('equal')
        self.ax.tick_params(colors='#444', labelsize=7)
        self.ax.set_title("Track Map", color='#888', fontsize=9)
        self.track_line = None
        self.pos_marker = None
        self.fig.tight_layout(pad=0.5)
    
    def plot_track(self, pos_x, pos_y):
        self.ax.clear()
        self.ax.set_facecolor('#1e1e1e')
        self.track_line, = self.ax.plot(pos_x, pos_y, color='#444', linewidth=1.5, alpha=0.7)
        self.ax.set_aspect('equal')
        self.ax.set_title("Track Map", color='#888', fontsize=9)
        self.ax.tick_params(colors='#444', labelsize=7)
        self.fig.tight_layout(pad=0.5)
        self.draw()
    
    def update_position(self, pos_x, pos_y):
        if self.pos_marker:
            self.pos_marker.remove()
        self.pos_marker, = self.ax.plot([pos_x], [pos_y], 'o', color='#ff6b00', 
                                         markersize=8, zorder=5)
        self.draw()


# ========== MAIN WINDOW ==========
class TelemetryViewerPro(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_data = None
        self.current_lap_data = None
        self.laps = []
        self.time_col = None
        self.dist_col = None
        self.beacon_markers = []
        self.plots = []
        self.lap_combo_items = []
        self.color_palette = [
            '#ff6b00', '#00ff88', '#ff4444', '#4488ff', '#ff8844',
            '#ff44ff', '#ffff44', '#44ffff', '#ff8800', '#88ff00',
            '#0088ff', '#ff0088', '#8800ff', '#00ff88', '#ff4488'
        ]
        
        self.initUI()
    
    def initUI(self):
        self.setWindowTitle("GP Bikes Telemetry Viewer")
        self.setGeometry(50, 50, 1600, 900)
        self.setStyleSheet(DARK_STYLE)
        
        # Widget centrale
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # ========== TOOLBAR ==========
        self.create_toolbar()
        
        # ========== MAIN CONTENT ==========
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(4, 4, 4, 4)
        content_layout.setSpacing(4)
        
        # ========== LEFT PANEL (Variable Browser) ==========
        left_panel = QWidget()
        left_panel.setFixedWidth(260)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(4, 4, 4, 4)
        left_layout.setSpacing(6)
        
        # File info
        self.file_label = QLabel("No file loaded")
        self.file_label.setStyleSheet("color: #888; font-size: 10px; padding: 4px;")
        self.file_label.setWordWrap(True)
        left_layout.addWidget(self.file_label)
        
        # Lap selector
        lap_group = QGroupBox("Lap Selection")
        lap_layout = QVBoxLayout(lap_group)
        self.lap_combo = QComboBox()
        self.lap_combo.currentIndexChanged.connect(self.on_lap_changed)
        lap_layout.addWidget(self.lap_combo)
        
        lap_btn_layout = QHBoxLayout()
        self.prev_lap_btn = QPushButton("◀")
        self.next_lap_btn = QPushButton("▶")
        self.prev_lap_btn.clicked.connect(lambda: self.lap_combo.setCurrentIndex(
            max(0, self.lap_combo.currentIndex() - 1)))
        self.next_lap_btn.clicked.connect(lambda: self.lap_combo.setCurrentIndex(
            min(self.lap_combo.count() - 1, self.lap_combo.currentIndex() + 1)))
        self.prev_lap_btn.setFixedWidth(30)
        self.next_lap_btn.setFixedWidth(30)
        lap_btn_layout.addWidget(self.prev_lap_btn)
        lap_btn_layout.addWidget(self.next_lap_btn)
        lap_btn_layout.addStretch()
        lap_layout.addLayout(lap_btn_layout)
        
        self.lap_info_label = QLabel("--")
        self.lap_info_label.setStyleSheet("color: #ff6b00; font-size: 11px;")
        lap_layout.addWidget(self.lap_info_label)
        
        left_layout.addWidget(lap_group)
        
        # Variable search
        self.var_search = QLineEdit()
        self.var_search.setPlaceholderText("🔍 Search variables...")
        self.var_search.textChanged.connect(self.filter_variables)
        left_layout.addWidget(self.var_search)
        
        # Variable tree (categorized)
        self.var_tree = QTreeWidget()
        self.var_tree.setHeaderHidden(True)
        self.var_tree.setSelectionMode(QAbstractItemView.MultiSelection)
        self.var_tree.itemSelectionChanged.connect(self.on_var_selection_changed)
        left_layout.addWidget(self.var_tree)
        
        # Select buttons
        btn_layout = QHBoxLayout()
        select_all_btn = QPushButton("All")
        deselect_btn = QPushButton("None")
        select_all_btn.clicked.connect(self.select_all_vars)
        deselect_btn.clicked.connect(self.deselect_all_vars)
        select_all_btn.setFixedHeight(28)
        deselect_btn.setFixedHeight(28)
        btn_layout.addWidget(select_all_btn)
        btn_layout.addWidget(deselect_btn)
        left_layout.addLayout(btn_layout)
        
        left_layout.addStretch()
        
        # ========== RIGHT PANEL (Graphs) ==========
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Graph area with scroll
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setSpacing(6)
        self.scroll_layout.setContentsMargins(4, 4, 4, 4)
        self.scroll_area.setWidget(self.scroll_widget)
        right_layout.addWidget(self.scroll_area)
        
        # Status bar
        self.position_label = QLabel("  Time: -- | Ready")
        self.position_label.setStyleSheet("color: #666; font-size: 10px; background: #222; padding: 4px;")
        right_layout.addWidget(self.position_label)
        
        # ========== ASSEMBLY ==========
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        content_layout.addWidget(splitter)
        
        main_layout.addWidget(content_widget)
        
        self.statusBar().showMessage("Ready - Open a CSV file to begin")
        self.statusBar().setStyleSheet("color: #888; font-size: 10px;")
    
    def create_toolbar(self):
        """Create toolbar"""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(20, 20))
        self.addToolBar(toolbar)
        
        # Load button
        load_action = QAction("📂 Open", self)
        load_action.triggered.connect(self.load_file)
        toolbar.addAction(load_action)
        
        toolbar.addSeparator()
        
        # X-axis mode
        toolbar.addWidget(QLabel(" X-Axis: "))
        self.xaxis_combo = QComboBox()
        self.xaxis_combo.addItems(["Time (s)", "Distance (m)"])
        self.xaxis_combo.currentIndexChanged.connect(self.update_plots)
        toolbar.addWidget(self.xaxis_combo)
        
        toolbar.addSeparator()
        
        # Overlay laps
        self.overlay_check = QCheckBox("Overlay Laps")
        self.overlay_check.setStyleSheet("color: #c0c0c0;")
        self.overlay_check.stateChanged.connect(self.update_plots)
        toolbar.addWidget(self.overlay_check)
        
        toolbar.addSeparator()
        
        # Zoom controls
        zoom_fit = QPushButton("Fit")
        zoom_fit.clicked.connect(self.zoom_fit)
        zoom_fit.setFixedWidth(40)
        toolbar.addWidget(zoom_fit)
    
    # ========================================================================
    # DATA LOADING
    # ========================================================================
    def load_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open GP Bikes CSV", "", "CSV Files (*.csv);;All Files (*)")
        
        if not file_path:
            return
        
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            self.current_data = read_gpbikes_csv(file_path)
            
            if self.current_data.empty:
                raise Exception("No valid data found in file")
            
            # Detect time column
            self.time_col = self._detect_column(['Time', 'time', 'TIME', 't', 'T'])
            
            # Detect distance column
            self.dist_col = self._detect_column(['Distance', 'distance', 'Dist', 'dist', 'LapDistance'])
            
            # Extract header info (CSV metadata)
            self._parse_csv_header(file_path)
            
            # Update file label
            basename = os.path.basename(file_path)
            num_rows = len(self.current_data)
            num_cols = len(self.current_data.columns)
            self.file_label.setText(f"📁 {basename}\n{num_rows:,} rows × {num_cols} cols")
            
            # Populate variables
            self.populate_variable_tree()
            
            # Detect laps
            self.detect_laps()
            
            self.statusBar().showMessage(f"✅ Loaded: {basename}")
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load file:\n{str(e)}")
            traceback.print_exc()
        
        finally:
            QApplication.restoreOverrideCursor()
    
    def _parse_csv_header(self, file_path):
        """Parse CSV metadata header"""
        try:
            with open(file_path, 'r', encoding='latin1', errors='ignore') as f:
                header_lines = []
                for line in f:
                    if line.startswith('"'):
                        header_lines.append(line.strip())
                    else:
                        break
                
                for line in header_lines:
                    if 'Beacon Marker' in line or 'Beacon' in line:
                        parts = line.split(',')
                        self.beacon_markers = [float(p.strip('"')) for p in parts[1:] if p.strip('"').replace('.','').isdigit()]
        except:
            self.beacon_markers = []
    
    def _detect_column(self, candidates):
        """Detect a column from candidates list"""
        df_cols = [c.lower().strip().replace('"', '') for c in self.current_data.columns]
        for cand in candidates:
            cand_lower = cand.lower().strip().replace('"', '')
            if cand_lower in df_cols:
                return self.current_data.columns[df_cols.index(cand_lower)]
        
        # Fallback: find numeric column with reasonable values
        for col in self.current_data.columns:
            try:
                data = pd.to_numeric(self.current_data[col], errors='coerce')
                if data.notna().sum() > 10 and data.max() > 1:
                    return col
            except:
                pass
        return None
    
    # ========================================================================
    # LAP DETECTION
    # ========================================================================
    def detect_laps(self):
        """Advanced lap detection with multiple methods"""
        self.laps = []
        
        if self.current_data is None:
            return
        
        df = self.current_data
        
        # Method 1: Distance-based detection
        if self.dist_col and self.dist_col in df.columns:
            dist = pd.to_numeric(df[self.dist_col], errors='coerce')
            # Find distance resets (lap boundaries)
            dist_diff = dist.diff()
            lap_starts = [0] + list(dist_diff[dist_diff < -1].index)
            
            if len(lap_starts) > 1:
                for i, start in enumerate(lap_starts):
                    end = lap_starts[i + 1] if i + 1 < len(lap_starts) else len(df)
                    lap_data = df.iloc[start:end].copy()
                    if len(lap_data) > 20:
                        self._add_lap(lap_data, i + 1)
                if self.laps:
                    self._update_lap_combo()
                    return
        
        # Method 2: Time-based (estimate ~110s laps)
        if self.time_col and self.time_col in df.columns:
            time_data = pd.to_numeric(df[self.time_col], errors='coerce')
            total_time = time_data.iloc[-1] - time_data.iloc[0]
            est_lap_time = 110  # seconds
            num_laps = max(1, int(total_time / est_lap_time))
            samples_per_lap = len(df) // num_laps
            
            for i in range(num_laps):
                start = i * samples_per_lap
                end = (i + 1) * samples_per_lap if i + 1 < num_laps else len(df)
                lap_data = df.iloc[start:end].copy()
                if len(lap_data) > 20:
                    self._add_lap(lap_data, i + 1)
            if self.laps:
                self._update_lap_combo()
                return
        
        # Method 3: Single lap
        if len(df) > 20:
            self._add_lap(df.copy(), 1)
            self._update_lap_combo()
    
    def _add_lap(self, lap_data, lap_num):
        """Add a lap with time calculation"""
        if self.time_col and self.time_col in lap_data.columns:
            time_data = pd.to_numeric(lap_data[self.time_col], errors='coerce')
            lap_time = time_data.iloc[-1] - time_data.iloc[0]
        else:
            lap_time = len(lap_data) * 0.05  # assume 20Hz
        
        minutes = int(lap_time // 60)
        seconds = lap_time % 60
        
        self.laps.append({
            'num': lap_num,
            'data': lap_data,
            'time': lap_time,
            'time_str': f"{minutes}:{seconds:06.3f}",
            'samples': len(lap_data)
        })
    
    def _update_lap_combo(self):
        self.lap_combo.blockSignals(True)
        self.lap_combo.clear()
        for lap in self.laps:
            self.lap_combo.addItem(f"Lap {lap['num']} - {lap['time_str']} ({lap['samples']} pts)")
        self.lap_combo.setCurrentIndex(len(self.laps) - 1)  # Select last lap
        self.lap_combo.blockSignals(False)
        self.on_lap_changed(self.lap_combo.currentIndex())
    
    def on_lap_changed(self, index):
        if index < 0 or index >= len(self.laps):
            return
        lap = self.laps[index]
        self.current_lap_data = lap['data']
        self.lap_info_label.setText(f"Lap {lap['num']}\nTime: {lap['time_str']}\nPoints: {lap['samples']:,}")
        self.update_plots()
    
    # ========================================================================
    # VARIABLE TREE
    # ========================================================================
    def populate_variable_tree(self):
        """Populate categorized variable tree"""
        self.var_tree.clear()
        
        # Get numeric columns
        numeric_cols = []
        for col in self.current_data.columns:
            try:
                data = pd.to_numeric(self.current_data[col], errors='coerce')
                if data.notna().sum() > 10:
                    numeric_cols.append(col)
            except:
                pass
        
        # Categorize
        categories = {}
        for col in numeric_cols:
            cat = categorize_variable(col)
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(col)
        
        # Sort categories
        preferred_order = ["Speed/Distance", "Engine", "Throttle/Brake", "Suspension", 
                          "Wheels", "Acceleration", "Steering", "Driver", "Position", "Other"]
        
        for cat in preferred_order:
            if cat in categories:
                parent = QTreeWidgetItem(self.var_tree, [cat])
                parent.setFlags(parent.flags() & ~Qt.ItemIsSelectable)
                font = QFont()
                font.setBold(True)
                parent.setFont(0, font)
                parent.setForeground(0, QColor('#ff6b00'))
                
                for var in sorted(categories[cat]):
                    item = QTreeWidgetItem(parent, [var])
                    item.setData(0, Qt.UserRole, var)
                    item.setFlags(item.flags() | Qt.ItemIsSelectable)
        
        self.var_tree.expandAll()
    
    def filter_variables(self, text):
        """Filter variable tree by search text"""
        for i in range(self.var_tree.topLevelItemCount()):
            parent = self.var_tree.topLevelItem(i)
            visible = False
            for j in range(parent.childCount()):
                child = parent.child(j)
                if text.lower() in child.text(0).lower():
                    child.setHidden(False)
                    visible = True
                else:
                    child.setHidden(True)
            parent.setHidden(not visible)
    
    def select_all_vars(self):
        for i in range(self.var_tree.topLevelItemCount()):
            parent = self.var_tree.topLevelItem(i)
            for j in range(parent.childCount()):
                item = parent.child(j)
                if not item.isHidden():
                    item.setSelected(True)
    
    def deselect_all_vars(self):
        self.var_tree.clearSelection()
    
    def on_var_selection_changed(self):
        self.update_plots()
    
    def get_selected_variables(self):
        """Get list of selected variable names"""
        selected = []
        for item in self.var_tree.selectedItems():
            if item.data(0, Qt.UserRole):
                selected.append(item.data(0, Qt.UserRole))
        return selected
    
    # ========================================================================
    # PLOTTING
    # ========================================================================
    def update_plots(self):
        """Update all telemetry plots"""
        # Clear existing plots
        for plot in self.plots:
            plot.setParent(None)
        self.plots.clear()
        
        # Clear layout
        for i in reversed(range(self.scroll_layout.count())):
            widget = self.scroll_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        if self.current_lap_data is None:
            return
        
        selected_vars = self.get_selected_variables()
        if not selected_vars:
            label = QLabel("Select variables from the left panel to display telemetry data")
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("color: #666; padding: 40px; font-size: 14px;")
            self.scroll_layout.addWidget(label)
            return
        
        # Get X-axis data
        x_data, x_label = self._get_x_axis_data(self.current_lap_data)
        
        # Create plot for each variable
        for i, var in enumerate(selected_vars):
            if var not in self.current_lap_data.columns:
                continue
            
            data = pd.to_numeric(self.current_lap_data[var], errors='coerce')
            if data.notna().sum() < 5:
                continue
            
            color = self.color_palette[i % len(self.color_palette)]
            plot = TelemetryPlot(self.scroll_widget, title=var, ylabel=var, color=color)
            plot.plot(x_data, data, var, color)
            self.plots.append(plot)
            self.scroll_layout.addWidget(plot)
        
        # Add beacon markers if available
        if self.beacon_markers:
            for plot in self.plots:
                for bm in self.beacon_markers:
                    plot.ax.axvline(x=bm, color='#ffff00', linestyle='--', 
                                  alpha=0.3, linewidth=0.5)
        
        self.scroll_layout.addStretch()
    
    def _get_x_axis_data(self, lap_data):
        """Get X-axis data based on current mode"""
        if self.xaxis_combo.currentText() == "Distance (m)" and self.dist_col:
            try:
                dist = pd.to_numeric(lap_data[self.dist_col], errors='coerce')
                # Make distance monotonic increasing
                dist = dist - dist.iloc[0]
                dist[dist < 0] = np.nan
                dist = dist.fillna(method='ffill')
                return dist, "Distance (m)"
            except:
                pass
        
        if self.time_col and self.time_col in lap_data.columns:
            time_data = pd.to_numeric(lap_data[self.time_col], errors='coerce')
            return time_data - time_data.iloc[0], "Time (s)"
        
        return np.arange(len(lap_data)) * 0.05, "Time (s)"
    
    def zoom_fit(self):
        """Reset zoom on all plots"""
        for plot in self.plots:
            plot.ax.relim()
            plot.ax.autoscale_view()
            plot.draw()


# ========== MAIN ==========
def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Set dark palette
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(26, 26, 26))
    palette.setColor(QPalette.WindowText, QColor(192, 192, 192))
    palette.setColor(QPalette.Base, QColor(30, 30, 30))
    palette.setColor(QPalette.AlternateBase, QColor(40, 40, 40))
    palette.setColor(QPalette.ToolTipBase, QColor(255, 107, 0))
    palette.setColor(QPalette.ToolTipText, QColor(255, 255, 255))
    palette.setColor(QPalette.Text, QColor(192, 192, 192))
    palette.setColor(QPalette.Button, QColor(45, 45, 45))
    palette.setColor(QPalette.ButtonText, QColor(192, 192, 192))
    palette.setColor(QPalette.Highlight, QColor(255, 107, 0))
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    app.setPalette(palette)
    
    window = TelemetryViewerPro()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()