import customtkinter as ctk
from tkinter import ttk, filedialog, messagebox, colorchooser
import gzip
import json
import os

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class ValueHandler:
    @staticmethod
    def decode(raw_value):
        if isinstance(raw_value, dict):
            v_type = raw_value.get("__type") or raw_value.get("_type")
            value = raw_value.get("value")
            return (v_type, value) if v_type else ("OBJECT", raw_value)
        
        if isinstance(raw_value, str):
            trimmed = raw_value.strip()
            if trimmed.startswith("{") and ("_type" in trimmed or "__type" in trimmed):
                try:
                    data = json.loads(trimmed)
                    return data.get("__type") or data.get("_type"), data.get("value")
                except: pass
            return "STRING", raw_value

        if isinstance(raw_value, (int, float, bool)):
            return type(raw_value).__name__, raw_value
        return "UNKNOWN", raw_value

    @staticmethod
    def to_readable(raw_value):
        v_type, val = ValueHandler.decode(raw_value)
        if v_type and "color" in str(v_type).lower() and isinstance(val, dict):
            return f"🎨 Color (R:{val.get('r',0):.2f}, G:{val.get('g',0):.2f}, B:{val.get('b',0):.2f})"
        if "Vector" in str(v_type) and isinstance(val, dict):
            parts = [f"{k}:{v:.2f}" for k, v in val.items()]
            return f"📍 {v_type} ({', '.join(parts)})"
        if v_type == "bool" or isinstance(val, bool):
            return "🟢 ON" if val else "⚫ OFF"
        if isinstance(val, (int, float)):
            return f"🔢 {val:.2f}" if isinstance(val, float) else f"🔢 {val}"
        return f"📝 {str(val).strip('\"\'')}"

    @staticmethod
    def encode(v_type, clean_val):
        return {"__type": v_type, "value": clean_val}

class MSLPEditor(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.iconbitmap(resource_path("Icon.ico"))
        self.title("MSLP Save Editor")
        self.geometry("1200x850")

        self.active_color_win = None
        
        self.bg_color = "#2e2e2e"
        self.card_color = "#2e2e2e"
        self.accent_color = "#3a7ebf"
        self.configure(fg_color=self.bg_color)

        self.default_path = os.path.join(os.path.expandvars(r'%USERPROFILE%'), "AppData", "LocalLow", "Overline Games", "My Sleeper")
        self.full_data = {}
        self.categorized_groups = {}
        self.domains = ["META", "WORLD", "PLAYER", "VEHICLE", "ITEM", "UNCATEGORIZED"]
        self.tab_names = {d: d for d in self.domains}
        self.tab_names.update({"VEHICLE": "VEHICLES", "ITEM": "ITEMS"})
        
        self.current_page = {domain: 0 for domain in self.domains}
        self.items_per_page = 100
        
        self.setup_ui()
        self.apply_modern_tree_style()

    def get_current_domain(self):
        if not hasattr(self, 'tab_view'): return "UNCATEGORIZED"
        current_tab_name = self.tab_view.get()
        for dom, name in self.tab_names.items():
            if name == current_tab_name: return dom
        return "UNCATEGORIZED"

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Barra superior
        self.top_bar = ctk.CTkFrame(self, height=70, fg_color=self.card_color, corner_radius=0)
        self.top_bar.grid(row=0, column=0, sticky="ew")
        
        ctk.CTkButton(self.top_bar, text="Open Save", command=self.load_file, font=("Segoe UI", 13, "bold")).pack(side="left", padx=20, pady=20)
        ctk.CTkButton(self.top_bar, text="Save Changes", command=self.save_file, fg_color="#1fb588", font=("Segoe UI", 13, "bold")).pack(side="left")
        
        self.lbl_file = ctk.CTkLabel(self.top_bar, text="No File Selected", font=("Segoe UI", 12, "italic"), text_color="#aaaaaa")
        self.lbl_file.pack(side="left", padx=20)

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self.on_search_change)
        self.search_entry = ctk.CTkEntry(self.top_bar, placeholder_text="🔍 Search item or key...", width=300, textvariable=self.search_var)
        self.search_entry.pack(side="right", padx=20)

        # Abas
        self.tab_view = ctk.CTkTabview(self, command=self.on_tab_change, segmented_button_fg_color=self.card_color, segmented_button_selected_color=self.accent_color, fg_color="#262626")
        self.tab_view.grid(row=1, column=0, sticky="nsew", padx=20, pady=(10, 5))
        self.tab_view._segmented_button.configure(height=40, font=("Segoe UI", 16), corner_radius=8)
        
        self.trees = {}
        for d in self.domains:
            tab = self.tab_view.add(self.tab_names[d])
            f = ctk.CTkFrame(tab, fg_color="transparent")
            f.pack(fill="both", expand=True, padx=5, pady=5)
            
            t = ttk.Treeview(f, columns=("Value"), show="tree headings")
            t.heading("#0", text="PROPERTY")
            t.heading("Value", text="VALUE")
            t.column("#0", width=400)
            t.column("Value", width=500)
            
            s = ttk.Scrollbar(f, orient="vertical", command=t.yview)
            t.configure(yscrollcommand=s.set)
            t.pack(side="left", fill="both", expand=True)
            s.pack(side="right", fill="y")
            
            t.bind("<Double-1>", self.on_item_double_click)
            self.trees[d] = t

        # Barra inferior
        self.bottom_bar = ctk.CTkFrame(self, height=60, fg_color="transparent")
        self.bottom_bar.grid(row=2, column=0, sticky="ew", padx=20, pady=10)
        
        # Container centralizado
        self.page_control_container = ctk.CTkFrame(self.bottom_bar, fg_color="transparent")
        self.page_control_container.pack(expand=True) 

        # Botão voltar
        ctk.CTkButton(self.page_control_container, text="<", width=40, 
                      command=lambda: self.change_page(-1)).pack(side="left", padx=10)
        
        # Label da página
        self.lbl_page = ctk.CTkLabel(self.page_control_container, text="Page 0/0", 
                                     font=("Segoe UI", 12, "bold"), text_color="#FFFFFF")
        self.lbl_page.pack(side="left", padx=20)
        
        # Botão próximo
        ctk.CTkButton(self.page_control_container, text=">", width=40, 
                      command=lambda: self.change_page(1)).pack(side="left", padx=10)

    def on_search_change(self, *args):
        query = self.search_var.get().lower()
        if len(query) < 2:
            self.update_current_tab()
            return
        
        results = [k for k in self.full_data.keys() if query in k.lower()]
        if not results: return

        current_dom = self.get_current_domain()
        found_in_current = any(res.startswith(current_dom) for res in results)

        if not found_in_current:
            first_res = results[0]
            new_dom = first_res.split('.')[0] if '.' in first_res else "UNCATEGORIZED"
            if new_dom in self.domains and new_dom != current_dom:
                self.tab_view.set(self.tab_names[new_dom])
        
        active_dom = self.get_current_domain()
        filtered_keys = [r for r in results if r.startswith(active_dom)]
        self.render_tree(active_dom, filtered_keys)
        self.lbl_page.configure(text=f"SEARCH: {len(results)} matches")

    def apply_modern_tree_style(self):
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background=self.card_color, foreground="#ffffff", fieldbackground=self.card_color, borderwidth=0, font=("Segoe UI", 11), rowheight=35)
        style.configure("Treeview.Heading", background="#2d2d2d", foreground="#ffffff", relief="flat", font=("Segoe UI", 10, "bold"))
        style.map("Treeview", background=[('selected', self.accent_color)])

    def load_file(self):
        path = filedialog.askopenfilename(initialdir=self.default_path)
        if not path: return
        try:
            try:
                with gzip.open(path, 'rb') as f: self.full_data = json.loads(f.read().decode('utf-8'))
            except:
                with open(path, 'r', encoding='utf-8') as f: self.full_data = json.load(f)
            self.lbl_file.configure(text=f"📂 {os.path.basename(path)}")
            self.process_keys()
            self.update_current_tab()
        except Exception as e: messagebox.showerror("Error", str(e))

    def process_keys(self):
        self.categorized_groups = {d: {} for d in self.domains}
        for k in sorted(self.full_data.keys()):
            if not k or not k.strip() or k in self.domains: continue # Pula chaves inválidas ou raiz
            
            p = k.split('.')
            dom = p[0] if p[0] in self.domains else "UNCATEGORIZED" # Se n tem aba fixa, ent é sem categoria
            grp = p[1] if len(p) > 1 else p[0]
            
            if grp not in self.categorized_groups[dom]: 
                self.categorized_groups[dom][grp] = []
            self.categorized_groups[dom][grp].append(k)

    def update_current_tab(self):
        if not self.categorized_groups: return
        dom = self.get_current_domain()
        grps = list(self.categorized_groups[dom].keys())
        max_p = max(0, (len(grps)-1)//self.items_per_page)
        self.lbl_page.configure(text=f"PAGE {self.current_page[dom]+1} OF {max_p+1}")
        start = self.current_page[dom] * self.items_per_page
        end = start + self.items_per_page
        keys = []
        for g in grps[start:end]: keys.extend(self.categorized_groups[dom][g])
        self.render_tree(dom, keys)

    def render_tree(self, dom, keys):
        t = self.trees[dom]
        t.delete(*t.get_children())
        h = {}
        for k in keys:
            parts = k.split('.')
            if parts[0] == dom and len(parts) > 1: parts = parts[1:]
            curr = h
            for i, part in enumerate(parts):
                if part not in curr:
                    curr[part] = {"_val_": self.full_data[k], "_key_": k} if i == len(parts)-1 else {}
                curr = curr[part]

        def ins(parent, dic):
            for n, c in dic.items():
                if n in ["_val_", "_key_"]: continue
                if "_val_" in c:
                    t.insert(parent, "end", text=n, values=(ValueHandler.to_readable(c["_val_"]),), tags=(c["_key_"],))
                else:
                    is_searching = len(self.search_var.get()) > 1
                    node = t.insert(parent, "end", text=n, open=False)
                    ins(node, c)
        ins("", h)

    def open_teleport_window(self, item, full_key, v_type, clean_val):
        win = ctk.CTkToplevel(self)
        win.title("Teleport Menu")
        win.geometry("300x400")
        win.attributes("-topmost", True)

        ctk.CTkLabel(win, text=f"Teleport Item:", font=("Segoe UI", 12, "bold")).pack(pady=10)
        # Mostra o nome do objeto pra vc saber oq está teleportando
        ctk.CTkLabel(win, text=full_key.split('.')[-2] if '.' in full_key else full_key, text_color=self.accent_color).pack(pady=5)

        def apply_tp(coords):
            # Garante que vai salvar no mesmo formato que o jogo mandou (Lista ou Dicionário)
            if isinstance(clean_val, list) and len(clean_val) >= 3:
                new_val = clean_val.copy()
                new_val[0] = coords['x']
                new_val[1] = coords['y']
                new_val[2] = coords['z']
            elif isinstance(clean_val, dict):
                new_val = clean_val.copy()
                new_val['x'] = coords['x']
                new_val['y'] = coords['y']
                new_val['z'] = coords['z']
            else:
                new_val = coords

            self.save_direct_value(item, full_key, v_type, new_val)
            win.destroy()
            messagebox.showinfo("TP", "Position Updated!")

        # BOTÃO TP TO PLAYER
        def tp_to_player():
            player_key = "PLAYER.Transform.Position"
            if player_key in self.full_data:
                p_type, p_pos = ValueHandler.decode(self.full_data[player_key])
                
                # Extrai as coordenadas do player seja lá como o ES3 tiver salvo
                coords = {'x': 0, 'y': 0, 'z': 0}
                if isinstance(p_pos, list) and len(p_pos) >= 3:
                    coords = {'x': p_pos[0], 'y': p_pos[1], 'z': p_pos[2]}
                elif isinstance(p_pos, dict):
                    coords = {'x': p_pos.get('x', 0), 'y': p_pos.get('y', 0), 'z': p_pos.get('z', 0)}
                else:
                    messagebox.showerror("Error", "Formato de posição do Player desconhecido!")
                    return
                    
                apply_tp(coords)
            else:
                messagebox.showerror("Error", "Player não encontrado!")

        ctk.CTkButton(win, text="📍 To Player", fg_color="#3a7ebf", command=tp_to_player).pack(pady=10, padx=20, fill="x")

        # BOTÕES TP TARGET TO OTHER TARGET
        ctk.CTkButton(win, text="🏠 To House", command=lambda: apply_tp({'x': -115.0, 'y': 5.8, 'z': 76.7})).pack(pady=5, padx=20, fill="x")
        ctk.CTkButton(win, text="🏁 To Street Race", command=lambda: apply_tp({'x': -35.0, 'y': 20.0, 'z': -482.0})).pack(pady=5, padx=20, fill="x")
        ctk.CTkButton(win, text="⌨️ Edit Manually", fg_color="gray", 
                      command=lambda: [win.destroy(), self.edit_inline(item, "#1", full_key, v_type, clean_val)]).pack(pady=20)      

    def change_page(self, v):
        dom = self.get_current_domain()
        grps = list(self.categorized_groups[dom].keys())
        max_p = max(0, (len(grps)-1)//self.items_per_page)
        new_p = self.current_page[dom] + v
        if 0 <= new_p <= max_p:
            self.current_page[dom] = new_p
            self.update_current_tab()

    def on_tab_change(self): self.update_current_tab()

    def open_array_color_window(self, full_key):
        if self.active_color_win and self.active_color_win.winfo_exists():
            self.active_color_win.focus()
            return

        base_key = full_key.rsplit('[', 1)[0]
        
        # Pega os dados puros do JSON, ignorando o ValueHandler
        def get_raw_val(idx):
            k = f"{base_key}[{idx}]"
            return self.full_data.get(k)
            
        raw_vals = [get_raw_val(i) for i in range(4)]

        # --- 1. FUNÇÃO RAIO-X PARA EXTRAIR O NÚMERO À FORÇA ---
        def extract_num(v):
            if v is None: return None
            if isinstance(v, (int, float)): return float(v)
            if isinstance(v, str):
                try: return float(v)
                except: return None
            if isinstance(v, dict):
                # O ES3 às vezes esconde o número dentro de "value" sem avisar o tipo
                if "value" in v: return extract_num(v["value"])
                # Pega o primeiro valor que conseguir achar se não tiver a chave "value"
                for key, val in v.items():
                    res = extract_num(val)
                    if res is not None: return res
            return None

        r = extract_num(raw_vals[0])
        g = extract_num(raw_vals[1])
        b = extract_num(raw_vals[2])
        a = extract_num(raw_vals[3])

        # --- 2. DETECTA SE É FLOAT (0.0 - 1.0) ---
        def is_val_float(v):
            if isinstance(v, float): return True
            if isinstance(v, str) and '.' in v: return True
            if isinstance(v, dict): return any(is_val_float(val) for val in v.values())
            return False

        is_float = any(is_val_float(v) for v in raw_vals)

        # Preenche com padrão caso falte alguma cor no save
        r = r if r is not None else 0.0
        g = g if g is not None else 0.0
        b = b if b is not None else 0.0
        a = a if a is not None else (1.0 if is_float else 255.0)

        # --- 3. CONVERTE PRA INTERFACE DO TKINTER ---
        if is_float:
            ui_r = max(0, min(255, int(r * 255)))
            ui_g = max(0, min(255, int(g * 255)))
            ui_b = max(0, min(255, int(b * 255)))
        else:
            ui_r = max(0, min(255, int(r)))
            ui_g = max(0, min(255, int(g)))
            ui_b = max(0, min(255, int(b)))

        win = ctk.CTkToplevel(self)
        self.active_color_win = win
        win.title("Color Selector")
        win.geometry("350x450")
        win.attributes("-topmost", True)
        
        preview = ctk.CTkFrame(win, width=120, height=60, fg_color=f"#{ui_r:02x}{ui_g:02x}{ui_b:02x}", corner_radius=8)
        preview.pack(pady=30)

        def pick():
            res = colorchooser.askcolor(parent=win, initialcolor=preview.cget("fg_color"))
            c = res[0]
            if c and win.winfo_exists() and preview.winfo_exists():
                nonlocal r, g, b
                if is_float:
                    r, g, b = c[0]/255.0, c[1]/255.0, c[2]/255.0
                else:
                    r, g, b = int(c[0]), int(c[1]), int(c[2])
                
                preview.configure(fg_color=f"#{int(c[0]):02x}{int(c[1]):02x}{int(c[2]):02x}")

        ctk.CTkButton(win, text="Pick Color Palette", command=pick).pack(pady=10)
        
        lbl_text = "Alpha (0.0 to 1.0):" if is_float else "Alpha (0 to 255):"
        ctk.CTkLabel(win, text=lbl_text, font=("Segoe UI", 12)).pack(pady=(15, 0))
        
        ae = ctk.CTkEntry(win)
        ae.insert(0, str(round(a, 3)) if is_float else str(int(a)))
        ae.pack(pady=(5, 20))

        def save():
            try:
                new_a = float(ae.get()) if is_float else int(float(ae.get()))
                
                vals_to_save = [r, g, b, new_a]
                if not is_float:
                    vals_to_save = [int(v) for v in vals_to_save]
                
                for i, val in enumerate(vals_to_save):
                    k = f"{base_key}[{i}]"
                    original = raw_vals[i]
                    
                    # Se o JSON original era um dicionário (ex: {"value": 0.9}), injeta de volta sem quebrar a estrutura!
                    if original is not None and isinstance(original, dict) and "value" in original:
                        self.full_data[k]["value"] = val
                    else:
                        self.full_data[k] = val
                
                self.update_current_tab()
                win.destroy()
            except Exception as e:
                print(f"Erro ao salvar a cor: {e}")

        ctk.CTkButton(win, text="Apply Color", fg_color="#2e7d32", command=save).pack(pady=10)

    def open_list_color_window(self, item, full_key, clean_val):
        if hasattr(self, 'active_color_win') and self.active_color_win and self.active_color_win.winfo_exists():
            self.active_color_win.focus()
            return

        win = ctk.CTkToplevel(self)
        self.active_color_win = win
        win.title("Color Selector")
        win.geometry("350x450")
        win.attributes("-topmost", True)
        
        # Pega os valores da lista de forma segura
        r = float(clean_val[0]) if len(clean_val) > 0 else 0.0
        g = float(clean_val[1]) if len(clean_val) > 1 else 0.0
        b = float(clean_val[2]) if len(clean_val) > 2 else 0.0
        
        # Detecta se é float (0.0 a 1.0)
        is_float = any(isinstance(v, float) or (isinstance(v, str) and '.' in str(v)) for v in clean_val)
        
        a = float(clean_val[3]) if len(clean_val) > 3 else (1.0 if is_float else 255.0)

        # Converte para 0-255 apenas para a interface
        if is_float:
            ui_r = max(0, min(255, int(r * 255)))
            ui_g = max(0, min(255, int(g * 255)))
            ui_b = max(0, min(255, int(b * 255)))
        else:
            ui_r = max(0, min(255, int(r)))
            ui_g = max(0, min(255, int(g)))
            ui_b = max(0, min(255, int(b)))
        
        preview = ctk.CTkFrame(win, width=120, height=60, fg_color=f"#{ui_r:02x}{ui_g:02x}{ui_b:02x}", corner_radius=8)
        preview.pack(pady=30)
        
        def pick():
            res = colorchooser.askcolor(parent=win, initialcolor=preview.cget("fg_color"))
            c = res[0]
            if c and win.winfo_exists() and preview.winfo_exists():
                nonlocal r, g, b
                if is_float:
                    r, g, b = c[0]/255.0, c[1]/255.0, c[2]/255.0
                else:
                    r, g, b = int(c[0]), int(c[1]), int(c[2])
                preview.configure(fg_color=f"#{int(c[0]):02x}{int(c[1]):02x}{int(c[2]):02x}")
                
        ctk.CTkButton(win, text="Pick Color Palette", command=pick).pack(pady=10)
        
        lbl_text = "Alpha (0.0 to 1.0):" if is_float else "Alpha (0 to 255):"
        ctk.CTkLabel(win, text=lbl_text, font=("Segoe UI", 12)).pack(pady=(15, 0))

        ae = ctk.CTkEntry(win)
        ae.insert(0, str(round(a, 3)) if is_float else str(int(a)))
        ae.pack(pady=(5, 20))
        
        def save():
            try:
                new_a = float(ae.get()) if is_float else int(float(ae.get()))
                
                new_list = [r, g, b, new_a]
                if not is_float:
                    new_list = [int(v) for v in new_list]
                
                self.save_direct_value(item, full_key, "UNKNOWN", new_list)
                win.destroy()
            except Exception as e:
                print(f"Erro ao salvar a cor em lista: {e}")
            
        ctk.CTkButton(win, text="Apply Color", fg_color="#2e7d32", command=save).pack(pady=20)

    def on_item_double_click(self, event):
        dom = self.get_current_domain()
        t = self.trees[dom]
        item = t.identify_row(event.y)
        col = t.identify_column(event.x)
        if not item or col != "#1": return

        full_key = t.item(item, "tags")[0]
        v_type, clean_val = ValueHandler.decode(self.full_data[full_key])

        # --- CASO 1: Chave é dividida (ex: "ItemColor[0]", "Colors[1]", "Body Color [0]")
        if "color" in full_key.lower() and "[" in full_key and full_key.endswith("]"):
            self.open_array_color_window(full_key)
            return

        # --- CASO 2: Chave é única e o valor é uma lista (ex: "BodyColor" -> [255, 128, 0, 255])
        if "color" in full_key.lower() and isinstance(clean_val, list) and len(clean_val) >= 3:
            self.open_list_color_window(item, full_key, clean_val)
            return

        # --- CASO 3: Teleporte (Vetores ou qualquer chave que tenha "position") ---
        if (v_type and "Vector" in str(v_type)) or ("position" in full_key.lower()):
            self.open_teleport_window(item, full_key, v_type, clean_val)
            return
        
        # --- Resto do código normal ---
        if v_type == "bool" or isinstance(clean_val, bool):
            self.save_direct_value(item, full_key, v_type, not clean_val)
        elif v_type and "color" in str(v_type).lower():
            self.open_color_window(item, full_key, v_type, clean_val)
        elif v_type and "Vector" in str(v_type):
            self.open_teleport_window(item, full_key, v_type, clean_val)
        else:
            self.edit_inline(item, col, full_key, v_type, clean_val)

    def edit_inline(self, item, column, full_key, v_type, clean_val):
        dom = self.get_current_domain()
        t = self.trees[dom]
        x, y, w, h = t.bbox(item, column)
        entry = ctk.CTkEntry(t, width=w, height=h, border_width=1, corner_radius=0, fg_color="#333333")
        entry.insert(0, str(clean_val))
        entry.place(x=x, y=y)
        entry.focus_set()

        def confirm(e=None):
            val = entry.get()
            try:
                if val.lower() == 'true': 
                    res = True
                elif val.lower() == 'false': 
                    res = False
                else:
                    try:
                        res = int(val)
                    except ValueError:
                        try:
                            res = float(val)
                        except ValueError:
                            res = val

                self.save_direct_value(item, full_key, v_type, res)
                entry.destroy()
            except Exception as ex:
                print(f"Erro ao salvar valor: {ex}") 
                entry.configure(border_color="red")

        entry.bind("<Return>", confirm)
        entry.bind("<FocusOut>", lambda e: entry.destroy())
        entry.bind("<Escape>", lambda e: entry.destroy())

    def save_direct_value(self, item, full_key, v_type, new_val):
        dom = self.get_current_domain()
        t = self.trees[dom]
        
        # Se o valor original já era um dicionário (ex: {"__type": "Color"...}), mantemos a estrutura!
        if isinstance(self.full_data[full_key], dict) and ("__type" in self.full_data[full_key] or "_type" in self.full_data[full_key]):
            self.full_data[full_key]["value"] = new_val
        else:
            # Se era um valor direto (int, float, array puro), salvamos ele de forma pura!
            self.full_data[full_key] = new_val
            
        t.item(item, values=(ValueHandler.to_readable(self.full_data[full_key]),))

    def open_color_window(self, item, full_key, v_type, clean_val):
        win = ctk.CTkToplevel(self)
        win.title("Color Selector")
        win.geometry("350x450")
        win.attributes("-topmost", True)
        
        r, g, b = [max(0, min(255, int(clean_val.get(c, 0) * 255))) for c in 'rgb']
        preview = ctk.CTkFrame(win, width=120, height=60, fg_color=f"#{r:02x}{g:02x}{b:02x}", corner_radius=8)
        preview.pack(pady=30)

        def pick():
            res = colorchooser.askcolor(parent=win, initialcolor=preview.cget("fg_color"))
            c = res[0]
            if c and win.winfo_exists() and preview.winfo_exists():
                for i, axis in enumerate('rgb'): 
                    clean_val[axis] = c[i]/255
                preview.configure(fg_color=f"#{int(c[0]):02x}{int(c[1]):02x}{int(c[2]):02x}")

        ctk.CTkButton(win, text="Pick Color Palette", command=pick).pack(pady=10)
        ae = ctk.CTkEntry(win, placeholder_text="Alpha (0-1)")
        ae.insert(0, str(clean_val.get('a', 1)))
        ae.pack(pady=20)

        def save():
            try:
                clean_val['a'] = float(ae.get())
                self.save_direct_value(item, full_key, v_type, clean_val)
                win.destroy()
            except: pass
        ctk.CTkButton(win, text="Apply Color", fg_color="#2e7d32", command=save).pack(pady=20)

    def save_file(self):
        if not self.full_data: return
        p = filedialog.asksaveasfilename(initialdir=self.default_path, defaultextension=".save")
        if p:
            try:
                content = json.dumps(self.full_data, separators=(',', ':')).encode('utf-8')
                with gzip.open(p, 'wb') as f: 
                    f.write(content)
                messagebox.showinfo("Success", "Saved!")
            except Exception as e: 
                messagebox.showerror("Error", str(e))

if __name__ == "__main__":
    app = MSLPEditor()
    app.mainloop()
