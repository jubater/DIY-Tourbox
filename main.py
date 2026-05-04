import serial
import serial.tools.list_ports
import customtkinter as ctk
import tkinter.filedialog as filedialog
from pynput.mouse import Controller as MouseController
from pynput.keyboard import Controller, Key
import json
import os
import sys
from tkinter import messagebox
from PIL import Image
import pystray
from pystray import MenuItem as item
import threading


try:
    import win32gui
    import win32process
    import psutil
    AUTO_SWITCH_AVAILABLE = True
except ImportError:
    AUTO_SWITCH_AVAILABLE = False


BAUD_RATE = 115200
keyboard = Controller()
mouse = MouseController()

if getattr(sys, 'frozen', False):
    base_path = os.path.dirname(sys.executable)
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

PROFILES_DIR = os.path.join(base_path, "profiles")
if not os.path.exists(PROFILES_DIR): os.makedirs(PROFILES_DIR)

CUSTOM_ACTIONS_FILE = os.path.join(PROFILES_DIR, "custom_actions.json")


arduino = None
last_active_app = None
current_app_profile = "default" 

held_layer_keys = set()        
smart_mods_used = set()        
active_held_actions = {}       


CATEGORIZED_ACTIONS = {
    "System & Nav": {
        "Copy [Ctrl+C]": [Key.ctrl, 'c'], "Paste [Ctrl+V]": [Key.ctrl, 'v'], "Cut [Ctrl+X]": [Key.ctrl, 'x'],
        "Undo [Ctrl+Z]": [Key.ctrl, 'z'], "Redo [Ctrl+Shift+Z]": [Key.ctrl, Key.shift, 'z'],
        "Save [Ctrl+S]": [Key.ctrl, 's'], "Select All [Ctrl+A]": [Key.ctrl, 'a'],
        "Up Arrow": [Key.up], "Down Arrow": [Key.down], "Left Arrow": [Key.left], "Right Arrow": [Key.right],
        "Enter": [Key.enter], "Spacebar": [Key.space], "Escape": [Key.esc], "Backspace": [Key.backspace]
    },
    "Modifiers": { "Ctrl": [Key.ctrl], "Shift": [Key.shift], "Alt": [Key.alt] },
    "Photoshop": {
        "Brush [B]": ['b'], "Eraser [E]": ['e'], "Eyedropper [I]": ['i'], "Move [V]": ['v'],
        "Lasso [L]": ['l'], "Pen Tool [P]": ['p'], "Text Tool [T]": ['t'], "Magic Wand [W]": ['w'],
        "Transform [Ctrl+T]": [Key.ctrl, 't'], "New Layer [Ctrl+Shift+N]": [Key.ctrl, Key.shift, 'n'],
        "Deselect [Ctrl+D]": [Key.ctrl, 'd'], "Brush Size Down [ [ ]": ['['], "Brush Size Up [ ] ]": [']'],
        "Zoom In [Ctrl++]": [Key.ctrl, '+'], "Zoom Out [Ctrl+-]": [Key.ctrl, '-']
    },
    "Video Editing": {
        "Play/Pause [Space]": [Key.space], "Razor Tool [C]": ['c'], "Selection Tool [V]": ['v'],
        "Ripple Delete [Shift+Del]": [Key.shift, Key.delete], "Add Edit/Cut [Ctrl+K]": [Key.ctrl, 'k']
    },
    "Media Controls": {
        "Media Play/Pause": [Key.media_play_pause], "Media Next": [Key.media_next], "Media Prev": [Key.media_previous],
        "Volume Up": [Key.media_volume_up], "Volume Down": [Key.media_volume_down], "Mute": [Key.media_volume_mute], 
        "Stop": [Key.media_stop], "Fast Forward": [Key.ctrl, Key.media_next]
    },
    "Mouse Tools": {
        "Mouse Scroll Up": [], 
        "Mouse Scroll Down": []
    },
    "Custom User": {}
}

KEY_MAP = {
    'ctrl': Key.ctrl, 'lctrl': Key.ctrl_l, 'rctrl': Key.ctrl_r,
    'shift': Key.shift, 'lshift': Key.shift_l, 'rshift': Key.shift_r,
    'alt': Key.alt, 'lalt': Key.alt_l, 'ralt': Key.alt_r,
    'cmd': Key.cmd, 'win': Key.cmd, 'space': Key.space, 'enter': Key.enter, 
    'esc': Key.esc, 'tab': Key.tab, 'up': Key.up, 'down': Key.down, 
    'left': Key.left, 'right': Key.right, 'backspace': Key.backspace, 'delete': Key.delete,
    'insert': Key.insert, 'home': Key.home, 'end': Key.end, 'pageup': Key.page_up, 'pagedown': Key.page_down
}
for i in range(1, 25): KEY_MAP[f'f{i}'] = getattr(Key, f'f{i}', None)

def parse_shortcut_string(s):
    parts = s.lower().split('+')
    keys = []
    for p in parts:
        p = p.strip()
        if p in KEY_MAP and KEY_MAP[p]: keys.append(KEY_MAP[p])
        elif len(p) == 1: keys.append(p)
    return keys

if os.path.exists(CUSTOM_ACTIONS_FILE):
    try:
        with open(CUSTOM_ACTIONS_FILE, "r") as f: 
            saved = json.load(f)
            for name, key_str in saved.items():
                parsed = parse_shortcut_string(key_str)
                if parsed: CATEGORIZED_ACTIONS["Custom User"][name] = parsed
    except Exception: pass

ACTIONS = {"None": []}
for cat, items in CATEGORIZED_ACTIONS.items(): ACTIONS.update(items)

INPUTS = [f"B{i}" for i in range(1, 13)] + ["E1R", "E1L", "E1C", "E2R", "E2L", "E2C", "E3R", "E3L", "E3C"]
PIN_LABELS = {f"B{i}": f"Button {i}" for i in range(1, 13)}
PIN_LABELS.update({
    "E1R": "Enc 1 Right", "E1L": "Enc 1 Left", "E1C": "Enc 1 Click",
    "E2R": "Enc 2 Right", "E2L": "Enc 2 Left", "E2C": "Enc 2 Click",
    "E3R": "Enc 3 Right", "E3L": "Enc 3 Left", "E3C": "Enc 3 Click"
})

current_mapping = {inp: {"role": "Button", "norm": "None", "mod1": "None", "mod2": "None", "mod3": "None"} for inp in INPUTS}
if not os.path.exists(os.path.join(PROFILES_DIR, "default.json")):
    with open(os.path.join(PROFILES_DIR, "default.json"), "w") as f: json.dump(current_mapping, f)

def get_open_apps():
    apps = set()
    if not AUTO_SWITCH_AVAILABLE: return list(apps)
    def callback(hwnd, extra):
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                name = psutil.Process(pid).name().lower()
                if name not in ['explorer.exe', 'applicationframehost.exe', 'textinputhost.exe']: apps.add(name)
            except Exception: pass 
    try: win32gui.EnumWindows(callback, None)
    except Exception: pass
    return sorted(list(apps))


app = ctk.CTk(); app.title("Not TourBox v1"); app.geometry("1150x850")
ctk.set_appearance_mode("dark"); app.configure(fg_color="#2b2b2b") 

auto_switch_enabled = ctk.BooleanVar(value=False)


def withdraw_window():
    app.withdraw()

def show_window():
    app.deiconify()

def quit_window(icon, item):
    icon.stop()
    app.destroy()
    sys.exit()

icon_image = Image.new('RGB', (64, 64), color=(31, 113, 169))
tray_icon = pystray.Icon("NotTourBox", icon_image, "NotTourBox", menu=pystray.Menu(
    item('Show Dashboard', show_window, default=True),
    item('Exit Fully', quit_window)
))

def run_tray():
    tray_icon.run()

app.protocol('WM_DELETE_WINDOW', withdraw_window)


header = ctk.CTkFrame(app, fg_color="#1a1a1a", height=45, corner_radius=0); header.pack(fill="x")
header_status_label = ctk.CTkLabel(header, text="HARDWARE: DISCONNECTED", text_color="#f87171", font=("Arial", 11, "bold")); header_status_label.pack(side="left", padx=25)
editing_status_label = ctk.CTkLabel(header, text="Editing: default", text_color="#4ade80", font=("Arial", 12, "bold")); editing_status_label.pack(side="right", padx=25)

body_frame = ctk.CTkFrame(app, fg_color="transparent"); body_frame.pack(fill="both", expand=True, padx=15, pady=15)
global_sidebar = ctk.CTkFrame(body_frame, width=220, fg_color="#1e1e1e", corner_radius=10); global_sidebar.pack(side="left", fill="y", padx=(0, 15)); global_sidebar.pack_propagate(False)

ctk.CTkLabel(global_sidebar, text="APPLICATIONS", font=("Arial", 14, "bold"), text_color="#3b77a3").pack(pady=(20, 10))
if AUTO_SWITCH_AVAILABLE:
    ctk.CTkSwitch(global_sidebar, text="Auto-Switch Profiles", variable=auto_switch_enabled, onvalue=True, offvalue=False, font=("Arial", 11)).pack(pady=(0, 10))

app_list_scroll = ctk.CTkScrollableFrame(global_sidebar, fg_color="#141414", corner_radius=5); app_list_scroll.pack(fill="both", expand=True, padx=10, pady=5)
app_list_buttons = {}

def get_app_profiles():
    return [f.replace('.json', '') for f in os.listdir(PROFILES_DIR) if f.endswith(".json") and f not in ["custom_actions.json", "links.json"]]

def load_app_profile(app_name):
    global current_mapping, current_app_profile
    filepath = os.path.join(PROFILES_DIR, f"{app_name}.json")
    current_mapping = {inp: {"role": "Button", "norm": "None", "mod1": "None", "mod2": "None", "mod3": "None"} for inp in INPUTS}
    if os.path.exists(filepath):
        with open(filepath, "r") as f: current_mapping.update(json.load(f))
    current_app_profile = app_name
    editing_status_label.configure(text=f"Editing: {app_name}")
    highlight_active_app()
    for inp in INPUTS:
        if inp in ui_vars:
            ui_vars[inp]["role"].set(current_mapping[inp].get("role", "Button"))
            ui_vars[inp]["norm"].set(current_mapping[inp].get("norm", "None"))
            ui_vars[inp]["mod1"].set(current_mapping[inp].get("mod1", "None"))
            ui_vars[inp]["mod2"].set(current_mapping[inp].get("mod2", "None"))
            ui_vars[inp]["mod3"].set(current_mapping[inp].get("mod3", "None"))
    log_action(f"SYSTEM: Switched UI to '{app_name}'")

def highlight_active_app():
    for name, btn in app_list_buttons.items():
        if name == current_app_profile: btn.configure(fg_color="#1f71a9", hover_color="#1f71a9")
        else: btn.configure(fg_color="transparent", hover_color="#333")

def refresh_app_list():
    for widget in app_list_scroll.winfo_children(): widget.destroy()
    app_list_buttons.clear()
    for app_name in get_app_profiles():
        btn = ctk.CTkButton(app_list_scroll, text=f"  {app_name}", anchor="w", fg_color="transparent", text_color="#fff", height=35, command=lambda a=app_name: load_app_profile(a))
        btn.pack(fill="x", pady=2); app_list_buttons[app_name] = btn
    highlight_active_app()

class AppLinkerWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master); self.title("Add Application"); self.geometry("450x600")
        self.attributes("-topmost", True); self.grab_set()
        self.selected_app = ctk.StringVar(value="None Selected"); self.app_buttons = []
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent"); bottom_frame.pack(side="bottom", fill="x", pady=20)
        ctk.CTkLabel(bottom_frame, textvariable=self.selected_app, text_color="#4ade80", font=("Arial", 12, "bold")).pack(side="left", padx=20)
        ctk.CTkButton(bottom_frame, text="Add Profile", fg_color="#4ade80", text_color="#000", font=("Arial", 12, "bold"), command=self.confirm, width=120).pack(side="right", padx=20)
        self.template_var = ctk.StringVar(value="Clean (Empty)")
        template_frame = ctk.CTkFrame(self, fg_color="transparent"); template_frame.pack(side="bottom", fill="x", padx=20, pady=(0, 10))
        ctk.CTkLabel(template_frame, text="Base Profile:", font=("Arial", 12, "bold"), text_color="#7a7a7a").pack(side="left")
        templates = ["Clean (Empty)"] + get_app_profiles()
        ctk.CTkOptionMenu(template_frame, variable=self.template_var, values=templates, fg_color="#333").pack(side="right", fill="x", expand=True, padx=(10, 0))
        ctk.CTkLabel(self, text="Select Application", font=("Arial", 16, "bold"), text_color="#3b77a3").pack(pady=15)
        ctk.CTkButton(self, text="Browse .exe...", fg_color="#333", command=self.browse_app).pack()
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="#1e1e1e"); self.scroll.pack(fill="both", expand=True, padx=20, pady=10)
        for app_name in get_open_apps():
            btn = ctk.CTkButton(self.scroll, text=app_name, anchor="w", fg_color="transparent", command=lambda a=app_name: self.select_app(a))
            btn.pack(fill="x", pady=2); self.app_buttons.append((app_name, btn))
    def select_app(self, app_name):
        self.selected_app.set(app_name)
        for name, btn in self.app_buttons: btn.configure(fg_color="#1f71a9" if name == app_name else "transparent")
    def browse_app(self):
        f = filedialog.askopenfilename(filetypes=[("Executables", "*.exe")])
        if f: self.selected_app.set(os.path.basename(f).lower())
    def confirm(self):
        a = self.selected_app.get()
        if a != "None Selected":
            fp = os.path.join(PROFILES_DIR, f"{a}.json")
            if not os.path.exists(fp):
                t_val = self.template_var.get()
                new_map = {inp: {"role": "Button", "norm": "None", "mod1": "None", "mod2": "None", "mod3": "None"} for inp in INPUTS} if t_val == "Clean (Empty)" else json.load(open(os.path.join(PROFILES_DIR, f"{t_val}.json"), "r"))
                with open(fp, "w") as f: json.dump(new_map, f)
            refresh_app_list(); load_app_profile(a)
        self.destroy()

btn_frame = ctk.CTkFrame(global_sidebar, fg_color="transparent"); btn_frame.pack(fill="x", padx=10, pady=(5, 20))
ctk.CTkButton(btn_frame, text="+ Add", width=90, fg_color="#333", command=lambda: AppLinkerWindow(app)).pack(side="left", padx=2)
ctk.CTkButton(btn_frame, text="− Del", width=90, fg_color="#333", hover_color="#a61e1e", command=lambda: [os.remove(os.path.join(PROFILES_DIR, f"{current_app_profile}.json")) if current_app_profile != "default" else None, refresh_app_list(), load_app_profile("default")]).pack(side="right", padx=2)

main_content = ctk.CTkFrame(body_frame, fg_color="transparent"); main_content.pack(side="right", fill="both", expand=True)
tabview = ctk.CTkTabview(main_content, segmented_button_selected_color="#1f71a9", fg_color="transparent"); tabview.pack(fill="both", expand=True); tabview.add("Dashboard"); tabview.add("Buttons"); tabview.add("Encoders")


dash_container = ctk.CTkFrame(tabview.tab("Dashboard"), fg_color="transparent"); dash_container.pack(fill="both", expand=True, pady=10)
hw_card = ctk.CTkFrame(dash_container, fg_color="#1e1e1e", corner_radius=10, height=80); hw_card.pack(fill="x", pady=(0, 20)); hw_card.pack_propagate(False)
hw_inner = ctk.CTkFrame(hw_card, fg_color="transparent"); hw_inner.pack(pady=25)
ctk.CTkLabel(hw_inner, text="HARDWARE PORT:", font=("Arial", 12, "bold"), text_color="#7a7a7a").pack(side="left", padx=15)
port_var = ctk.StringVar(value="Scan needed..."); port_dropdown = ctk.CTkOptionMenu(hw_inner, variable=port_var, values=["Scan needed..."], fg_color="#1f71a9", button_color="#185a87", width=250); port_dropdown.pack(side="left", padx=10)

def scan_ports():
    ports = serial.tools.list_ports.comports()
    dl = [f"{p.device} - {p.description}" for p in ports] if ports else ["No devices"]
    port_dropdown.configure(values=dl); port_var.set(dl[0])

ctk.CTkButton(hw_inner, text="⟳", width=40, font=("Arial", 16), fg_color="#333", command=scan_ports).pack(side="left", padx=10)

def toggle_connection():
    global arduino
    if arduino and arduino.is_open:
        arduino.close(); arduino = None; connect_btn.configure(text="⚡ Connect", fg_color="#1f71a9"); header_status_label.configure(text="HARDWARE: DISCONNECTED", text_color="#f87171")
    else:
        try: arduino = serial.Serial(port_var.get().split(" - ")[0], BAUD_RATE, timeout=0.1); connect_btn.configure(text="❌ Disconnect", fg_color="#c92a2a"); header_status_label.configure(text="CONNECTED", text_color="#4ade80")
        except: pass

connect_btn = ctk.CTkButton(hw_inner, text="⚡ Connect", width=120, fg_color="#1f71a9", command=toggle_connection); connect_btn.pack(side="left", padx=10)
log_split = ctk.CTkFrame(dash_container, fg_color="transparent"); log_split.pack(fill="both", expand=True)
raw_box = ctk.CTkTextbox(log_split, fg_color="#1e1e1e", font=("Consolas", 11)); raw_box.pack(side="left", fill="both", expand=True, padx=(0, 10))
action_box = ctk.CTkTextbox(log_split, fg_color="#1e1e1e", font=("Consolas", 12)); action_box.pack(side="right", fill="both", expand=True)

def log_raw(t): raw_box.configure(state="normal"); raw_box.insert("end", f"› {t}\n"); raw_box.see("end"); raw_box.configure(state="disabled")
def log_action(t): action_box.configure(state="normal"); action_box.insert("end", f"▶ {t}\n"); action_box.see("end"); action_box.configure(state="disabled")


class VisualKeyPicker(ctk.CTkToplevel):
    def __init__(self, master, target_entry):
        super().__init__(master); self.title("Keyboard Keys"); self.geometry("500x550"); self.attributes("-topmost", True); self.grab_set(); self.target_entry = target_entry
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent"); scroll.pack(fill="both", expand=True, padx=10, pady=10)
        LAYOUT = {"Modifiers": ["lctrl", "rctrl", "lalt", "ralt", "lshift", "rshift", "win", "cmd"], "System": ["enter", "space", "tab", "backspace", "delete", "esc", "insert"], "Nav": ["up", "down", "left", "right", "home", "end", "pageup", "pagedown"], "Function Keys": [f"f{i}" for i in range(1, 25)], "Alpha": [chr(i) for i in range(97, 123)] + [str(i) for i in range(10)]}
        for cat, keys in LAYOUT.items():
            ctk.CTkLabel(scroll, text=cat, font=("Arial", 12, "bold")).pack(anchor="w", pady=(10, 5))
            f = ctk.CTkFrame(scroll, fg_color="transparent"); f.pack(fill="x")
            c, r = 0, 0
            for k in keys:
                ctk.CTkButton(f, text=k, width=60, command=lambda x=k: [self.target_entry.insert("end", "+" if self.target_entry.get().strip() and not self.target_entry.get().strip().endswith("+") else ""), self.target_entry.insert("end", x), self.destroy()]).grid(row=r, column=c, padx=2, pady=2)
                c += 1
                if c > 6: c, r = 0, r + 1

class AddShortcutWindow(ctk.CTkToplevel):
    def __init__(self, master, picker_instance):
        super().__init__(master); self.title("Add Shortcut"); self.geometry("420x350"); self.attributes("-topmost", True); self.grab_set(); self.picker_instance = picker_instance
        ctk.CTkLabel(self, text="Create Custom Shortcut", font=("Arial", 16, "bold")).pack(pady=15)
        self.name_entry = ctk.CTkEntry(self, width=360, placeholder_text="Name"); self.name_entry.pack(pady=10)
        k_frame = ctk.CTkFrame(self, fg_color="transparent"); k_frame.pack(fill="x", padx=30, pady=10)
        self.key_entry = ctk.CTkEntry(k_frame); self.key_entry.pack(side="left", expand=True, fill="x")
        ctk.CTkButton(k_frame, text="+", width=40, command=lambda: VisualKeyPicker(self, self.key_entry)).pack(side="right", padx=(5, 0))
        ctk.CTkButton(self, text="Save", command=self.save).pack(pady=20)
    def save(self):
        name, keys = self.name_entry.get().strip(), self.key_entry.get().strip()
        if name and keys:
            custom_raw = json.load(open(CUSTOM_ACTIONS_FILE, "r")) if os.path.exists(CUSTOM_ACTIONS_FILE) else {}
            custom_raw[name] = keys; json.dump(custom_raw, open(CUSTOM_ACTIONS_FILE, "w"))
            parsed = parse_shortcut_string(keys); CATEGORIZED_ACTIONS["Custom User"][name] = parsed; ACTIONS[name] = parsed; self.picker_instance.select_category("Custom User"); self.destroy()

class ShortcutPicker(ctk.CTkToplevel):
    def __init__(self, master, target_var):
        super().__init__(master); self.title("Assign"); self.geometry("750x550"); self.target_var = target_var; self.attributes("-topmost", True); self.grab_set() 
        self.sidebar = ctk.CTkFrame(self, width=200, fg_color="#1e1e1e"); self.sidebar.pack(side="left", fill="y"); self.sidebar.pack_propagate(False)
        self.main_area = ctk.CTkFrame(self, fg_color="transparent"); self.main_area.pack(side="right", fill="both", expand=True, padx=20, pady=20)
        self.cat_buttons = {}
        for cat in CATEGORIZED_ACTIONS.keys():
            self.cat_buttons[cat] = ctk.CTkButton(self.sidebar, text=cat, anchor="w", fg_color="transparent", command=lambda c=cat: self.select_category(c))
            self.cat_buttons[cat].pack(fill="x", padx=10, pady=2)
        header_f = ctk.CTkFrame(self.main_area, fg_color="transparent"); header_f.pack(fill="x", pady=(0, 10))
        self.cat_title = ctk.CTkLabel(header_f, text="All Actions", font=("Arial", 18, "bold")); self.cat_title.pack(side="left")
        ctk.CTkButton(header_f, text="+ Custom", width=100, command=lambda: AddShortcutWindow(self, self)).pack(side="right")
        self.search_var = ctk.StringVar(); self.search_var.trace_add("write", lambda *a: self.populate_list([k for k in self.current_category_data if self.search_var.get().lower() in k.lower()]))
        ctk.CTkEntry(self.main_area, textvariable=self.search_var, placeholder_text="Search...").pack(fill="x", pady=(0, 10))
        self.scroll = ctk.CTkScrollableFrame(self.main_area, fg_color="#1a1a1a"); self.scroll.pack(fill="both", expand=True)
        self.current_cat = "All Actions"
        self.action_rows = []; self.current_category_data = list(ACTIONS.keys()); self.populate_list(self.current_category_data)
    
    def select_category(self, cat):
        self.current_cat = cat
        self.cat_title.configure(text=cat); self.current_category_data = list(CATEGORIZED_ACTIONS[cat].keys()); self.current_category_data.insert(0, "None") if "None" not in self.current_category_data else None; self.search_var.set(""); self.populate_list(self.current_category_data)
    
    def delete_shortcut(self, item):
        if messagebox.askyesno("Delete Shortcut", f"Are you sure you want to delete '{item}'?"):
            if item in CATEGORIZED_ACTIONS["Custom User"]:
                del CATEGORIZED_ACTIONS["Custom User"][item]
                if item in ACTIONS: del ACTIONS[item]
                custom_raw = json.load(open(CUSTOM_ACTIONS_FILE, "r")) if os.path.exists(CUSTOM_ACTIONS_FILE) else {}
                if item in custom_raw: del custom_raw[item]
                json.dump(custom_raw, open(CUSTOM_ACTIONS_FILE, "w"))
                self.populate_list(list(CATEGORIZED_ACTIONS["Custom User"].keys()))

    def populate_list(self, items):
        for row in self.action_rows: row.destroy()
        self.action_rows = []
        for item in items:
            row = ctk.CTkFrame(self.scroll, fg_color="transparent"); row.pack(fill="x", pady=1); self.action_rows.append(row)
            btn = ctk.CTkButton(row, text=item, anchor="w", fg_color="transparent", command=lambda i=item: [self.target_var.set(i), self.destroy()])
            btn.pack(side="left", fill="x", expand=True)
            if self.current_cat == "Custom User" and item != "None":
                ctk.CTkButton(row, text="X", width=30, fg_color="#a61e1e", command=lambda i=item: self.delete_shortcut(i)).pack(side="right", padx=5)


ui_vars = {}
W_INP, W_BEH, W_ACT = 100, 120, 140

def create_aligned_header(parent, is_primary=True):
    h_row = ctk.CTkFrame(parent, fg_color="transparent"); h_row.pack(fill="x", pady=(10, 5))
    ctk.CTkLabel(h_row, text="INPUT", width=W_INP, text_color="#7a7a7a", font=("Arial", 10, "bold")).pack(side="left", padx=5)
    ctk.CTkLabel(h_row, text="BEHAVIOR" if is_primary else "", width=W_BEH, text_color="#7a7a7a", font=("Arial", 10, "bold")).pack(side="left", padx=5)
    ctk.CTkLabel(h_row, text="NORMAL ACTION", width=W_ACT, text_color="#7a7a7a", font=("Arial", 10, "bold")).pack(side="left", padx=5)
    ctk.CTkLabel(h_row, text="MOD 1 ACTION", width=W_ACT, text_color="#7a7a7a", font=("Arial", 10, "bold")).pack(side="left", padx=5)
    ctk.CTkLabel(h_row, text="MOD 2 ACTION", width=W_ACT, text_color="#7a7a7a", font=("Arial", 10, "bold")).pack(side="left", padx=5)
    ctk.CTkLabel(h_row, text="MOD 3 ACTION", width=W_ACT, text_color="#7a7a7a", font=("Arial", 10, "bold")).pack(side="left", padx=5)

def create_row(parent, inp, is_btn=True):
    row = ctk.CTkFrame(parent, fg_color="transparent"); row.pack(pady=4, fill="x")
    u = {"role": ctk.StringVar(value=current_mapping[inp].get("role", "Button")), "norm": ctk.StringVar(value=current_mapping[inp].get("norm", "None")), "mod1": ctk.StringVar(value=current_mapping[inp].get("mod1", "None")), "mod2": ctk.StringVar(value=current_mapping[inp].get("mod2", "None")), "mod3": ctk.StringVar(value=current_mapping[inp].get("mod3", "None"))}
    ui_vars[inp] = u
    ctk.CTkLabel(row, text=PIN_LABELS.get(inp, inp), width=W_INP).pack(side="left", padx=5)
    if is_btn: ctk.CTkOptionMenu(row, variable=u["role"], values=["Button", "Mod 1", "Mod 2", "Mod 3", "Smart Mod 1", "Smart Mod 2", "Smart Mod 3"], width=120).pack(side="left", padx=5)
    else: ctk.CTkLabel(row, text="Encoder", width=120).pack(side="left", padx=5)
    for k in ["norm", "mod1", "mod2", "mod3"]:
        btn = ctk.CTkButton(row, textvariable=u[k], width=W_ACT, fg_color="#1f71a9" if k == "norm" else "#1e1e1e", command=lambda x=u[k]: ShortcutPicker(app, x))
        btn.pack(side="left", padx=5)

for tab in ["Buttons", "Encoders"]:
    s = ctk.CTkScrollableFrame(tabview.tab(tab)); s.pack(fill="both", expand=True)
    create_aligned_header(s, tab=="Buttons")
    if tab == "Buttons": [create_row(s, f"B{i}") for i in range(1, 13)]
    else: [create_row(s, e, False) for e in ["E1R", "E1L", "E1C", "E2R", "E2L", "E2C", "E3R", "E3L", "E3C"]]
    ctk.CTkButton(tabview.tab(tab), text="SAVE PRESET", command=lambda: json.dump({inp: {k: ui_vars[inp][k].get() for k in ui_vars[inp]} for inp in INPUTS}, open(os.path.join(PROFILES_DIR, f"{current_app_profile}.json"), "w")) or log_action("SYSTEM: Saved."), height=50, fg_color="#1f71a9").pack(pady=20)

refresh_app_list(); load_app_profile("default"); scan_ports()


def auto_switch_loop():
    global last_active_app
    if not app.winfo_exists(): return
    if auto_switch_enabled.get() and AUTO_SWITCH_AVAILABLE:
        try:
            window_id = win32gui.GetForegroundWindow()
            if window_id:
                _, process_id = win32process.GetWindowThreadProcessId(window_id)
                active_app = psutil.Process(process_id).name().lower()
                if active_app not in ["python.exe", "pythonw.exe", "code.exe"] and active_app != last_active_app:
                    last_active_app = active_app
                    if os.path.exists(os.path.join(PROFILES_DIR, f"{active_app}.json")):
                        if current_app_profile != active_app: load_app_profile(active_app)
                    else:
                        if current_app_profile != "default": load_app_profile("default")
        except Exception: pass
    try:
        app.after(1000, auto_switch_loop)
    except: pass


def check():
    global arduino, held_layer_keys, smart_mods_used, active_held_actions
    if not app.winfo_exists(): return
    if arduino and arduino.is_open:
        try:
            while arduino.in_waiting > 0:
                try:
                    line = arduino.readline().decode('utf-8', errors='ignore').strip()
                except Exception: continue
                
                if not line: continue
                log_raw(line)
                is_p, is_r = line.endswith("_DOWN") or "E" in line and not line.endswith("_UP"), line.endswith("_UP")
                base = line.replace("_DOWN", "").replace("_UP", "")
                if base not in ui_vars: continue
                role = ui_vars[base]["role"].get()
                
                if is_p:
                    active_roles = [ui_vars[b]["role"].get() for b in held_layer_keys]
                    layer = "mod3" if any("3" in r for r in active_roles) else "mod2" if any("2" in r for r in active_roles) else "mod1" if any("1" in r for r in active_roles) else "norm"
                    act = ui_vars[base][layer].get()
                    if act == "None": act = ui_vars[base]["norm"].get()
                    
                    if "Mod" in role:
                        for m in held_layer_keys: smart_mods_used.add(m)
                        held_layer_keys.add(base)
                        if "Smart" in role: act = "None"
                    else:
                        if act != "None":
                            for m in held_layer_keys: smart_mods_used.add(m)
                            
                    if act != "None":
                     
                        if act == "Mouse Scroll Up":
                            mouse.scroll(0, 1); continue
                        if act == "Mouse Scroll Down":
                            mouse.scroll(0, -1); continue

                        keys_to_press = ACTIONS.get(act, [])
                        active_held_actions[base] = keys_to_press
                        for k in keys_to_press: keyboard.press(k)
                        if "E" in line:
                            for k in reversed(keys_to_press): keyboard.release(k)
                            log_action(f"Turn: {act}")
                        else: log_action(f"Press: {act}")
                            
                elif is_r:
                    if "Mod" in role:
                        held_layer_keys.discard(base)
                        if "Smart" in role and base not in smart_mods_used:
                            a = ui_vars[base]["norm"].get()
                            if a != "None": 
                                keys_to_tap = ACTIONS.get(a, [])
                                for k in keys_to_tap: keyboard.press(k)
                                for k in reversed(keys_to_tap): keyboard.release(k)
                                log_action(f"Smart Tap: {a}")
                        smart_mods_used.discard(base)
                    
                    keys_to_release = active_held_actions.pop(base, None)
                    if keys_to_release:
                        for k in reversed(keys_to_release): keyboard.release(k)
        except Exception: pass
    try:
        app.after(10, check)
    except: pass

threading.Thread(target=run_tray, daemon=True).start()
app.after(1000, auto_switch_loop)
app.after(10, check)
app.mainloop()