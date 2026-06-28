# Lib/Colors.py
"""
Chart color constants for PyQtGraph series.
Each color is a string accepted by pyqtgraph's pen= argument.
"""

# Primary channel colors (7 channels)
CHANNEL_COLORS = [
    "#FF6B35",   # 0 — orange
    "#4ECDC4",   # 1 — teal
    "#45B7D1",   # 2 — sky blue
    "#96CEB4",   # 3 — sage green
    "#FFEAA7",   # 4 — yellow
    "#DDA0DD",   # 5 — plum
    "#98D8C8",   # 6 — mint
]

# Photodiode pair colors
IUP_COLOR = "#FF8C00"        # dark orange
IDOWN_COLOR = "#00BFFF"      # deep sky blue
IUP7_COLOR = "#90EE90"       # light green
IDOWN7_COLOR = "#FF69B4"     # hot pink

# Signal colors
LASER_COLOR = "#FF4444"      # red
SR_COLOR = "#44FF44"         # green
PHASE_COLOR = "#AAAAFF"      # light blue

# Point signal pairs (2 per channel = 14 total)
POINT_COLORS = [
    "#FF6B35", "#FF9966",   # channel 0
    "#4ECDC4", "#88E8E0",   # channel 1
    "#45B7D1", "#88D4E8",   # channel 2
    "#96CEB4", "#BBE0CC",   # channel 3
    "#FFEAA7", "#FFF4CC",   # channel 4
    "#DDA0DD", "#EEC8EE",   # channel 5
    "#98D8C8", "#BBEADD",   # channel 6
]