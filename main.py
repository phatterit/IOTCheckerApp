import tkinter as tk
from tkinter import messagebox, filedialog, ttk, simpledialog, scrolledtext
from PIL import Image, ImageTk
import threading
import logging
import smtplib
import json
import os
import time
import hashlib
import random
import webbrowser
from cryptography.fernet import Fernet
from email.mime.text import MIMEText
from datetime import datetime
from ping3 import ping

# --- BIBLIOTEKI PDF ---
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as PDFImage
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import inch

# --- KONFIGURACJA ---
LOG_FILE = 'network_checker.log'
CONFIG_FILE = 'settings.json'
KEY_FILE = 'secret.key'
ICO_FILE = 'wiref.ico'
CHANGELOG_FILE = 'changelog.json'
GITHUB_URL = "https://github.com/phatterit" 

logging.basicConfig(
    filename=LOG_FILE, 
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# --- TREŚĆ LICENCJI MIT ---
MIT_LICENSE_TEXT = """MIT License

Copyright (c) 2026 hatterp

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

# --- REJESTRACJA CZCIONKI PL ---
FONT_NAME = 'Helvetica'
try:
    font_path = os.path.join(os.environ['WINDIR'], "Fonts", "arial.ttf")
    if os.path.exists(font_path):
        pdfmetrics.registerFont(TTFont('Arial', font_path))
        FONT_NAME = 'Arial'
    else:
        pdfmetrics.registerFont(TTFont('Arial', 'arial.ttf'))
        FONT_NAME = 'Arial'
except Exception: pass

# --- KLASA ZAKŁADKI ---
class SectionTab:
    def __init__(self, notebook, title, app_reference, insert_index=None):
        self.app = app_reference
        self.title = title
        self.devices = []  
        
        self.frame = tk.Frame(notebook)
        if insert_index is not None: notebook.insert(insert_index, self.frame, text=title)
        else: notebook.add(self.frame, text=title)
        
        title_lbl = tk.Label(self.frame, text=title, font=("Arial", 16, "bold"), fg="#34495e")
        title_lbl.pack(pady=(10, 5))

        h_frame = tk.Frame(self.frame, bg="#ecf0f1", pady=2)
        h_frame.pack(fill="x", padx=5, pady=2)
        
        headers = [("Nazwa", 28), ("Adres IP", 20), ("Status", 28), ("Web", 4), ("Sort", 6), ("Usuń", 4)]
        for text, w in headers:
            lbl = tk.Label(h_frame, text=text, width=w, font=("Arial", 9, "bold"), bg="#ecf0f1", anchor="c")
            lbl.pack(side="left", padx=2)
        
        self.container = tk.Frame(self.frame)
        self.container.pack(fill="both", expand=True, padx=5, pady=2)
        self.canvas = tk.Canvas(self.container)
        self.scrollbar = ttk.Scrollbar(self.container, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas)
        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        btn_add = tk.Button(self.frame, text=f"+ Dodaj wiersz do: {title}", 
                           command=self.add_row_ui, bg="#95a5a6", fg="white", font=("Arial", 9))
        btn_add.pack(fill="x", pady=2)

    def add_row_ui(self):
        self.add_row()
        logging.info(f"AKCJA: Dodano wiersz do sekcji '{self.title}'")

    def add_row(self, name="", ip=""):
        nv, iv = tk.StringVar(value=name), tk.StringVar(value=ip)
        device_data = {"name": nv, "ip": iv, "label": None, "frame": None}
        self.devices.append(device_data)
        self.refresh_view()

    def refresh_view(self):
        for widget in self.scrollable_frame.winfo_children(): widget.destroy()
        for index, dd in enumerate(self.devices):
            r = tk.Frame(self.scrollable_frame, pady=2)
            r.pack(fill="x", anchor="n")
            dd["frame"] = r
            tk.Entry(r, textvariable=dd["name"], width=28, font=("Arial", 10)).pack(side="left", padx=2)
            tk.Entry(r, textvariable=dd["ip"], width=20, font=("Arial", 10)).pack(side="left", padx=2)
            l = tk.Label(r, text="Oczekiwanie", bg="#bdc3c7", width=28, anchor="c", font=("Arial", 9))
            l.pack(side="left", padx=2)
            dd["label"] = l
            tk.Button(r, text="🌐", bg="#3498db", fg="white", width=3, command=lambda ip=dd["ip"]: self.open_web(ip.get())).pack(side="left", padx=2)
            tk.Button(r, text="▲", font=("Arial", 6), width=2, command=lambda i=index: self.move_item(i, -1)).pack(side="left", padx=1)
            tk.Button(r, text="▼", font=("Arial", 6), width=2, command=lambda i=index: self.move_item(i, 1)).pack(side="left", padx=1)
            tk.Button(r, text="X", bg="#c0392b", fg="white", width=3, command=lambda d=dd: self.remove_row(d)).pack(side="left", padx=2)

    def move_item(self, index, direction):
        new_index = index + direction
        if 0 <= new_index < len(self.devices):
            self.devices[index], self.devices[new_index] = self.devices[new_index], self.devices[index]
            self.refresh_view()

    def open_web(self, ip):
        ip = ip.strip()
        if ip: webbrowser.open(f"http://{ip}")
        else: messagebox.showwarning("Błąd", "Brak adresu IP!")

    def remove_row(self, device_data):
        if device_data in self.devices:
            self.devices.remove(device_data)
            self.refresh_view()
            logging.info(f"AKCJA: Usunięto wiersz z sekcji '{self.title}'")

# --- SECURITY ---
class SecurityManager:
    def __init__(self):
        self.key = self.load_key()
        self.cipher = Fernet(self.key)
    def load_key(self):
        if os.path.exists(KEY_FILE):
            with open(KEY_FILE, "rb") as kf: return kf.read()
        else:
            k = Fernet.generate_key(); open(KEY_FILE, "wb").write(k); return k
    def encrypt(self, t): return self.cipher.encrypt(t.encode()).decode() if t else ""
    def decrypt(self, t): 
        try: return self.cipher.decrypt(t.encode()).decode() if t else ""
        except: return ""
    def hash_pwd(self, p): return hashlib.sha256(p.encode()).hexdigest()
    def verify_pwd(self, s, p): return s == hashlib.sha256(p.encode()).hexdigest()

# --- APP ---
class IOTCheckerApp:
    def __init__(self, root):
        self.root = root
        self.program_version = "1.1.0"
        self.program_author = "hatterp"
        self.security = SecurityManager()
        
        self.root.title(f"IOT Guardian - v{self.program_version}")
        self.root.geometry("850x750")
        self.root.protocol("WM_DELETE_WINDOW", self.confirm_exit)

        if os.path.exists(ICO_FILE):
            try: self.root.iconbitmap(ICO_FILE)
            except Exception as e: logging.warning(f"Ikona błąd: {e}")
        
        self.sections = [] 
        self.is_auto_checking = False
        self.failed_devices = set()
        self.last_check_time = "Brak danych"
        
        self.config = {
            "smtp_server": "", "smtp_port": 587, "sender_email": "", "app_password_encrypted": "",
            "receivers": ["", "", ""], "last_list_path": "", "admin_password_hash": self.security.hash_pwd("admin")
        }
        self.current_app_password_plain = ""
        self.load_config()
        self.setup_ui()
        self.update_clock()
        
        threading.Thread(target=self.daily_report_scheduler, daemon=True).start()
        
        if self.config["last_list_path"] and os.path.exists(self.config["last_list_path"]):
            self.load_full_project(self.config["last_list_path"], silent=True)
        else:
            self.add_new_section("Ogólne"); self.sections[0].add_row()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    saved = json.load(f)
                    for k in self.config: 
                        if k in saved: self.config[k] = saved[k]
                    if "app_password_encrypted" in saved:
                        self.current_app_password_plain = self.security.decrypt(saved["app_password_encrypted"])
            except: pass

    def save_config(self):
        try:
            with open(CONFIG_FILE, 'w') as f: json.dump(self.config, f, indent=4)
        except Exception as e: messagebox.showerror("Błąd", str(e))

    def setup_ui(self):
        style = ttk.Style()
        try: style.theme_use('clam') 
        except: pass
        style.configure("TNotebook", background="#2c3e50")
        style.configure("TNotebook.Tab", font=('Arial', 10, 'bold'), padding=[12, 5], background="#bdc3c7")
        style.map("TNotebook.Tab", background=[("selected", "#ecf0f1")], foreground=[("selected", "black")])

        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        f_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Plik", menu=f_menu)
        f_menu.add_command(label="Otwórz Projekt (Reset)", command=lambda: self.load_full_project(None))
        f_menu.add_command(label="Importuj do AKTYWNEJ", command=self.import_to_active_tab)
        f_menu.add_separator()
        f_menu.add_command(label="Eksportuj Całość", command=self.export_all)
        f_menu.add_separator()
        f_menu.add_command(label="Wyjście", command=self.confirm_exit)
        
        sec_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Sekcje", menu=sec_menu)
        sec_menu.add_command(label="Dodaj nową sekcję", command=self.ask_new_section)
        sec_menu.add_command(label="Zmień nazwę sekcji", command=self.rename_current_section)
        sec_menu.add_command(label="Usuń aktywną sekcję", command=self.remove_current_section)

        r_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Raporty", menu=r_menu)
        r_menu.add_command(label="Generuj PDF", command=self.generate_pdf_report)
        r_menu.add_command(label="Logi", command=self.open_logs_window)

        t_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Narzędzia", menu=t_menu)
        t_menu.add_command(label="Konfiguracja E-mail", command=self.ask_password_and_open_settings)
        t_menu.add_command(label="Zmień hasło Admina", command=self.change_admin_password)
        t_menu.add_command(label="O Autorze", command=self.show_about)

        top = tk.Frame(self.root, bg="#2c3e50", pady=8)
        top.pack(fill="x")
        
        if os.path.exists("img/wirefm.png"):
            try:
                img = Image.open("img/wirefm.png").resize((40,40), Image.Resampling.LANCZOS)
                self.logo_img = ImageTk.PhotoImage(img)
                tk.Label(top, image=self.logo_img, bg="#2c3e50").pack(side="left", padx=10)
            except: pass

        # --- PRZYCISK IMPORT ---
        tk.Button(top, text="IMPORTUJ", command=self.import_to_active_tab, bg="#f39c12", fg="white", font=("Arial",10,"bold")).pack(side="left", padx=10)

        tk.Button(top, text="SPRAWDŹ WSZYSTKO", command=self.start_manual_ping, bg="#27ae60", fg="white", font=("Arial",10,"bold")).pack(side="left", padx=10)
        self.btn_auto = tk.Button(top, text="START AUTO", command=self.toggle_auto_ping, bg="#2980b9", fg="white", font=("Arial",10,"bold"))
        self.btn_auto.pack(side="left", padx=10)
        
        self.led_canvas = tk.Canvas(top, width=32, height=14, bg="#2c3e50", highlightthickness=0)
        self.led_green = self.led_canvas.create_oval(2, 2, 12, 12, fill="#7f8c8d", outline="") 
        self.led_orange = self.led_canvas.create_oval(18, 2, 28, 12, fill="#7f8c8d", outline="")
        self.led_canvas.pack(side="left", padx=2)

        self.clock_label = tk.Label(top, text="", bg="#2c3e50", fg="#ecf0f1", font=("Consolas",11))
        self.clock_label.pack(side="right", padx=15)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)
        self.notebook.bind("<Button-1>", self.on_tab_click)
        self.plus_frame = tk.Frame(self.notebook, bg="#2c3e50")
        self.notebook.add(self.plus_frame, text="  +  ")

    def animate_network_leds(self):
        if not self.is_auto_checking:
            self.led_canvas.itemconfig(self.led_green, fill="#7f8c8d")
            self.led_canvas.itemconfig(self.led_orange, fill="#7f8c8d")
            return
        state_g = random.choice(["#2ecc71", "#27ae60", "#2ecc71", "#7f8c8d"]) 
        state_o = random.choice(["#f39c12", "#d35400", "#7f8c8d", "#7f8c8d"])
        self.led_canvas.itemconfig(self.led_green, fill=state_g)
        self.led_canvas.itemconfig(self.led_orange, fill=state_o)
        self.root.after(random.randint(50, 150), self.animate_network_leds)

    def on_tab_click(self, event):
        try:
            clicked_tab_index = self.notebook.index(f"@{event.x},{event.y}")
            if clicked_tab_index == self.notebook.index("end") - 1:
                self.ask_new_section()
                return "break"
        except: pass

    def add_new_section(self, name):
        insert_idx = len(self.sections) 
        new_sec = SectionTab(self.notebook, name, self, insert_index=insert_idx)
        self.sections.append(new_sec)
        return new_sec

    def ask_new_section(self):
        name = simpledialog.askstring("Nowa sekcja", "Podaj nazwę działu:")
        if name:
            s = self.add_new_section(name)
            self.notebook.select(len(self.sections)-1)
            s.add_row()

    def remove_current_section(self):
        if not self.sections: return
        idx = self.notebook.index("current")
        if idx >= len(self.sections): return 
        name = self.sections[idx].title
        if messagebox.askyesno("Usuń", f"Usunąć zakładkę '{name}'?"):
            self.sections[idx].frame.destroy()
            self.sections.pop(idx)

    def rename_current_section(self):
        if not self.sections: return
        idx = self.notebook.index("current")
        if idx >= len(self.sections): return
        old_name = self.sections[idx].title
        new_name = simpledialog.askstring("Zmiana nazwy", "Nowa nazwa:", initialvalue=old_name)
        if new_name:
            self.sections[idx].title = new_name
            self.notebook.tab(idx, text=new_name)
            for child in self.sections[idx].frame.winfo_children():
                if isinstance(child, tk.Label) and child.cget("text") == old_name:
                    child.config(text=new_name)
                    break

    def load_full_project(self, path, silent=False):
        if not path: path = filedialog.askopenfilename()
        if not path: return
        if self.sections and path != self.config["last_list_path"] and not silent:
            if not messagebox.askyesno("Uwaga", "Resetować projekt?"): return
        for s in self.sections: s.frame.destroy()
        self.sections = []
        current_section = None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    if line.startswith("[") and line.endswith("]"):
                        current_section = self.add_new_section(line[1:-1])
                    else:
                        if current_section is None: current_section = self.add_new_section("Domyślna")
                        parts = line.split()
                        if len(parts) >= 2: current_section.add_row(parts[0], parts[1])
            self.config["last_list_path"] = path; self.save_config()
        except Exception as e: messagebox.showerror("Błąd", str(e))

    def import_to_active_tab(self):
        if not self.sections: return messagebox.showwarning("Błąd", "Brak sekcji!")
        idx = self.notebook.index("current")
        if idx >= len(self.sections): return 
        active_section = self.sections[idx]
        path = filedialog.askopenfilename(filetypes=[("Pliki tekstowe", "*.txt")])
        if not path: return
        try:
            count = 0
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    if line.startswith("[") and line.endswith("]"): continue 
                    parts = line.split()
                    if len(parts) >= 2: 
                        active_section.add_row(parts[0], parts[1])
                        count += 1
            # --- ZMIANA: WYŚWIETLANIE LICZBY ZAIMPORTOWANYCH WPISÓW ---
            messagebox.showinfo("Sukces", f"Sukces! Zaimportowano {count} nowych wpisów.")
            # -----------------------------------------------------------
        except Exception as e: messagebox.showerror("Błąd", str(e))

    def export_all(self):
        path = filedialog.asksaveasfilename(defaultextension=".txt")
        if not path: return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                for sec in self.sections:
                    if not sec.devices: continue
                    f.write(f"[{sec.title}]\n")
                    for d in sec.devices:
                        if d["name"].get(): f.write(f"{d['name'].get()} {d['ip'].get()}\n")
                    f.write("\n")
            messagebox.showinfo("Sukces", "Zapisano projekt.")
        except Exception as e: messagebox.showerror("Błąd", str(e))

    def ping_logic(self, d, gui=True):
        ip = d["ip"].get().strip()
        name = d["name"].get().strip()
        if not ip: return False
        try:
            res = ping(ip, timeout=2)
            if gui and d.get("label"):
                if res:
                    self.root.after(0, lambda: d["label"].config(text=f"OK ({res*1000:.0f}ms)", bg="#2ecc71", fg="black"))
                    if ip in self.failed_devices: 
                        self.failed_devices.remove(ip)
                        logging.info(f"STATUS: '{name}' ONLINE")
                else:
                    self.root.after(0, lambda: d["label"].config(text="OFFLINE", bg="#e74c3c", fg="white"))
                    if ip not in self.failed_devices: 
                        self.failed_devices.add(ip)
                        logging.warning(f"STATUS: '{name}' OFFLINE")
            return res is not None
        except: return False

    def start_manual_ping(self):
        self.last_check_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for sec in self.sections:
            for d in sec.devices:
                if d.get("label") and d["label"].winfo_exists():
                    d["label"].config(text="...", bg="#f1c40f")
                    threading.Thread(target=self.ping_logic, args=(d,), daemon=True).start()

    def generate_pdf_report(self):
        if not self.sections: return
        path = filedialog.askdirectory()
        if not path: return
        fn = os.path.join(path, f"Raport_KD_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf")
        try:
            doc = SimpleDocTemplate(fn, pagesize=letter)
            styles = getSampleStyleSheet()
            normal_style = ParagraphStyle('PL_Normal', parent=styles['Normal'], fontName=FONT_NAME, fontSize=10)
            title_style = ParagraphStyle('PL_Title', parent=styles['Title'], fontName=FONT_NAME, fontSize=18, spaceAfter=20)
            header_style = ParagraphStyle('PL_Header', parent=styles['Heading2'], fontName=FONT_NAME, fontSize=14, spaceBefore=15, spaceAfter=10)
            elements = []
            
            logo_path = "img/wirefm.png"
            if os.path.exists(logo_path):
                pil_img = Image.open(logo_path)
                w, h = pil_img.size
                t_w = 2.0 * inch
                t_h = t_w * (h/float(w))
                elements.append(PDFImage(logo_path, width=t_w, height=t_h, hAlign='LEFT'))
                elements.append(Spacer(1, 15))

            elements.append(Paragraph(f"Raport Sieciowy - IOT Guardian", title_style))
            elements.append(Paragraph(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", normal_style))
            elements.append(Spacer(1, 20))
            
            for sec in self.sections:
                if not sec.devices: continue
                elements.append(Paragraph(f"Dział: {sec.title}", header_style))
                data = [['Urządzenie', 'IP', 'Status']]
                for d in sec.devices:
                    if d.get("label"):
                        n = d["name"].get()
                        if FONT_NAME=='Helvetica': n=n.replace("ą","a").replace("ę","e").replace("ś","s").replace("ć","c").replace("ż","z").replace("ź","z").replace("ł","l").replace("ó","o").replace("ń","n")
                        data.append([n, d["ip"].get(), d["label"].cget("text")])
                t = Table(data, colWidths=[2.5*inch, 1.5*inch, 2.5*inch])
                t.setStyle(TableStyle([('FONTNAME',(0,0),(-1,-1),FONT_NAME), ('BACKGROUND',(0,0),(-1,0),colors.HexColor("#2c3e50")), ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke), ('GRID',(0,0),(-1,-1),0.5,colors.grey), ('ALIGN',(0,0),(-1,-1),'CENTER')]))
                elements.append(t); elements.append(Spacer(1, 15))
            doc.build(elements)
            messagebox.showinfo("Sukces", f"PDF: {fn}")
        except Exception as e: messagebox.showerror("Błąd", str(e))

    def daily_report_scheduler(self):
        lr = None
        while True:
            n = datetime.now()
            if n.hour == 6 and n.minute == 0 and lr != n.strftime("%F"):
                lns = []
                for sec in self.sections:
                    lns.append(f"--- {sec.title} ---")
                    for d in sec.devices: lns.append(f"{d['name'].get()} ({d['ip'].get()}): {'ONLINE' if self.ping_logic(d,True) else 'OFFLINE'}")
                self.send_email("Raport Dzienny", "\n".join(lns))
                lr = n.strftime("%F"); time.sleep(65)
            time.sleep(30)

    def send_email(self, subj, body):
        if not self.config["sender_email"] or not self.current_app_password_plain: return
        rec = [r for r in self.config["receivers"] if r]
        if not rec: return
        try:
            msg = MIMEText(body); msg['Subject'] = subj; msg['From'] = self.config["sender_email"]; msg['To'] = ", ".join(rec)
            with smtplib.SMTP(self.config["smtp_server"], int(self.config["smtp_port"])) as s:
                s.starttls(); s.login(self.config["sender_email"], self.current_app_password_plain); s.send_message(msg)
        except: pass

    def ask_password_and_open_settings(self):
        pwd = simpledialog.askstring("Auth", "Hasło Admina:", show='*')
        if pwd and self.security.verify_pwd(self.config["admin_password_hash"], pwd): self.open_settings_window()
        else: messagebox.showerror("Błąd", "Złe hasło!")

    def open_settings_window(self):
        win = tk.Toplevel(self.root); win.title("SMTP"); win.geometry("400x550")
        vars = {}
        for k, l in [("smtp_server","Serwer"), ("smtp_port","Port"), ("sender_email","Login")]:
            tk.Label(win, text=l).pack(); e=tk.Entry(win); e.insert(0,self.config.get(k,"")); e.pack(fill="x",padx=10); vars[k]=e
        tk.Label(win, text="Hasło:").pack(); pe = tk.Entry(win, show="*"); pe.pack(fill="x",padx=10)
        tk.Label(win, text="Odbiorcy:").pack(); rv = []
        for i in range(3): e=tk.Entry(win); e.insert(0,self.config["receivers"][i] if i<len(self.config["receivers"]) else ""); e.pack(fill="x",padx=10); rv.append(e)
        def save():
            for k in ["smtp_server","sender_email"]: self.config[k]=vars[k].get()
            try: self.config["smtp_port"]=int(vars["smtp_port"].get())
            except: pass
            if pe.get(): self.current_app_password_plain=pe.get(); self.config["app_password_encrypted"]=self.security.encrypt(pe.get())
            self.config["receivers"]=[e.get() for e in rv]; self.save_config(); win.destroy(); messagebox.showinfo("OK","Zapisano")
        tk.Button(win, text="ZAPISZ", command=save, bg="green", fg="white").pack(fill="x", padx=20, pady=20)

    def change_admin_password(self):
        old = simpledialog.askstring("Auth", "Stare:", show='*')
        if not self.security.verify_pwd(self.config["admin_password_hash"], old): return
        new = simpledialog.askstring("Auth", "Nowe:", show='*')
        if new: self.config["admin_password_hash"] = self.security.hash_pwd(new); self.save_config()

    def toggle_auto_ping(self):
        self.is_auto_checking = not self.is_auto_checking
        self.btn_auto.config(text="STOP AUTO" if self.is_auto_checking else "START AUTO", bg="#c0392b" if self.is_auto_checking else "#2980b9")
        if self.is_auto_checking:
            self.auto_loop()
            self.animate_network_leds()
        else:
            self.animate_network_leds()

    def auto_loop(self):
        if self.is_auto_checking: self.start_manual_ping(); self.root.after(60000, self.auto_loop)

    def update_clock(self):
        self.clock_label.config(text=datetime.now().strftime("%H:%M:%S | %d.%m.%Y")); self.root.after(1000, self.update_clock)
    def confirm_exit(self):
        if messagebox.askyesno("Wyjście", "Czy zamknąć?"): self.root.destroy()

    def show_about(self):
        about_win = tk.Toplevel(self.root)
        about_win.title("O Autorze i Licencja")
        about_win.geometry("600x650") # Nieco szersze okno dla licencji
        
        # --- ZMIENIONY NAGŁÓWEK ---
        header_text = f"hatterp\nIOT Guardian v{self.program_version}\n\nPowered by hatterp & AI (Gemini)"
        tk.Label(about_win, text=header_text, font=("Arial", 12, "bold"), fg="#2c3e50").pack(pady=(20, 5))
        
        # --- LINK DO GITHUB ---
        link_lbl = tk.Label(about_win, text=f"GitHub: {GITHUB_URL}", font=("Arial", 10, "underline"), fg="blue", cursor="hand2")
        link_lbl.pack(pady=(0, 15))
        link_lbl.bind("<Button-1>", lambda e: webbrowser.open(GITHUB_URL))

        st = scrolledtext.ScrolledText(about_win, width=65, height=28, wrap=tk.WORD)
        st.pack(padx=10, pady=10)
        st.tag_config("bold", font=("Arial", 10, "bold"))
        st.tag_config("version", foreground="#2980b9", font=("Arial", 10, "bold"))
        st.tag_config("license_header", foreground="#e67e22", font=("Arial", 11, "bold"))

        # 1. Wstawienie Licencji MIT na początek
        st.insert(tk.END, "LICENCJA / LICENSE:\n", "license_header")
        st.insert(tk.END, MIT_LICENSE_TEXT + "\n\n", "normal")
        st.insert(tk.END, "-"*50 + "\n\n")

        # 2. Wstawienie Changeloga
        st.insert(tk.END, "HISTORIA ZMIAN / CHANGELOG:\n\n", "license_header")
        
        if os.path.exists(CHANGELOG_FILE):
            try:
                with open(CHANGELOG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for entry in data:
                        header = f"[{entry['version']}] - {entry['title']}"
                        st.insert(tk.END, header + "\n", "version")
                        st.insert(tk.END, f"Data: {entry.get('date', '')}\n", "bold")
                        for change in entry['changes']:
                            st.insert(tk.END, f" • {change}\n")
                        st.insert(tk.END, "\n" + "-"*40 + "\n\n")
            except Exception as e:
                st.insert(tk.END, f"Błąd wczytywania historii zmian: {e}")
        else:
            st.insert(tk.END, "Nie znaleziono pliku changelog.json")
            
        st.config(state='disabled')
        tk.Button(about_win, text="Zamknij", command=about_win.destroy).pack(pady=10)

    def open_logs_window(self):
        w = tk.Toplevel(self.root); t = scrolledtext.ScrolledText(w); t.pack()
        if os.path.exists(LOG_FILE): t.insert(tk.END, open(LOG_FILE).read())

if __name__ == "__main__":
    root = tk.Tk()
    app = IOTCheckerApp(root)
    root.mainloop()