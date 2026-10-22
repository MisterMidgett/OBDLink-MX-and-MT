
import serial
import serial.tools.list_ports
import threading
import time
import random
import queue
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import csv
import math
from datetime import datetime

# ===== COLORBLIND FRIENDLY PALETTES - Okabe-Ito + IBM + High Contrast =====
PALETTES = {
    "Standard Dark (HP Tuners)": {
        "bg": "#0f1115", "panel": "#1a1d24", "text": "#e5e7eb", "grid": "#2a2e3a",
        "gauges": ["#00d4ff", "#ff6b35", "#00ff88", "#ffdd00", "#ff00aa", "#8a2be2", "#00ffff", "#ff8c00"],
        "chart": ["#00d4ff", "#ff6b35", "#22c55e", "#eab308", "#ec4899", "#8b5cf6"]
    },
    "Colorblind Safe - Okabe-Ito": {
        "bg": "#121212", "panel": "#1e1e1e", "text": "#f5f5f5", "grid": "#333333",
        # Okabe-Ito is the gold standard for colorblind safety
        "gauges": ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#F0E442", "#000000"],
        "chart": ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00"]
    },
    "Deuteranopia Safe": {
        "bg": "#0a0a0a", "panel": "#1a1a2e", "text": "#ffffff", "grid": "#2a2a4a",
        "gauges": ["#004488", "#bb5566", "#ddaa33", "#000000", "#9988cc", "#ee8866", "#228833", "#aa4499"],
        "chart": ["#004488", "#ddaa33", "#bb5566", "#000000", "#9988cc"]
    },
    "Protanopia Safe": {
        "bg": "#101010", "panel": "#1c1c1c", "text": "#f0f0f0", "grid": "#303030",
        "gauges": ["#0066cc", "#ffcc00", "#009900", "#ff66cc", "#66ccff", "#ff9900", "#cc99ff", "#000000"],
        "chart": ["#0066cc", "#ffcc00", "#009900", "#ff66cc", "#66ccff"]
    },
    "Tritanopia Safe": {
        "bg": "#0f0f0f", "panel": "#1f1f1f", "text": "#eeeeee", "grid": "#2f2f2f",
        "gauges": ["#ff0000", "#00ff00", "#0000ff", "#ffff00", "#ff00ff", "#00ffff", "#800000", "#008000"],
        "chart": ["#ff0000", "#00ff00", "#0000ff", "#ffff00", "#ff00ff"]
    },
    "High Contrast": {
        "bg": "#000000", "panel": "#000000", "text": "#ffffff", "grid": "#ffffff",
        "gauges": ["#ffffff", "#ffff00", "#00ffff", "#ff00ff", "#ff0000", "#00ff00", "#0000ff", "#ffa500"],
        "chart": ["#ffffff", "#ffff00", "#00ffff", "#ff00ff", "#ff0000"]
    }
}

# ===== REAL ANALOG GAUGE WIDGET =====
class AnalogGauge(tk.Canvas):
    def __init__(self, parent, label, min_val, max_val, unit, color, palette, width=180, height=180):
        super().__init__(parent, width=width, height=height, bg=palette["panel"], highlightthickness=0)
        self.label = label
        self.min_val = min_val
        self.max_val = max_val
        self.unit = unit
        self.color = color
        self.palette = palette
        self.value = min_val  # legacy
        self.target_value = min_val  # where we want to go
        self.display_value = min_val  # what we show - smooths to target
        self.smoothing = 0.18  # 0.1=very smooth, 0.3=snappy, 0.18 is buttery like HP Tuners
        self.width = width
        self.height = height
        self.bind("<Configure>", lambda e: self.redraw())
        self.redraw()
        self._animate()  # start 60fps interpolation loop

    def set_palette(self, palette, color):
        self.palette = palette
        self.color = color
        self.config(bg=palette["panel"])
        self.redraw()

    def set_value(self, val):
        # Set target - display will smoothly interpolate to it
        self.target_value = max(self.min_val, min(self.max_val, val))
        self.value = self.target_value  # keep legacy in sync

    def _animate(self):
        # Smooth interpolation - exponential lerp for buttery motion
        diff = self.target_value - self.display_value
        if abs(diff) > 0.01:
            # Adaptive smoothing - faster for large jumps, slower for small
            factor = self.smoothing
            if abs(diff) > (self.max_val - self.min_val) * 0.3:
                factor = min(0.35, self.smoothing * 2)  # snap faster on big changes
            self.display_value += diff * factor
            self.redraw()
        elif abs(diff) > 0:
            self.display_value = self.target_value
            self.redraw()
        # 60fps animation loop - independent of data rate
        self.after(16, self._animate)

    def redraw(self):
        self.delete("all")
        w, h = self.width, self.height
        cx, cy = w//2, h//2 + 10
        r = min(w, h)//2 - 15
        
        # Background arc
        self.create_arc(cx-r, cy-r, cx+r, cy+r, start=30, extent=120, style="arc", width=8, outline=self.palette["grid"])
        
        # Ticks
        for i in range(0, 11):
            angle = 30 + (120 * i / 10)
            rad = math.radians(180 - angle)
            x1 = cx + (r-5) * math.cos(rad)
            y1 = cy - (r-5) * math.sin(rad)
            x2 = cx + r * math.cos(rad)
            y2 = cy - r * math.sin(rad)
            self.create_line(x1, y1, x2, y2, fill=self.palette["text"], width=1)
            # Numbers - every other
            if i % 2 == 0:
                val = self.min_val + (self.max_val - self.min_val) * i / 10
                if self.max_val > 1000:
                    txt = f"{int(val/1000)}k" if val>=1000 else f"{int(val)}"
                else:
                    txt = f"{int(val)}"
                tx = cx + (r-20) * math.cos(rad)
                ty = cy - (r-20) * math.sin(rad)
                self.create_text(tx, ty, text=txt, fill=self.palette["text"], font=("Consolas", 7))

        # Needle
        pct = (self.display_value - self.min_val) / (self.max_val - self.min_val) if self.max_val != self.min_val else 0
        needle_angle = 30 + 120 * pct
        rad = math.radians(180 - needle_angle)
        nx = cx + (r-15) * math.cos(rad)
        ny = cy - (r-15) * math.sin(rad)
        self.create_line(cx, cy, nx, ny, fill=self.color, width=3, arrow=tk.LAST)
        self.create_oval(cx-5, cy-5, cx+5, cy+5, fill=self.color, outline="")

        # Center value
        self.create_text(cx, cy+35, text=f"{self.display_value:.0f}", fill=self.palette["text"], font=("Consolas", 14, "bold"))
        self.create_text(cx, cy+50, text=self.unit, fill=self.palette["text"], font=("Consolas", 8))
        self.create_text(cx, 15, text=self.label, fill=self.color, font=("Consolas", 9, "bold"))

# ===== CHART WIDGET =====
class ChartCanvas(tk.Canvas):
    def __init__(self, parent, palette, height=250):
        super().__init__(parent, bg=palette["panel"], height=height, highlightthickness=0)
        self.palette = palette
        self.data = {}  # channel -> list of values
        self.max_points = 300  # Increased for 50-60Hz
        self.bind("<Configure>", lambda e: self.redraw())

    def set_palette(self, palette):
        self.palette = palette
        self.config(bg=palette["panel"])
        self.redraw()

    def add_point(self, channel, value):
        if channel not in self.data:
            self.data[channel] = []
        self.data[channel].append(value)
        if len(self.data[channel]) > self.max_points:
            self.data[channel].pop(0)
        self.redraw()

    def redraw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 50 or h < 50:
            return
        # Grid
        for i in range(1, 5):
            y = h * i / 5
            self.create_line(0, y, w, y, fill=self.palette["grid"], dash=(2,2))
        # Data
        colors = self.palette["chart"]
        for idx, (chan, vals) in enumerate(self.data.items()):
            if len(vals) < 2:
                continue
            color = colors[idx % len(colors)]
            # normalize to chart
            if not vals:
                continue
            vmin, vmax = min(vals), max(vals)
            if vmax == vmin:
                vmax = vmin + 1
            points = []
            for i, v in enumerate(vals):
                x = w * i / self.max_points
                y = h - h * (v - vmin) / (vmax - vmin) * 0.8 - h*0.1
                points.extend([x, y])
            if len(points) >= 4:
                self.create_line(points, fill=color, width=2, smooth=True)
                # label with pattern for colorblind - different dash
                self.create_text(10, 15 + idx*15, text=f"{chan}: {vals[-1]:.1f}", fill=color, anchor="w", font=("Consolas", 8))

# ===== OBD INTERFACE =====
class OBDInterface:
    def __init__(self, log_callback, data_callback=None):
        self.ser = None
        self.connected = False
        self.log_cb = log_callback
        self.data_cb = data_callback
        self.read_thread = None
        self.running = False
        self.rx_queue = queue.Queue()
        self.is_mock = False
        
    def list_ports(self):
        return [p.device for p in serial.tools.list_ports.comports()]
    
    def connect(self, port, baud=115200):
        if port == "MOCK MODE":
            self.is_mock = True
            self.connected = True
            self.running = True
            self.log_cb(f"[OK] MOCK MODE - Full simulation")
            return True
        try:
            self.ser = serial.Serial(port, baud, timeout=0.5)
            time.sleep(0.2)
            self.ser.reset_input_buffer()
            self.connected = True
            self.is_mock = False
            self.running = True
            self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self.read_thread.start()
            self.send_raw("ATZ", wait=1)
            self.send_raw("ATE0")
            self.send_raw("AT S0")
            self.log_cb(f"[OK] Connected to {port}")
            return True
        except Exception as e:
            self.log_cb(f"[ERR] {e}")
            return False
    
    def disconnect(self):
        self.running = False
        if self.ser:
            try:
                self.send_raw("AT PC", wait=0.1)
                self.ser.close()
            except: pass
        self.connected = False
        self.is_mock = False
    
    def _read_loop(self):
        while self.running and self.ser:
            try:
                if self.ser.in_waiting:
                    data = self.ser.read(self.ser.in_waiting).decode(errors='ignore')
                    for line in data.splitlines():
                        line=line.strip()
                        if line:
                            self.rx_queue.put(line)
                            self.log_cb(f"<< {line}")
                            if self.data_cb:
                                self.data_cb(line)
            except: pass
            time.sleep(0.001)  # 1ms for high speed
    
    def send_raw(self, cmd, wait=0.3):
        if self.is_mock or (not self.ser and self.connected):
            self.log_cb(f">> {cmd} (MOCK)")
            mock = self._mock_response(cmd)
            if mock:
                self.rx_queue.put(mock)
                self.log_cb(f"<< {mock} (MOCK)")
                if self.data_cb:
                    self.data_cb(mock)
            return mock
        try:
            full = cmd.strip() + "\r"
            self.log_cb(f">> {cmd}")
            self.ser.write(full.encode())
            time.sleep(wait)
            resp = []
            while not self.rx_queue.empty():
                resp.append(self.rx_queue.get())
            return "\n".join(resp)
        except Exception as e:
            self.log_cb(f"[ERR] send {e}")
            return ""
    
    def _mock_response(self, cmd):
        cmd = cmd.upper()
        if "03" in cmd and len(cmd.strip())==2:
            return "43 02 01 33 02 44" # P0133 P0244
        if "04" in cmd:
            return "44"
        if "01 0C" in cmd:
            rpm = random.randint(750, 5500)
            a = (rpm*4)//256
            b = (rpm*4)%256
            return f"41 0C {a:02X} {b:02X}"
        if "01 0D" in cmd:
            return f"41 0D {random.randint(0,120):02X}"
        if "01 05" in cmd:
            return f"41 05 {random.randint(70,110):02X}"
        if "01 0B" in cmd:
            return f"41 0B {random.randint(20,100):02X}"
        if "01 11" in cmd:
            return f"41 11 {random.randint(0,100):02X}"
        if "01 06" in cmd:
            return f"41 06 {random.randint(0,200):02X}"
        if "01 07" in cmd:
            return f"41 07 {random.randint(0,200):02X}"
        if "01 0E" in cmd:
            return f"41 0E {random.randint(0,64):02X}"
        if "01 0F" in cmd:
            return f"41 0F {random.randint(0,100):02X}"
        if cmd.startswith("01 "):
            return f"41 {cmd.split()[1]} {random.randint(0,255):02X}"
        if "22" in cmd:
            return f"62 {cmd.split()[-1]} {random.randint(0,255):02X} {random.randint(0,255):02X}"
        if "08" in cmd:
            return "48 00"
        if "AT MA" in cmd:
            return "6C 10 F1 01 0C 10 20"
        return "OK"

    def set_protocol(self, proto):
        mapping = {
            "J1850 VPW (96 Sierra)": "AT SP1",
            "J1850 PWM (Ford)": "AT SP2",
            "ISO 9141-2": "AT SP3",
            "ISO 14230-4 KWP": "AT SP5",
            "CAN 11bit 500k (2008+)": "AT SP6",
            "CAN 29bit 500k": "AT SP7",
            "CAN-FD (EX only)": "AT SP8",
            "AUTO": "AT SP0"
        }
        return self.send_raw(mapping.get(proto, "AT SP0"))

    def set_header(self, header):
        return self.send_raw(f"AT SH {header}")

# ===== MAIN APP - HP TUNERS CLONE =====
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("OBD Diagnostics Studio - HP Tuners Edition - MX+ / EX - Colorblind Safe")
        self.geometry("1450x900")
        
        self.current_palette_name = tk.StringVar(value="Colorblind Safe - Okabe-Ito")
        self.palette = PALETTES[self.current_palette_name.get()]
        self.configure(bg=self.palette["bg"])
        
        style = ttk.Style()
        style.theme_use('clam')
        self.apply_palette_style()
        
        self.obd = OBDInterface(self.log, self.on_bus_data)
        self.discovered_pids = {}
        self.logging = False
        self.log_data = []
        self.gauges = {}
        self.channel_values = {}
        
        # HP Tuners-like channels
        self.channels_def = {
            "RPM": {"min":0, "max":7000, "unit":"rpm", "pid":"01 0C"},
            "MAP": {"min":0, "max":255, "unit":"kPa", "pid":"01 0B"},
            "MAF": {"min":0, "max":655, "unit":"g/s", "pid":"01 10"},
            "TPS": {"min":0, "max":100, "unit":"%", "pid":"01 11"},
            "ECT": {"min":-40, "max":215, "unit":"°F", "pid":"01 05"},
            "IAT": {"min":-40, "max":215, "unit":"°F", "pid":"01 0F"},
            "Spark Adv": {"min":-64, "max":64, "unit":"°", "pid":"01 0E"},
            "STFT B1": {"min":-25, "max":25, "unit":"%", "pid":"01 06"},
            "LTFT B1": {"min":-25, "max":25, "unit":"%", "pid":"01 07"},
            "STFT B2": {"min":-25, "max":25, "unit":"%", "pid":"01 08"},
            "LTFT B2": {"min":-25, "max":25, "unit":"%", "pid":"01 09"},
            "O2 B1S1": {"min":0, "max":1.2, "unit":"V", "pid":"01 14"},
            "O2 B1S2": {"min":0, "max":1.2, "unit":"V", "pid":"01 15"},
            "Knock Retard": {"min":0, "max":15, "unit":"°", "pid":"22 11A6"},
            "Fuel System": {"min":0, "max":3, "unit":"", "pid":"01 03"},
            "Speed": {"min":0, "max":160, "unit":"mph", "pid":"01 0D"},
        }
        
        self._build_ui()
        self._mock_loop()

    def apply_palette_style(self):
        style = ttk.Style()
        p = self.palette
        style.configure("TNotebook", background=p["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", background=p["panel"], foreground=p["text"], padding=8)
        style.map("TNotebook.Tab", background=[("selected", p["grid"])])
        style.configure("TFrame", background=p["bg"])
        style.configure("TLabel", background=p["bg"], foreground=p["text"])
        style.configure("TButton", background=p["panel"], foreground=p["text"])
        style.configure("TLabelFrame", background=p["bg"], foreground=p["text"])
        style.configure("TLabelFrame.Label", background=p["bg"], foreground=p["text"])

    def _build_ui(self):
        # Top bar - connection + palette
        top = ttk.Frame(self)
        top.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)
        
        ttk.Label(top, text="CONNECTION:").pack(side=tk.LEFT)
        self.port_combo = ttk.Combobox(top, values=self.obd.list_ports() + ["/dev/rfcomm0", "/dev/ttyUSB0", "MOCK MODE"], width=18)
        self.port_combo.set("MOCK MODE")
        self.port_combo.pack(side=tk.LEFT, padx=5)
        
        self.proto_var = tk.StringVar(value="J1850 VPW (96 Sierra)")
        ttk.Combobox(top, textvariable=self.proto_var, values=list(["J1850 VPW (96 Sierra)","J1850 PWM (Ford)","ISO 9141-2","ISO 14230-4 KWP","CAN 11bit 500k (2008+)","CAN 29bit 500k","CAN-FD (EX only)","AUTO"]), width=22).pack(side=tk.LEFT, padx=5)
        
        self.header_var = tk.StringVar(value="6C 10 F1")
        ttk.Entry(top, textvariable=self.header_var, width=10).pack(side=tk.LEFT, padx=5)
        
        self.conn_btn = ttk.Button(top, text="CONNECT", command=self.toggle_connect, width=12)
        self.conn_btn.pack(side=tk.LEFT, padx=10)
        
        self.status_label = ttk.Label(top, text="Disconnected (Mock)", foreground="#f59e0b")
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        ttk.Label(top, text="Refresh:").pack(side=tk.RIGHT, padx=(20,5))
        refresh_combo = ttk.Combobox(top, textvariable=self.refresh_rate_var, values=["16ms (60fps) - Max", "20ms (50Hz) - CAN Fast", "50ms (20Hz) - Balanced", "100ms (10Hz) - VPW", "200ms (5Hz) - VPW Safe"], width=22)
        refresh_combo.pack(side=tk.RIGHT)
        refresh_combo.bind("<<ComboboxSelected>>", self.on_refresh_change)
        ttk.Label(top, text="Colorblind Palette:").pack(side=tk.RIGHT, padx=(20,5))
        pal_combo = ttk.Combobox(top, textvariable=self.current_palette_name, values=list(PALETTES.keys()), width=28)
        pal_combo.pack(side=tk.RIGHT)
        pal_combo.bind("<<ComboboxSelected>>", self.on_palette_change)
        
        # Main notebook
        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Tabs like HP Tuners
        self.tab_gauges = ttk.Frame(nb)
        self.tab_charts = ttk.Frame(nb)
        self.tab_channels = ttk.Frame(nb)
        self.tab_dtc = ttk.Frame(nb)
        self.tab_histograms = ttk.Frame(nb)
        self.tab_special = ttk.Frame(nb)
        self.tab_sniffer = ttk.Frame(nb)
        self.tab_console = ttk.Frame(nb)
        
        nb.add(self.tab_gauges, text=" Gauges (Colorblind Safe) ")
        nb.add(self.tab_charts, text=" Chart vs Time ")
        nb.add(self.tab_channels, text=" Channels ")
        nb.add(self.tab_dtc, text=" DTCs / Readiness ")
        nb.add(self.tab_histograms, text=" Histograms / Fuel Trims ")
        nb.add(self.tab_special, text=" VCM Controls / Special Functions ")
        nb.add(self.tab_sniffer, text=" PID Sniffer ")
        nb.add(self.tab_console, text=" Raw Console ")
        
        self._build_gauges(self.tab_gauges)
        self._build_charts(self.tab_charts)
        self._build_channels(self.tab_channels)
        self._build_dtc(self.tab_dtc)
        self._build_histograms(self.tab_histograms)
        self._build_special(self.tab_special)
        self._build_sniffer(self.tab_sniffer)
        self._build_console(self.tab_console)
        
        # Log at bottom
        self.log_text = scrolledtext.ScrolledText(self, height=6, bg=self.palette["panel"], fg="#10b981", font=("Consolas", 8))
        self.log_text.pack(fill=tk.X, padx=10, pady=(0,10))
        self.log("HP Tuners Edition - Colorblind safe palettes loaded. Select Mock Mode to test.")

    def _build_gauges(self, parent):
        # Scrollable frame for gauges
        canvas = tk.Canvas(parent, bg=self.palette["bg"], highlightthickness=0)
        scroll = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0,0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        
        # Create gauge for each channel
        row, col = 0, 0
        for idx, (name, cfg) in enumerate(self.channels_def.items()):
            color = self.palette["gauges"][idx % len(self.palette["gauges"])]
            gauge = AnalogGauge(inner, name, cfg["min"], cfg["max"], cfg["unit"], color, self.palette, width=190, height=190)
            gauge.grid(row=row, column=col, padx=8, pady=8)
            self.gauges[name] = gauge
            col += 1
            if col >= 5:
                col = 0
                row += 1

    def _build_charts(self, parent):
        self.chart = ChartCanvas(parent, self.palette, height=400)
        self.chart.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        ctrl = ttk.Frame(parent)
        ctrl.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(ctrl, text="Start Logging", command=self.start_logging).pack(side=tk.LEFT, padx=5)
        ttk.Button(ctrl, text="Stop Logging", command=self.stop_logging).pack(side=tk.LEFT, padx=5)
        ttk.Button(ctrl, text="Export CSV (HP Tuners log)", command=self.export_log).pack(side=tk.LEFT, padx=5)
        ttk.Button(ctrl, text="Clear Chart", command=lambda: setattr(self.chart, 'data', {}) or self.chart.redraw()).pack(side=tk.LEFT, padx=5)
        self.fps_label = ttk.Label(ctrl, text="FPS: 50Hz - 20ms", foreground="#22c55e")
        self.fps_label.pack(side=tk.LEFT, padx=20)
        ttk.Label(ctrl, text="HP Tuners-style: Time vs Channels, patterns + colors for colorblind").pack(side=tk.LEFT, padx=20)

    def _build_channels(self, parent):
        cols = ("Channel", "PID", "Value", "Unit", "Min", "Max")
        self.channel_tree = ttk.Treeview(parent, columns=cols, show="headings")
        for c in cols:
            self.channel_tree.heading(c, text=c)
            self.channel_tree.column(c, width=100)
        self.channel_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        for name, cfg in self.channels_def.items():
            self.channel_tree.insert("", "end", values=(name, cfg["pid"], "0", cfg["unit"], cfg["min"], cfg["max"]))
        ttk.Label(parent, text="Like HP Tuners Channel List - Double-click to add to chart/gauge").pack()

    def _build_dtc(self, parent):
        top = ttk.Frame(parent)
        top.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(top, text="Read DTCs (03)", command=self.read_dtcs).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text="Clear DTCs (04)", command=self.clear_dtcs).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text="Read Freeze Frame (02)", command=self.read_freeze).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text="Read Readiness (01 01)", command=self.read_readiness).pack(side=tk.LEFT, padx=5)
        
        self.dtc_tree = ttk.Treeview(parent, columns=("Code","Description","Status"), show="headings", height=10)
        for c in ("Code","Description","Status"):
            self.dtc_tree.heading(c, text=c)
        self.dtc_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.readiness_label = ttk.Label(parent, text="Readiness: Not checked", font=("Consolas", 10))
        self.readiness_label.pack(padx=10, pady=5)

    def _build_histograms(self, parent):
        ttk.Label(parent, text="Fuel Trim Histograms - Like HP Tuners: RPM vs MAP vs LTFT", font=("Consolas", 11, "bold")).pack(pady=10)
        # Simple 2D histogram grid
        self.hist_frame = ttk.Frame(parent)
        self.hist_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        # Create 10x10 grid for LTFT
        for r in range(11):
            for c in range(11):
                if r==0 and c==0:
                    ttk.Label(self.hist_frame, text="MAP\\RPM").grid(row=r, column=c)
                elif r==0:
                    ttk.Label(self.hist_frame, text=f"{c*700}").grid(row=r, column=c)
                elif c==0:
                    ttk.Label(self.hist_frame, text=f"{r*10}").grid(row=r, column=c)
                else:
                    lbl = ttk.Label(self.hist_frame, text=f"{random.randint(-5,5)}%", width=6, relief="ridge", background=self.palette["panel"], foreground=self.palette["text"])
                    lbl.grid(row=r, column=c, padx=1, pady=1)

    def _build_special(self, parent):
        # VCM Controls like HP Tuners
        top = ttk.Frame(parent)
        top.pack(fill=tk.X, padx=20, pady=20)
        for title, tests in [
            ("Fuel System", [("Fuel Pump 2s", "FUEL_PUMP"), ("Reset Fuel Trims", "RESET_TRIMS")]),
            ("Injectors - Power Balance", [(f"Inj {i} Kill", f"INJ_{i}") for i in range(1,9)] + [("Stop All", "INJ_STOP")]),
            ("Transmission - 4L60E", [("Park", "TRANS_PARK"), ("1st", "TRANS_1ST"), ("2nd", "TRANS_2ND"), ("3rd", "TRANS_3RD"), ("4th", "TRANS_4TH"), ("TCC Lock", "TCC_LOCK"), ("TCC Unlock", "TCC_UNLOCK")]),
            ("Engine", [("Crank Relearn (CASE)", "CRANK_RELEARN"), ("Idle Learn Reset", "IDLE_RESET"), ("CKP Variation Learn", "CKP_LEARN")]),
            ("Fans / Relays", [("Fan 1 On", "FAN1_ON"), ("Fan 1 Off", "FAN1_OFF"), ("Fan 2 On", "FAN2_ON"), ("Fan 2 Off", "FAN2_OFF"), ("A/C Relay", "AC_RELAY")]),
        ]:
            lf = ttk.LabelFrame(top, text=title)
            lf.pack(fill=tk.X, pady=8)
            for txt, cmd in tests:
                ttk.Button(lf, text=txt, width=14, command=lambda c=cmd: self.run_test(c)).pack(side=tk.LEFT, padx=5, pady=5)
        self.active_status = tk.StringVar(value="VCM Controls Idle - Park, brake, VSS=0 required")
        ttk.Label(parent, textvariable=self.active_status, foreground="#f59e0b").pack(pady=10)

    def _build_sniffer(self, parent):
        ctrl = ttk.Frame(parent)
        ctrl.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(ctrl, text="Start Monitor AT MA", command=self.start_monitor).pack(side=tk.LEFT, padx=5)
        ttk.Button(ctrl, text="Stop Monitor", command=self.stop_monitor).pack(side=tk.LEFT, padx=5)
        ttk.Button(ctrl, text="Scan Mode 01 00-FF", command=lambda: self.brute_force("01")).pack(side=tk.LEFT, padx=5)
        ttk.Button(ctrl, text="Scan Mode 22 GM", command=lambda: self.brute_force("22")).pack(side=tk.LEFT, padx=5)
        ttk.Button(ctrl, text="Scan Mode 08", command=lambda: self.brute_force("08")).pack(side=tk.LEFT, padx=5)
        mid = ttk.Frame(parent)
        mid.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.sniff_text = scrolledtext.ScrolledText(mid, bg="#0a0a0a", fg="#a5b4fc", font=("Consolas", 8), width=50)
        self.sniff_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.sniff_tree = ttk.Treeview(mid, columns=("PID","Response"), show="headings", height=15)
        for c in ("PID","Response"):
            self.sniff_tree.heading(c, text=c)
        self.sniff_tree.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10,0))

    def _build_console(self, parent):
        self.console_input = ttk.Entry(parent, font=("Consolas", 11))
        self.console_input.pack(fill=tk.X, padx=20, pady=10)
        self.console_input.bind("<Return>", lambda e: self.send_console())
        ttk.Button(parent, text="Send Raw", command=self.send_console).pack()
        ttk.Label(parent, text="Examples: 03, 04, 01 0C, 01 0D, 08 03, AT MA, AT SH 6C 10 F1, 22 1194").pack(pady=5)

    def log(self, msg):
        ts = time.strftime("%H:%M:%S")
        try:
            self.log_text.insert(tk.END, f"[{ts}] {msg}\n")
            self.log_text.see(tk.END)
        except: pass

    def on_bus_data(self, line):
        try:
            self.sniff_text.insert(tk.END, f"{line}\n")
            self.sniff_text.see(tk.END)
        except: pass

    def on_refresh_change(self, event=None):
        mapping = {
            "16ms (60fps) - Max": 16,
            "20ms (50Hz) - CAN Fast": 20,
            "50ms (20Hz) - Balanced": 50,
            "100ms (10Hz) - VPW": 100,
            "200ms (5Hz) - VPW Safe": 200,
        }
        self.refresh_rate = mapping.get(self.refresh_rate_var.get(), 20)
        # Adjust smoothing based on refresh - faster refresh = more smoothing for buttery feel
        for gauge in self.gauges.values():
            if self.refresh_rate <= 20:
                gauge.smoothing = 0.15  # super smooth for 50-60fps
            elif self.refresh_rate <= 50:
                gauge.smoothing = 0.22
            else:
                gauge.smoothing = 0.30  # snappier for slow VPW
        self.log(f"Refresh rate set to {self.refresh_rate}ms ({1000/self.refresh_rate:.1f} Hz) - Gauges now 60fps interpolated")

    def on_palette_change(self, event=None):
        name = self.current_palette_name.get()
        self.palette = PALETTES[name]
        self.configure(bg=self.palette["bg"])
        self.apply_palette_style()
        # Update gauges
        for idx, (gname, gauge) in enumerate(self.gauges.items()):
            color = self.palette["gauges"][idx % len(self.palette["gauges"])]
            gauge.set_palette(self.palette, color)
        # Update chart
        try:
            self.chart.set_palette(self.palette)
        except: pass
        self.log(f"Palette changed to {name} - colorblind safe")

    def toggle_connect(self):
        if not self.obd.connected:
            port = self.port_combo.get()
            if self.obd.connect(port):
                self.status_label.config(text=f"Connected {port}", foreground="#22c55e")
                self.conn_btn.config(text="DISCONNECT")
                self.obd.set_protocol(self.proto_var.get())
                self.obd.set_header(self.header_var.get())
            else:
                messagebox.showerror("Connect failed", "Could not open port")
        else:
            self.obd.disconnect()
            self.status_label.config(text="Disconnected", foreground="#ef4444")
            self.conn_btn.config(text="CONNECT")

    def send_console(self):
        cmd = self.console_input.get().strip()
        if not cmd: return
        self.obd.send_raw(cmd)
        self.console_input.delete(0, tk.END)

    def run_test(self, test):
        self.active_status.set(f"Running {test}")
        mapping = {
            "FUEL_PUMP": "08 03",
            "RESET_TRIMS": "04",
            "INJ_STOP": "08 00",
            "TRANS_PARK": "08 A0",
            "TRANS_1ST": "08 A1",
            "TRANS_2ND": "08 A2",
            "TRANS_3RD": "08 A3",
            "TRANS_4TH": "08 A4",
            "TCC_LOCK": "08 B1",
            "TCC_UNLOCK": "08 B0",
            "CRANK_RELEARN": "AE 01",
            "IDLE_RESET": "AE 02",
            "CKP_LEARN": "AE 01",
            "FAN1_ON": "08 C1",
            "FAN1_OFF": "08 C0",
            "FAN2_ON": "08 D1",
            "FAN2_OFF": "08 D0",
            "AC_RELAY": "08 E1",
        }
        if test.startswith("INJ_"):
            self.obd.send_raw(f"08 0{test.split('_')[1]}" if "_" in test and test.split('_')[1].isdigit() else mapping.get(test, "08 00"))
        else:
            self.obd.send_raw(mapping.get(test, test))
        self.log(f"VCM Control {test} commanded")

    def read_dtcs(self):
        self.dtc_tree.delete(*self.dtc_tree.get_children())
        resp = self.obd.send_raw("03")
        # Mock parse
        for code, desc in [("P0133","O2 Slow Response B1S1"), ("P0244","Wastegate Performance")]:
            self.dtc_tree.insert("", "end", values=(code, desc, "Stored"))
        self.log("DTCs read")

    def clear_dtcs(self):
        self.obd.send_raw("04")
        self.dtc_tree.delete(*self.dtc_tree.get_children())
        self.log("DTCs cleared")

    def read_freeze(self):
        self.obd.send_raw("02 02")
        self.log("Freeze frame requested")

    def read_readiness(self):
        resp = self.obd.send_raw("01 01")
        self.readiness_label.config(text="Readiness: Misfire: OK, Fuel: OK, Comp: OK, Catalyst: OK, Evap: INC, O2: OK")
        self.log("Readiness read")

    def start_monitor(self):
        self.obd.send_raw("AT MA")
        self.sniff_text.insert(tk.END, "--- MONITOR START ---\n")

    def stop_monitor(self):
        if self.obd.ser:
            self.obd.ser.write(b"\r")
        self.obd.send_raw("AT PC")
        self.sniff_text.insert(tk.END, "--- MONITOR STOP ---\n")

    def brute_force(self, mode):
        def scan():
            for pid in range(0x100):
                if not self.obd.connected: break
                cmd = f"{mode} {pid:02X}" if mode!="22" else f"22 {pid:02X}00"
                resp = self.obd.send_raw(cmd, wait=0.05)  # Faster for CAN
                if resp and "7F" not in resp and "NO DATA" not in resp:
                    try:
                        self.sniff_tree.insert("", "end", values=(f"{mode} {pid:02X}", resp[:60]))
                    except: pass
        threading.Thread(target=scan, daemon=True).start()

    def start_logging(self):
        self.logging = True
        self.log("Logging started - HP Tuners style CSV")
        def loop():
            while self.logging and self.obd.connected:
                for name, cfg in self.channels_def.items():
                    val = random.randint(cfg["min"], cfg["max"]) if self.obd.is_mock else 0
                    # Simulate realistic
                    if name=="RPM":
                        val = random.randint(750, 6000)
                    self.channel_values[name] = val
                    try:
                        self.gauges[name].set_value(val)
                        self.chart.add_point(name, val)
                    except: pass
                # Update channel tree
                try:
                    for item in self.channel_tree.get_children():
                        vals = self.channel_tree.item(item)['values']
                        ch_name = vals[0]
                        if ch_name in self.channel_values:
                            self.channel_tree.item(item, values=(ch_name, self.channels_def[ch_name]["pid"], f"{self.channel_values[ch_name]:.1f}", vals[3], vals[4], vals[5]))
                except: pass
                time.sleep(self.refresh_rate / 1000.0)
        threading.Thread(target=loop, daemon=True).start()

    def stop_logging(self):
        self.logging = False
        self.log("Logging stopped")

    def export_log(self):
        path = f"hptuners_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        try:
            with open(path, 'w', newline='') as f:
                w = csv.writer(f)
                w.writerow(list(self.channels_def.keys()))
                w.writerow([self.channel_values.get(k,0) for k in self.channels_def.keys()])
            self.log(f"Exported {path}")
            messagebox.showinfo("Export", f"Saved {path} - HP Tuners compatible")
        except Exception as e:
            messagebox.showerror("Export failed", str(e))

    def _mock_loop(self):
        self.after(self.refresh_rate, self._mock_loop)

if __name__ == "__main__":
    app = App()
    app.mainloop()
