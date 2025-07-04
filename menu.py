# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import sys
import shutil
import os
import subprocess

if sys.platform == 'win32':
    import ctypes
    from ctypes import wintypes
    from ctypes import windll
    import winsound

    class ACCENTPOLICY(ctypes.Structure):
        _fields_ = [
            ("AccentState", ctypes.c_int),
            ("AccentFlags", ctypes.c_int),
            ("GradientColor", ctypes.c_int),
            ("AnimationId", ctypes.c_int)
        ]

    class WINCOMPATTRDATA(ctypes.Structure):
        _fields_ = [
            ("Attribute", ctypes.c_int),
            ("Data", ctypes.c_void_p),
            ("SizeOfData", ctypes.c_size_t)
        ]

    def set_blur_effect(hwnd):
        accent = ACCENTPOLICY()
        accent.AccentState = 4  # ACCENT_ENABLE_BLURBEHIND
        accent.GradientColor = 0xD9000000  
        data = WINCOMPATTRDATA()
        data.Attribute = 19  # WCA_ACCENT_POLICY
        data.Data = ctypes.addressof(accent)
        data.SizeOfData = ctypes.sizeof(accent)
        ctypes.windll.user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(data))

    def set_window_round_corner(hwnd, width, height, radius=20):
        hrgn = windll.gdi32.CreateRoundRectRgn(0, 0, width+1, height+1, radius, radius)
        windll.user32.SetWindowRgn(hwnd, hrgn, True)

    def play_sound(path):
        try:
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception:
            pass
else:
    def play_sound(path):
        pass  

LANG_PY_MAP = {
    'zh_cn': 'kiridroid_zh.py',
    'zh_tw': 'kiridroid_tw.py',
    'yue': 'kiridroid_hk.py',
    'en': 'kiridroid_en.py',
    'ja': 'kiridroid_ja.py',
    'ko': 'kiridroid_ko.py',
    'ru': 'kiridroid_ru.py',
    'uk': 'kiridroid_uk.py',
    'de': 'kiridroid_de.py',
    'fr': 'kiridroid_fr.py',
    'pt': 'kiridroid_pt.py',
    'es': 'kiridroid_es.py',
    'ar': 'kiridroid_ar.py',
}

class MenuApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Kiridroid Menu")
        self.geometry("520x500")
        self.resizable(False, False)
        self.configure(bg="#F0F0F0")
        self.attributes('-alpha', 0.92)
        self.icon_path = "icon.ico"
        try:
            self.iconbitmap(self.icon_path)
        except Exception as e:
            print(f"Set icon failed: {e}")
        self.overrideredirect(True)  
        self.create_titlebar()
        self.create_widgets()
        self.after(10, self.apply_round_corner)

    def apply_round_corner(self):
        if sys.platform == 'win32':
            hwnd = self.winfo_id()
            width = self.winfo_width()
            height = self.winfo_height()
            if width < 2 or height < 2:
                self.after(10, self.apply_round_corner)
                return
            set_window_round_corner(hwnd, width, height, radius=20)

    def create_titlebar(self):
        self.titlebar = tk.Frame(self, bg="#1976D2", relief="raised", bd=0, height=36)
        self.titlebar.pack(fill=tk.X, side=tk.TOP)
        self.titlebar.bind('<Button-1>', self.start_move)
        self.titlebar.bind('<B1-Motion>', self.do_move)

        self.title_label = tk.Label(self.titlebar, text="Kiridroid Menu", bg="#1976D2", fg="white", font=("Arial", 12, "bold"))
        self.title_label.pack(side=tk.LEFT, padx=12)
        self.title_label.bind('<Button-1>', self.start_move)
        self.title_label.bind('<B1-Motion>', self.do_move)

        close_btn = tk.Button(self.titlebar, text="✕", bg="#1976D2", fg="white", bd=0, font=("Arial", 12, "bold"), activebackground="#D32F2F", activeforeground="white", command=self.destroy)
        close_btn.pack(side=tk.RIGHT, padx=8, pady=2)

    def start_move(self, event):
        self._x = event.x
        self._y = event.y

    def do_move(self, event):
        x = self.winfo_pointerx() - self._x
        y = self.winfo_pointery() - self._y
        self.geometry(f'+{x}+{y}')
        self.apply_round_corner()  # Apply round corner when moving

    def create_widgets(self):
        lbl_language = ttk.Label(self, text="Select Your Language", font=("Arial", 14))
        lbl_language.pack(pady=(20, 10))

        languages = [
            ("English", "en"), ("简体中文", "zh_cn"), ("繁體中文", "zh_tw"), ("廣東話", "yue"),
            ("日本語", "ja"), ("한국어", "ko"), ("русский язык", "ru"), ("українська мова", "uk"),
            ("Deutsch", "de"), ("français", "fr"), ("português", "pt"), ("español", "es"),
            ("العربية", "ar"), ("", ""), ("", ""), ("", "")
        ]
        self.lang_var = tk.StringVar(value="en")
        lang_frame = ttk.Frame(self)
        lang_frame.pack(fill=tk.X, padx=20)
        for i in range(4):
            lang_frame.grid_rowconfigure(i, weight=1)
            for j in range(4):
                lang_frame.grid_columnconfigure(j, weight=1, minsize=120)
                idx = i * 4 + j
                text, value = languages[idx]
                if text:
                    rb = ttk.Radiobutton(
                        lang_frame, text=text, variable=self.lang_var, value=value
                    )
                    rb.grid(row=i, column=j, padx=2, pady=2, sticky='nsew')
                    rb.configure(style='Lang.TRadiobutton')

        style = ttk.Style()
        style.configure('Lang.TRadiobutton', font=("Arial", 10))

        key_label = ttk.Label(self, text="Select Your Key.jks", font=("Arial", 12))
        key_label.pack(pady=(30, 5))
        self.key_var = tk.StringVar(value="default")
        key_frame = ttk.Frame(self)
        key_frame.pack()
        ttk.Radiobutton(key_frame, text="Default Key", variable=self.key_var, value="default").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(key_frame, text="Your Key", variable=self.key_var, value="your").pack(side=tk.LEFT, padx=10)

        start_btn = ttk.Button(self, text="Start", width=20, command=self.on_start)
        start_btn.pack(pady=(30, 10))

        bottom_label = ttk.Label(self, text="Powered by RinstuPy Engine", font=("Arial", 10))
        bottom_label.pack(side=tk.BOTTOM, pady=10)

    def on_start(self):
        play_sound('trans.wav')  
        lang_code = self.lang_var.get()
        key_mode = self.key_var.get()
        # 1. Handle Key
        if key_mode == 'your':
            play_sound('file.wav')  
            file_path = filedialog.askopenfilename(
                title="Please select your .jks file",
                filetypes=[("KeyStore Files", "*.jks"), ("All Files", "*.*")]
            )
            if not file_path:
                play_sound('error.wav')  
                messagebox.showwarning("No file selected", "No jks file selected. Operation cancelled.")
                return
            try:
                shutil.copyfile(file_path, "testkey.jks")
            except Exception as e:
                play_sound('error.wav')
                messagebox.showerror("Copy failed", f"Failed to replace testkey.jks: {e}")
                return
        # 2. Handle language
        pyfile = LANG_PY_MAP.get(lang_code)
        if not pyfile or not os.path.exists(pyfile):
            play_sound('error.wav')
            messagebox.showerror("File not found", f"Cannot find the script file: {pyfile}")
            return
        # 3. Launch script
        try:
            if sys.platform == 'win32':
                subprocess.Popen([sys.executable, pyfile], shell=True)
            else:
                subprocess.Popen([sys.executable, pyfile])
        except Exception as e:
            play_sound('error.wav')
            messagebox.showerror("Launch failed", f"Failed to launch script: {e}")
            return
        self.destroy()

if __name__ == "__main__":
    app = MenuApp()
    app.mainloop() 