# ui_login.py - FiscalFlow — Tela de login e painel de administração
# Tema: Degradê azul moderno com botões arredondados via Canvas

import tkinter as tk
from tkinter import ttk, messagebox


# ─── Paleta FiscalFlow ────────────────────────────────────────────────────────
CORES = {
    "bg_primario":      "#0A0F1E",   # Azul muito escuro (quase preto)
    "bg_secundario":    "#0F1729",   # Azul escuro — painéis
    "bg_card":          "#141E35",   # Card de login
    "bg_campo":         "#1C2A45",   # Campos de entrada
    "borda":            "#2A3F6F",   # Bordas sutis azuladas
    "borda_foco":       "#4A7FE0",   # Borda em foco

    "azul1":            "#1565C0",   # Azul escuro do degradê
    "azul2":            "#1E88E5",   # Azul médio
    "azul3":            "#42A5F5",   # Azul claro
    "azul_accent":      "#64B5F6",   # Azul destaque suave
    "cyan_accent":      "#00B4D8",   # Ciano para detalhes

    "verde":            "#00C896",   # Sucesso
    "vermelho":         "#FF4757",   # Erro
    "amarelo_warn":     "#FFD60A",   # Aviso

    "texto_primario":   "#E8F0FE",   # Branco azulado
    "texto_secundario": "#7B9DC8",   # Azul acinzentado
    "texto_muted":      "#4A6080",   # Texto apagado
}


# ─── Botão arredondado via Canvas ─────────────────────────────────────────────

class RoundedButton(tk.Canvas):
    """Botão com cantos arredondados e efeito hover via Canvas."""

    def __init__(self, parent, text, command=None,
                 bg_normal=None, bg_hover=None, fg="#FFFFFF",
                 font=("Segoe UI", 10, "bold"),
                 radius=12, width=200, height=44, **kwargs):

        super().__init__(parent,
                         width=width, height=height,
                         bg=parent.cget("bg"), highlightthickness=0,
                         cursor="hand2", **kwargs)

        self._text = text
        self._command = command
        self._bg_normal = bg_normal or CORES["azul2"]
        self._bg_hover   = bg_hover  or CORES["azul3"]
        self._fg = fg
        self._font = font
        self._radius = radius
        self._btn_w = width   # CORREÇÃO: Variável renomeada
        self._btn_h = height  # CORREÇÃO: Variável renomeada
        self._hovered = False
        self._disabled = False

        self.bind("<Enter>",    self._on_enter)
        self.bind("<Leave>",    self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self.after_idle(lambda: self._draw(self._bg_normal))

    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        """Desenha retângulo com cantos arredondados."""
        pts = [
            x1+r, y1,
            x2-r, y1,
            x2,   y1,
            x2,   y1+r,
            x2,   y2-r,
            x2,   y2,
            x2-r, y2,
            x1+r, y2,
            x1,   y2,
            x1,   y2-r,
            x1,   y1+r,
            x1,   y1,
        ]
        return self.create_polygon(pts, smooth=True, **kw)

    def _draw(self, color):
        self.delete("all")
        self._round_rect(2, 2, self._btn_w-2, self._btn_h-2,
                         self._radius, fill=color, outline="")
        self.create_text(
            self._btn_w // 2, self._btn_h // 2,
            text=self._text, fill=self._fg,
            font=self._font, anchor="center"
        )

    def _on_enter(self, _=None):
        if not self._disabled:
            self._draw(self._bg_hover)

    def _on_leave(self, _=None):
        if not self._disabled:
            self._draw(self._bg_normal)

    def _on_click(self, _=None):
        if not self._disabled and self._command:
            self._command()

    def config_state(self, disabled: bool, text=None):
        self._disabled = disabled
        if text:
            self._text = text
        if disabled:
            self._draw(CORES["borda"])
        else:
            self._draw(self._bg_normal)

    def set_text(self, text):
        self._text = text
        self._draw(self._bg_normal if not self._disabled else CORES["borda"])


# ─── Campo de entrada customizado ────────────────────────────────────────────

class StyledEntry(tk.Frame):
    """Campo de entrada com borda arredondada e animação de foco."""

    def __init__(self, parent, placeholder="", show="", **kwargs):
        super().__init__(parent,
                         bg=CORES["bg_campo"],
                         highlightbackground=CORES["borda"],
                         highlightthickness=1,
                         **kwargs)

        self._show = show
        self._placeholder = placeholder

        self.entry = tk.Entry(
            self,
            font=("Segoe UI", 11),
            bg=CORES["bg_campo"],
            fg=CORES["texto_primario"],
            insertbackground=CORES["azul3"],
            relief="flat", bd=0,
            show=show,
        )
        self.entry.pack(fill="x", ipady=11, padx=14)
        self.entry.bind("<FocusIn>",  self._on_focus)
        self.entry.bind("<FocusOut>", self._off_focus)

    def _on_focus(self, _=None):
        self.config(highlightbackground=CORES["borda_foco"],
                    highlightthickness=2)

    def _off_focus(self, _=None):
        self.config(highlightbackground=CORES["borda"],
                    highlightthickness=1)

    def get(self): return self.entry.get()
    def delete(self, a, b): self.entry.delete(a, b)
    def insert(self, idx, val): self.entry.insert(idx, val)
    def bind(self, seq, func, add=None):
        # Delegate key binds to inner entry
        if seq.startswith("<Key") or seq == "<Return>":
            self.entry.bind(seq, func, add)
        else:
            super().bind(seq, func, add)
    def focus(self): self.entry.focus()
    def config_show(self, show): self.entry.config(show=show)


# ─── Separador com linha decorativa ──────────────────────────────────────────

def _linha_decorativa(parent, cor=None):
    c = cor or CORES["borda"]
    f = tk.Frame(parent, bg=c, height=1)
    f.pack(fill="x", pady=8)


# ─── Tela de Login ────────────────────────────────────────────────────────────

class LoginDialog(tk.Tk):
    """Janela de login FiscalFlow com tema azul moderno."""

    def __init__(self):
        super().__init__()
        self.title("FiscalFlow  •  Login")
        self.configure(bg=CORES["bg_primario"])
        self.resizable(False, False)
        self.usuario_logado = None

        self._construir()
        self._centralizar()
        self.protocol("WM_DELETE_WINDOW", self._fechar)

    def _centralizar(self):
        self.update_idletasks()
        w, h = 440, 560
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    def _construir(self):
        # ── Faixa superior degradê ────────────────────────────────────────────
        header = tk.Canvas(self, height=90, bg=CORES["bg_primario"],
                           highlightthickness=0)
        header.pack(fill="x")
        self._desenhar_header(header)

        # ── Linha ciano ───────────────────────────────────────────────────────
        tk.Frame(self, bg=CORES["cyan_accent"], height=2).pack(fill="x")

        # ── Card central ──────────────────────────────────────────────────────
        card = tk.Frame(self, bg=CORES["bg_card"],
                        highlightbackground=CORES["borda"],
                        highlightthickness=1)
        card.pack(fill="both", expand=True, padx=32, pady=24)

        # Boas-vindas
        tk.Label(card, text="Bem-vindo de volta",
                 font=("Segoe UI", 17, "bold"),
                 bg=CORES["bg_card"], fg=CORES["texto_primario"]
                 ).pack(pady=(28, 4))

        tk.Label(card, text="Faça login para acessar o sistema",
                 font=("Segoe UI", 10),
                 bg=CORES["bg_card"], fg=CORES["texto_secundario"]
                 ).pack(pady=(0, 24))

        # Campo usuário
        self._label_campo(card, "Usuário")
        self._ef_user = StyledEntry(card)
        self._ef_user.pack(fill="x", padx=24, pady=(4, 16))

        # Campo senha
        self._label_campo(card, "Senha")
        self._ef_senha = StyledEntry(card, show="●")
        self._ef_senha.pack(fill="x", padx=24, pady=(4, 4))

        # Mostrar senha
        self._var_mostrar = tk.BooleanVar(value=False)
        chk_frame = tk.Frame(card, bg=CORES["bg_card"])
        chk_frame.pack(fill="x", padx=24, pady=(4, 0))
        tk.Checkbutton(
            chk_frame, text="  Mostrar senha",
            variable=self._var_mostrar,
            font=("Segoe UI", 9),
            bg=CORES["bg_card"], fg=CORES["texto_secundario"],
            selectcolor=CORES["bg_campo"],
            activebackground=CORES["bg_card"],
            cursor="hand2",
            command=self._toggle_senha,
        ).pack(side="left")

        # Label de erro
        self._lbl_erro = tk.Label(
            card, text="",
            font=("Segoe UI", 9),
            bg=CORES["bg_card"], fg=CORES["vermelho"]
        )
        self._lbl_erro.pack(pady=(12, 4))

        # Botão entrar
        btn_frame = tk.Frame(card, bg=CORES["bg_card"])
        btn_frame.pack(fill="x", padx=24, pady=(4, 24))

        self._btn_entrar = RoundedButton(
            btn_frame,
            text="ENTRAR",
            command=self._tentar_login,
            bg_normal=CORES["azul1"],
            bg_hover=CORES["azul2"],
            fg=CORES["texto_primario"],
            font=("Segoe UI", 11, "bold"),
            radius=14, height=48,
        )
        self._btn_entrar.pack(fill="x")

        # Binds
        self._ef_user.entry.bind("<Return>", lambda e: self._ef_senha.focus())
        self._ef_senha.entry.bind("<Return>", lambda e: self._tentar_login())
        self._ef_user.focus()

        # ── Rodapé ────────────────────────────────────────────────────────────
        tk.Frame(self, bg=CORES["bg_secundario"], height=36).pack(fill="x", side="bottom")
        tk.Label(self, text="FiscalFlow v2.0  •  Gestão de Notas Fiscais",
                 font=("Segoe UI", 8),
                 bg=CORES["bg_secundario"], fg=CORES["texto_muted"]
                 ).place(relx=0.5, rely=1.0, anchor="s", y=-10)

    def _desenhar_header(self, canvas):
        """Desenha o cabeçalho com texto estilizado."""
        canvas.update_idletasks()
        w = canvas.winfo_reqwidth() or 440

        # Fundo degradê manual (simulado com retângulos)
        for i in range(90):
            r = int(0x0A + (0x15 - 0x0A) * i / 90)
            g = int(0x0F + (0x26 - 0x0F) * i / 90)
            b = int(0x1E + (0x4A - 0x1E) * i / 90)
            cor = f"#{r:02x}{g:02x}{b:02x}"
            canvas.create_rectangle(0, i, w, i+1, fill=cor, outline="")

        # Ícone ✦ e nome
        canvas.create_text(30, 45, text="✦",
                            font=("Segoe UI", 22), fill=CORES["cyan_accent"],
                            anchor="w")
        canvas.create_text(60, 38, text="FiscalFlow",
                            font=("Segoe UI", 22, "bold"),
                            fill=CORES["texto_primario"], anchor="w")
        canvas.create_text(62, 62, text="AUTOMAÇÃO LOGÍSTICA  •  CONTROLE DE NOTAS",
                            font=("Segoe UI", 8),
                            fill=CORES["texto_secundario"], anchor="w")

    def _label_campo(self, parent, texto):
        tk.Label(parent, text=texto,
                 font=("Segoe UI", 9, "bold"),
                 bg=CORES["bg_card"], fg=CORES["texto_secundario"],
                 anchor="w").pack(fill="x", padx=24)

    def _toggle_senha(self):
        self._ef_senha.config_show("" if self._var_mostrar.get() else "●")

    def _tentar_login(self):
        from auth import autenticar
        username = self._ef_user.get().strip()
        senha = self._ef_senha.get()

        if not username or not senha:
            self._lbl_erro.config(text="⚠  Preencha usuário e senha.")
            return

        self._btn_entrar.config_state(True, text="Verificando...")
        self.update()

        usuario = autenticar(username, senha)

        if usuario:
            self.usuario_logado = usuario
            self.destroy()
        else:
            self._lbl_erro.config(text="✕  Usuário ou senha incorretos.")
            self._ef_senha.delete(0, "end")
            self._btn_entrar.config_state(False, text="ENTRAR")

    def _fechar(self):
        self.usuario_logado = None
        self.destroy()


# ─── Painel de Administração ──────────────────────────────────────────────────

class PainelAdmin(tk.Toplevel):
    """Janela de administração de usuários e histórico — tema FiscalFlow."""

    def __init__(self, parent, usuario_logado: dict):
        super().__init__(parent)
        self.title("FiscalFlow  •  Administração")
        self.configure(bg=CORES["bg_primario"])
        self.geometry("780x520")
        self.minsize(700, 440)
        self._usuario_logado = usuario_logado
        self.grab_set()

        self._configurar_estilos()
        self._construir()

    def _configurar_estilos(self):
        s = ttk.Style(self)
        s.theme_use("clam")

        # Notebook
        s.configure("Admin.TNotebook",
                     background=CORES["bg_primario"], borderwidth=0)
        s.configure("Admin.TNotebook.Tab",
                     background=CORES["bg_secundario"],
                     foreground=CORES["texto_secundario"],
                     padding=[18, 9],
                     font=("Segoe UI", 10, "bold"),
                     borderwidth=0)
        s.map("Admin.TNotebook.Tab",
              background=[("selected", CORES["bg_card"])],
              foreground=[("selected", CORES["azul3"])])

        # Treeview
        s.configure("Admin.Treeview",
                     background=CORES["bg_secundario"],
                     fieldbackground=CORES["bg_secundario"],
                     foreground=CORES["texto_primario"],
                     borderwidth=0, rowheight=26,
                     font=("Segoe UI", 9))
        s.configure("Admin.Treeview.Heading",
                     background=CORES["bg_campo"],
                     foreground=CORES["azul3"],
                     font=("Segoe UI", 9, "bold"),
                     borderwidth=0)
        s.map("Admin.Treeview",
              background=[("selected", CORES["azul1"])],
              foreground=[("selected", "#FFFFFF")])

        # Combobox
        s.configure("Admin.TCombobox",
                     fieldbackground=CORES["bg_campo"],
                     background=CORES["bg_campo"],
                     foreground=CORES["texto_primario"],
                     arrowcolor=CORES["azul3"],
                     bordercolor=CORES["borda"],
                     selectbackground=CORES["bg_campo"],
                     selectforeground=CORES["texto_primario"])
        s.map("Admin.TCombobox",
              fieldbackground=[("readonly", CORES["bg_campo"])],
              foreground=[("readonly", CORES["texto_primario"])])

    def _construir(self):
        # Cabeçalho
        cab = tk.Frame(self, bg=CORES["bg_card"], height=56)
        cab.pack(fill="x")
        cab.pack_propagate(False)
        tk.Label(cab, text="✦  Painel de Administração",
                 font=("Segoe UI", 14, "bold"),
                 bg=CORES["bg_card"], fg=CORES["texto_primario"]
                 ).pack(side="left", padx=20, pady=14)
        tk.Label(cab,
                 text=f"Logado como: {self._usuario_logado['username']}",
                 font=("Segoe UI", 9),
                 bg=CORES["bg_card"], fg=CORES["texto_secundario"]
                 ).pack(side="right", padx=20)

        tk.Frame(self, bg=CORES["cyan_accent"], height=2).pack(fill="x")

        # Notebook
        nb = ttk.Notebook(self, style="Admin.TNotebook")
        nb.pack(fill="both", expand=True, padx=0, pady=0)

        a1 = tk.Frame(nb, bg=CORES["bg_primario"])
        nb.add(a1, text="  👥  Usuários  ")
        self._construir_aba_usuarios(a1)

        a2 = tk.Frame(nb, bg=CORES["bg_primario"])
        nb.add(a2, text="  📋  Histórico  ")
        self._construir_aba_historico(a2)

    # ── Aba Usuários ──────────────────────────────────────────────────────────

    def _construir_aba_usuarios(self, parent):
        # Toolbar
        bar = tk.Frame(parent, bg=CORES["bg_secundario"], height=52)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        for txt, cmd, bg, hov in [
            ("＋  Novo Usuário",      self._dlg_novo_usuario,   CORES["azul1"],   CORES["azul2"]),
            ("🔑  Redefinir Senha",   self._dlg_redefinir_senha,CORES["bg_campo"],CORES["borda"]),
            ("✕  Excluir Usuário",    self._excluir_usuario,    "#5C1A1A",        "#8B2222"),
        ]:
            RoundedButton(bar, text=txt, command=cmd,
                          bg_normal=bg, bg_hover=hov,
                          fg=CORES["texto_primario"],
                          font=("Segoe UI", 9, "bold"),
                          radius=10, width=160, height=34
                          ).pack(side="left", padx=(12, 0), pady=9)

        # Treeview
        frame_tree = tk.Frame(parent, bg=CORES["bg_primario"])
        frame_tree.pack(fill="both", expand=True, padx=12, pady=10)

        cols = ("username", "perfil", "criado_em", "criado_por")
        self._tree_users = ttk.Treeview(
            frame_tree, columns=cols, show="headings",
            style="Admin.Treeview", height=12
        )
        for col, titulo, larg in [
            ("username",  "Usuário",     180),
            ("perfil",    "Perfil",      100),
            ("criado_em", "Criado em",   160),
            ("criado_por","Criado por",  160),
        ]:
            self._tree_users.heading(col, text=titulo)
            self._tree_users.column(col, width=larg, anchor="w")

        sb = tk.Scrollbar(frame_tree, orient="vertical",
                          command=self._tree_users.yview,
                          bg=CORES["bg_campo"], troughcolor=CORES["bg_secundario"])
        self._tree_users.configure(yscrollcommand=sb.set)
        self._tree_users.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self._carregar_usuarios()

    def _carregar_usuarios(self):
        from auth import listar_usuarios
        for row in self._tree_users.get_children():
            self._tree_users.delete(row)
        for u in listar_usuarios():
            self._tree_users.insert("", "end",
                values=(u["username"], u["perfil"],
                        u["criado_em"], u["criado_por"]))

    def _usuario_selecionado(self):
        sel = self._tree_users.selection()
        if not sel:
            messagebox.showwarning("Atenção", "Selecione um usuário.", parent=self)
            return ""
        return self._tree_users.item(sel[0])["values"][0]

    def _dlg_novo_usuario(self):
        dlg = tk.Toplevel(self)
        dlg.title("Novo Usuário")
        dlg.configure(bg=CORES["bg_primario"])
        dlg.resizable(False, False)
        dlg.geometry("380x370")
        dlg.grab_set()

        tk.Label(dlg, text="Criar Novo Usuário",
                 font=("Segoe UI", 13, "bold"),
                 bg=CORES["bg_primario"], fg=CORES["texto_primario"]
                 ).pack(pady=(20, 16))

        tk.Frame(dlg, bg=CORES["cyan_accent"], height=1).pack(fill="x", padx=24)

        def campo(label, show=""):
            tk.Label(dlg, text=label, font=("Segoe UI", 9, "bold"),
                     bg=CORES["bg_primario"], fg=CORES["texto_secundario"],
                     anchor="w").pack(fill="x", padx=24, pady=(12, 2))
            e = StyledEntry(dlg, show=show)
            e.pack(fill="x", padx=24)
            return e

        e_user  = campo("Usuário")
        e_senha = campo("Senha", show="●")
        e_conf  = campo("Confirmar Senha", show="●")

        tk.Label(dlg, text="Perfil", font=("Segoe UI", 9, "bold"),
                 bg=CORES["bg_primario"], fg=CORES["texto_secundario"],
                 anchor="w").pack(fill="x", padx=24, pady=(12, 2))
        var_perfil = tk.StringVar(value="operador")
        fr = tk.Frame(dlg, bg=CORES["bg_primario"])
        fr.pack(anchor="w", padx=24)
        for val, txt in [("operador", "Operador"), ("admin", "Administrador")]:
            tk.Radiobutton(fr, text=txt, variable=var_perfil, value=val,
                           font=("Segoe UI", 9), bg=CORES["bg_primario"],
                           fg=CORES["texto_primario"],
                           selectcolor=CORES["bg_campo"],
                           activebackground=CORES["bg_primario"],
                           cursor="hand2").pack(side="left", padx=(0, 16))

        lbl_err = tk.Label(dlg, text="", font=("Segoe UI", 9),
                           bg=CORES["bg_primario"], fg=CORES["vermelho"])
        lbl_err.pack(pady=(8, 0))

        def _salvar():
            from auth import criar_usuario
            u = e_user.get().strip()
            s = e_senha.get()
            c = e_conf.get()
            if s != c:
                lbl_err.config(text="As senhas não coincidem."); return
            ok, msg = criar_usuario(u, s, var_perfil.get(),
                                    self._usuario_logado["username"])
            if ok:
                messagebox.showinfo("Sucesso", f"Usuário '{u}' criado!", parent=dlg)
                dlg.destroy()
                self._carregar_usuarios()
            else:
                lbl_err.config(text=msg)

        btn_f = tk.Frame(dlg, bg=CORES["bg_primario"])
        btn_f.pack(fill="x", padx=24, pady=(8, 16))
        RoundedButton(btn_f, text="CRIAR USUÁRIO", command=_salvar,
                      bg_normal=CORES["azul1"], bg_hover=CORES["azul2"],
                      fg=CORES["texto_primario"],
                      font=("Segoe UI", 10, "bold"),
                      radius=12, height=42).pack(fill="x")

    def _dlg_redefinir_senha(self):
        username = self._usuario_selecionado()
        if not username:
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"Redefinir senha — {username}")
        dlg.configure(bg=CORES["bg_primario"])
        dlg.resizable(False, False)
        dlg.geometry("360x260")
        dlg.grab_set()

        tk.Label(dlg, text=f"Nova senha para: {username}",
                 font=("Segoe UI", 11, "bold"),
                 bg=CORES["bg_primario"], fg=CORES["azul3"]
                 ).pack(pady=(20, 12))

        def campo(label):
            tk.Label(dlg, text=label, font=("Segoe UI", 9, "bold"),
                     bg=CORES["bg_primario"], fg=CORES["texto_secundario"],
                     anchor="w").pack(fill="x", padx=24, pady=(8, 2))
            e = StyledEntry(dlg, show="●")
            e.pack(fill="x", padx=24)
            return e

        e_nova = campo("Nova Senha")
        e_conf = campo("Confirmar")

        lbl_err = tk.Label(dlg, text="", font=("Segoe UI", 9),
                           bg=CORES["bg_primario"], fg=CORES["vermelho"])
        lbl_err.pack(pady=(6, 0))

        def _salvar():
            from auth import redefinir_senha_admin
            if e_nova.get() != e_conf.get():
                lbl_err.config(text="As senhas não coincidem."); return
            ok, msg = redefinir_senha_admin(
                username, e_nova.get(), self._usuario_logado["username"]
            )
            if ok:
                messagebox.showinfo("Sucesso", "Senha redefinida!", parent=dlg)
                dlg.destroy()
            else:
                lbl_err.config(text=msg)

        btn_f = tk.Frame(dlg, bg=CORES["bg_primario"])
        btn_f.pack(fill="x", padx=24, pady=(8, 16))
        RoundedButton(btn_f, text="SALVAR", command=_salvar,
                      bg_normal=CORES["azul1"], bg_hover=CORES["azul2"],
                      fg=CORES["texto_primario"],
                      font=("Segoe UI", 10, "bold"),
                      radius=12, height=42).pack(fill="x")

    def _excluir_usuario(self):
        username = self._usuario_selecionado()
        if not username:
            return
        if not messagebox.askyesno(
            "Confirmar",
            f"Excluir o usuário '{username}'?\nEsta ação não pode ser desfeita.",
            parent=self
        ):
            return
        from auth import excluir_usuario
        ok, msg = excluir_usuario(username, self._usuario_logado["username"])
        if ok:
            self._carregar_usuarios()
        else:
            messagebox.showerror("Erro", msg, parent=self)

    # ── Aba Histórico ─────────────────────────────────────────────────────────

    def _construir_aba_historico(self, parent):
        filtro = tk.Frame(parent, bg=CORES["bg_secundario"], height=48)
        filtro.pack(fill="x")
        filtro.pack_propagate(False)

        tk.Label(filtro, text="Filtrar por usuário:",
                 font=("Segoe UI", 9), bg=CORES["bg_secundario"],
                 fg=CORES["texto_secundario"]).pack(side="left", padx=(16, 8), pady=14)

        self._var_filtro_hist = tk.StringVar(value="(todos)")
        self._combo_filtro = ttk.Combobox(
            filtro, textvariable=self._var_filtro_hist,
            state="readonly", width=20,
            font=("Segoe UI", 9), style="Admin.TCombobox"
        )
        self._combo_filtro.pack(side="left", pady=12)
        self._combo_filtro.bind("<<ComboboxSelected>>",
                                lambda e: self._carregar_historico())

        RoundedButton(filtro, text="↻  Atualizar",
                      command=self._carregar_historico,
                      bg_normal=CORES["bg_campo"], bg_hover=CORES["borda"],
                      fg=CORES["texto_secundario"],
                      font=("Segoe UI", 9), radius=8,
                      width=110, height=30).pack(side="left", padx=10, pady=10)

        frame_tree = tk.Frame(parent, bg=CORES["bg_primario"])
        frame_tree.pack(fill="both", expand=True, padx=12, pady=10)

        cols = ("data_hora", "usuario", "operacao", "detalhes")
        self._tree_hist = ttk.Treeview(
            frame_tree, columns=cols, show="headings",
            style="Admin.Treeview", height=14
        )
        for col, titulo, larg in [
            ("data_hora", "Data/Hora",   150),
            ("usuario",   "Usuário",     110),
            ("operacao",  "Operação",    160),
            ("detalhes",  "Detalhes",    360),
        ]:
            self._tree_hist.heading(col, text=titulo)
            self._tree_hist.column(col, width=larg, anchor="w")

        sb = tk.Scrollbar(frame_tree, orient="vertical",
                          command=self._tree_hist.yview,
                          bg=CORES["bg_campo"])
        self._tree_hist.configure(yscrollcommand=sb.set)
        self._tree_hist.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self._carregar_historico()

    def _carregar_historico(self):
        from auth import consultar_historico, listar_usuarios
        for row in self._tree_hist.get_children():
            self._tree_hist.delete(row)

        usuarios = ["(todos)"] + [u["username"] for u in listar_usuarios()]
        self._combo_filtro.config(values=usuarios)

        filtro = self._var_filtro_hist.get()
        usuario_filtro = None if filtro == "(todos)" else filtro

        for h in consultar_historico(usuario=usuario_filtro):
            self._tree_hist.insert("", "end", values=(
                h["data_hora"], h["usuario"], h["operacao"], h["detalhes"]
            ))