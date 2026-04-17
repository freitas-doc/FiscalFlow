# ui.py - FiscalFlow — Interface principal com tema azul moderno
# Botões arredondados via Canvas, degradês em tons de azul

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import queue
from typing import Optional

from config import OPCOES_ORGANIZACAO
from organizer import organizar_lote
from lote_splitter import processar_capas_de_lote
from ui_print_tab import construir_aba_impressao
from auth import registrar_operacao

# ─── Paleta FiscalFlow ────────────────────────────────────────────────────────
CORES = {
    "bg_primario":      "#0A0F1E",
    "bg_secundario":    "#0F1729",
    "bg_card":          "#141E35",
    "bg_campo":         "#1C2A45",
    "borda":            "#2A3F6F",
    "borda_foco":       "#4A7FE0",

    "azul1":            "#1565C0",
    "azul2":            "#1E88E5",
    "azul3":            "#42A5F5",
    "azul_accent":      "#64B5F6",
    "cyan_accent":      "#00B4D8",
    "destaque":         "#00B4D8",

    "verde":            "#00C896",
    "vermelho":         "#FF4757",
    "amarelo_warn":     "#FFD60A",

    "texto_primario":   "#E8F0FE",
    "texto_secundario": "#7B9DC8",
    "texto_muted":      "#4A6080",
    "texto_log":        "#B0C8E8",

    "barra_prog":       "#1E88E5",
    "barra_prog2":      "#00B4D8",
}

FONTE_TITULO   = ("Segoe UI", 14, "bold")
FONTE_CAMPO    = ("Consolas", 10)
FONTE_BOTAO    = ("Segoe UI", 11, "bold")
FONTE_BTN_PEQN = ("Segoe UI", 9)
FONTE_LABEL    = ("Segoe UI", 10)
FONTE_LOG      = ("Consolas", 9)
FONTE_STATUS   = ("Segoe UI", 9)


# ─── Botão arredondado via Canvas ─────────────────────────────────────────────

class RoundedButton(tk.Canvas):
    def __init__(self, parent, text, command=None,
                 bg_normal=None, bg_hover=None, fg="#FFFFFF",
                 font=("Segoe UI", 10, "bold"),
                 radius=12, width=200, height=44, **kwargs):
        super().__init__(parent, width=width, height=height,
                         bg=parent.cget("bg"), highlightthickness=0,
                         cursor="hand2", **kwargs)
        self._text     = text
        self._command  = command
        self._bg_normal = bg_normal or CORES["azul2"]
        self._bg_hover  = bg_hover  or CORES["azul3"]
        self._fg       = fg
        self._font     = font
        self._radius   = radius
        self._btn_w    = width    # CORREÇÃO: Variável renomeada
        self._btn_h    = height   # CORREÇÃO: Variável renomeada
        self._disabled = False

        self._draw(self._bg_normal)
        self.bind("<Enter>",    self._on_enter)
        self.bind("<Leave>",    self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        pts = [x1+r,y1, x2-r,y1, x2,y1, x2,y1+r, x2,y2-r, x2,y2,
               x2-r,y2, x1+r,y2, x1,y2, x1,y2-r, x1,y1+r, x1,y1]
        return self.create_polygon(pts, smooth=True, **kw)

    def _draw(self, color):
        self.delete("all")
        self._round_rect(2, 2, self._btn_w-2, self._btn_h-2,
                         self._radius, fill=color, outline="")
        self.create_text(self._btn_w//2, self._btn_h//2,
                         text=self._text, fill=self._fg,
                         font=self._font, anchor="center")

    def _on_enter(self, _=None):
        if not self._disabled: self._draw(self._bg_hover)

    def _on_leave(self, _=None):
        if not self._disabled: self._draw(self._bg_normal)

    def _on_click(self, _=None):
        if not self._disabled and self._command:
            self._command()

    def config_state(self, disabled: bool, text=None):
        self._disabled = disabled
        if text: self._text = text
        self._draw(CORES["borda"] if disabled else self._bg_normal)

    def set_text(self, text):
        self._text = text
        self._draw(self._bg_normal if not self._disabled else CORES["borda"])

    def config(self, **kwargs):
        # Compatibilidade: remap state/bg/fg para nossos atributos
        if "state" in kwargs:
            disabled = kwargs["state"] == "disabled"
            self.config_state(disabled)
        if "text" in kwargs:
            self.set_text(kwargs["text"])
        if "bg" in kwargs:
            self._bg_normal = kwargs["bg"]
            if not self._disabled: self._draw(self._bg_normal)
        if "fg" in kwargs:
            self._fg = kwargs["fg"]
            if not self._disabled: self._draw(self._bg_normal)


# ─── Campo de pasta com botão Selecionar arredondado ─────────────────────────

class CampoPasta(tk.Frame):
    """Campo de texto + botão Selecionar com visual azul moderno."""

    def __init__(self, parent, placeholder, callback, arquivo=False, bg=None):
        bg = bg or CORES["bg_primario"]
        super().__init__(parent, bg=bg)

        inner = tk.Frame(self,
                         bg=CORES["bg_campo"],
                         highlightbackground=CORES["borda"],
                         highlightthickness=1)
        inner.pack(fill="x")

        self._placeholder = placeholder
        self._arquivo = arquivo
        self._callback = callback

        self._entry = tk.Entry(
            inner,
            font=FONTE_CAMPO,
            bg=CORES["bg_campo"],
            fg=CORES["texto_secundario"],
            insertbackground=CORES["azul3"],
            relief="flat", bd=0,
        )
        self._entry.insert(0, placeholder)
        self._entry.pack(side="left", fill="x", expand=True,
                         ipady=9, padx=(12, 0))
        self._entry.bind("<FocusIn>", self._on_focus)

        btn = RoundedButton(
            inner, text="Selecionar", command=callback,
            bg_normal=CORES["azul1"], bg_hover=CORES["azul2"],
            fg=CORES["texto_primario"],
            font=("Segoe UI", 9, "bold"),
            radius=8, width=100, height=36,
        )
        btn.pack(side="right", padx=4, pady=3)

        self._ph = placeholder

    def _on_focus(self, _=None):
        if self._entry.get() == self._placeholder:
            self._entry.delete(0, "end")
            self._entry.config(fg=CORES["texto_primario"])

    def set_valor(self, valor):
        self._entry.config(fg=CORES["texto_primario"])
        self._entry.delete(0, "end")
        self._entry.insert(0, valor)

    @property
    def _f_entry(self): return self._entry


# ─── Aplicação principal ──────────────────────────────────────────────────────

class AplicacaoOrganizador(tk.Tk):
    def __init__(self, usuario_logado: dict = None):
        super().__init__()
        self.title("FiscalFlow  •  Gestão de Notas Fiscais")
        self.geometry("980x740")
        self.minsize(860, 640)
        self.configure(bg=CORES["bg_primario"])

        self._usuario_logado = usuario_logado or {
            "username": "desconhecido", "perfil": "operador"
        }
        self._pasta_origem   = None
        self._pasta_destino  = None
        self._processando    = False
        self._parar_evento   = threading.Event()
        self._fila_log       = queue.Queue()

        self._caminho_capas        = None
        self._pasta_nfs_capas      = None
        self._pasta_destino_capas  = None
        self._processando_capas    = False
        self._fila_log_capas       = queue.Queue()

        self._configurar_estilos()
        self._construir_interface()
        self._processar_fila_log()
        self._processar_fila_log_capas()

    # ─── Estilos ttk ──────────────────────────────────────────────────────────
    def _configurar_estilos(self):
        e = ttk.Style(self)
        e.theme_use("clam")

        for nome, cor in [
            ("Amarelo",  CORES["barra_prog"]),
            ("Vermelho", CORES["barra_prog2"]),
            ("Laranja",  CORES["barra_prog"]),
        ]:
            e.configure(f"{nome}.Horizontal.TProgressbar",
                        troughcolor=CORES["bg_campo"], background=cor,
                        thickness=10, bordercolor=CORES["borda"],
                        darkcolor=cor, lightcolor=cor)

        for nome in ["Custom", "Print"]:
            e.configure(f"{nome}.TCombobox",
                        fieldbackground=CORES["bg_campo"],
                        background=CORES["bg_campo"],
                        foreground=CORES["texto_primario"],
                        arrowcolor=CORES["azul3"],
                        bordercolor=CORES["borda"],
                        selectbackground=CORES["bg_campo"],
                        selectforeground=CORES["texto_primario"])
            e.map(f"{nome}.TCombobox",
                  fieldbackground=[("readonly", CORES["bg_campo"])],
                  foreground=[("readonly", CORES["texto_primario"])])

        e.configure("Dark.TNotebook",
                    background=CORES["bg_primario"], borderwidth=0)
        e.configure("Dark.TNotebook.Tab",
                    background=CORES["bg_secundario"],
                    foreground=CORES["texto_secundario"],
                    padding=[22, 11],
                    font=("Segoe UI", 10, "bold"),
                    borderwidth=0)
        e.map("Dark.TNotebook.Tab",
              background=[("selected", CORES["bg_card"])],
              foreground=[("selected", CORES["azul3"])])

    # ─── Interface principal ───────────────────────────────────────────────────
    def _construir_interface(self):
        self._criar_cabecalho()
        nb = ttk.Notebook(self, style="Dark.TNotebook")
        nb.pack(fill="both", expand=True)

        a1 = tk.Frame(nb, bg=CORES["bg_primario"])
        nb.add(a1, text="  📂  Organizar Notas  ")
        self._aba_organizar(a1)

        a2 = tk.Frame(nb, bg=CORES["bg_primario"])
        nb.add(a2, text="  📋  Separar Capas de Lote  ")
        self._aba_capas(a2)

        a3 = tk.Frame(nb, bg=CORES["bg_primario"])
        nb.add(a3, text="  🖨️  Impressão em Lote  ")
        
        try:
            construir_aba_impressao(
                self, a3, CORES,
                FONTE_BOTAO, FONTE_BTN_PEQN,
                FONTE_CAMPO, FONTE_LOG, FONTE_STATUS,
            )
        except NameError:
            tk.Label(a3, text="Aba de Impressão (em desenvolvimento)",
                     bg=CORES["bg_primario"], fg=CORES["texto_secundario"],
                     font=("Segoe UI", 12)).pack(pady=40)

    # ─── Cabeçalho ────────────────────────────────────────────────────────────
    def _criar_cabecalho(self):
        cab = tk.Canvas(self, height=72,
                        bg=CORES["bg_primario"], highlightthickness=0)
        cab.pack(fill="x")
        self._desenhar_header(cab)
        tk.Frame(self, bg=CORES["cyan_accent"], height=2).pack(fill="x")

    def _desenhar_header(self, canvas):
        self.update_idletasks()
        # Força w a ser pelo menos 980 (largura padrão) para os cálculos de posicionamento
        w = max(self.winfo_width(), 980)

        # Degradê desenhado bem mais largo para preencher a tela caso o usuário maximize
        for i in range(72):
            r = int(0x0A + (0x10 - 0x0A) * i / 72)
            g = int(0x0F + (0x1E - 0x0F) * i / 72)
            b = int(0x1E + (0x45 - 0x1E) * i / 72)
            canvas.create_rectangle(0, i, w + 2000, i+1, fill=f"#{r:02x}{g:02x}{b:02x}", outline="")

        # Ícone e título
        canvas.create_text(22, 36, text="✦", font=("Segoe UI", 20), fill=CORES["cyan_accent"], anchor="w")
        canvas.create_text(52, 30, text="FiscalFlow", font=("Segoe UI", 20, "bold"), fill=CORES["texto_primario"], anchor="w")
        canvas.create_text(54, 53, text="AUTOMAÇÃO LOGÍSTICA  •  GESTÃO DE NOTAS FISCAIS", font=("Segoe UI", 8), fill=CORES["texto_secundario"], anchor="w")

        # Área direita: usuário
        perfil_icon = "🛡️" if self._usuario_logado["perfil"] == "admin" else "👤"
        uname = f"{perfil_icon}  {self._usuario_logado['username']}"
        canvas.create_text(w - 30, 36, text=uname, font=("Segoe UI", 10, "bold"), fill=CORES["texto_primario"], anchor="e", tags="user_label")

        # Botões
        btn_frame = tk.Frame(canvas, bg="#0d1425") # Usa uma cor sólida parecida com a do degradê na direita
        if self._usuario_logado["perfil"] == "admin":
            RoundedButton(btn_frame, text="⚙  Admin", command=self._abrir_painel_admin, bg_normal="#1A2F55", bg_hover=CORES["azul1"], fg=CORES["texto_primario"], font=("Segoe UI", 9, "bold"), radius=10, width=90, height=32).pack(side="left", padx=(0, 6))

        RoundedButton(btn_frame, text="Sair", command=self._sair, bg_normal="#1A1A2E", bg_hover="#2E1A2E", fg=CORES["texto_secundario"], font=("Segoe UI", 9), radius=10, width=70, height=32).pack(side="left")

        # Posiciona os botões à esquerda do nome de usuário (com margem de segurança)
        btn_x = w - 200
        canvas.create_window(btn_x, 36, window=btn_frame, anchor="e")

    def _abrir_painel_admin(self):
        from ui_login import PainelAdmin
        PainelAdmin(self, self._usuario_logado)

    def _sair(self):
        if messagebox.askyesno("Sair", "Deseja encerrar a sessão?"):
            self.destroy()

    # ══════════════════════════════════════════════════════════════════════════
    # ABA 1 — ORGANIZAR NOTAS
    # ══════════════════════════════════════════════════════════════════════════
    def _aba_organizar(self, parent):
        c = tk.Frame(parent, bg=CORES["bg_primario"])
        c.pack(fill="both", expand=True, padx=20, pady=12)

        # Coluna esquerda — controles
        esq = tk.Frame(c, bg=CORES["bg_primario"], width=360)
        esq.pack(side="left", fill="both", padx=(0, 12))
        esq.pack_propagate(False)

        self._sec(esq, "📁  PASTA DE ORIGEM")
        self._cp_orig = CampoPasta(esq, "Selecione a pasta com as NFs...",
                                   self._sel_origem)
        self._cp_orig.pack(fill="x")

        self._sec(esq, "📂  PASTA DE DESTINO")
        self._cp_dest = CampoPasta(esq, "Selecione onde salvar...",
                                   self._sel_destino)
        self._cp_dest.pack(fill="x")

        self._sec(esq, "⚙️  TIPO DE ORGANIZAÇÃO")
        self._var_org = tk.StringVar(value=OPCOES_ORGANIZACAO[0])
        cb = ttk.Combobox(esq, textvariable=self._var_org,
                          values=OPCOES_ORGANIZACAO,
                          state="readonly", style="Custom.TCombobox",
                          font=FONTE_CAMPO)
        cb.pack(fill="x", ipady=7)

        fp = tk.Frame(esq, bg=CORES["bg_primario"])
        fp.pack(fill="x", pady=(14, 0))
        self._var_copia = tk.BooleanVar(value=True)
        self._chk(fp, "Manter cópia dos originais (recomendado)", self._var_copia)

        self._sec(esq, "📊  RESUMO")
        fs = tk.Frame(esq, bg=CORES["bg_card"],
                      highlightbackground=CORES["azul1"],
                      highlightthickness=1)
        fs.pack(fill="x")
        fi = tk.Frame(fs, bg=CORES["bg_card"])
        fi.pack(fill="x", padx=12, pady=12)
        self._st_total = self._stat(fi, "Total",   "—", CORES["texto_primario"])
        self._st_ok    = self._stat(fi, "Sucesso", "—", CORES["verde"])
        self._st_err   = self._stat(fi, "Erros",   "—", CORES["vermelho"])

        # Divisor vertical
        tk.Frame(c, bg=CORES["borda"], width=1).pack(
            side="left", fill="y", pady=10)

        # Coluna direita — log
        dir_ = tk.Frame(c, bg=CORES["bg_primario"])
        dir_.pack(side="left", fill="both", expand=True, padx=(12, 0))
        self._txt_log = self._painel_log(dir_, "info")

        # Rodapé
        rod = tk.Frame(parent, bg=CORES["bg_secundario"])
        rod.pack(fill="x", side="bottom")
        tk.Frame(rod, bg=CORES["azul1"], height=2).pack(fill="x")
        ri = tk.Frame(rod, bg=CORES["bg_secundario"])
        ri.pack(fill="x", padx=20, pady=12)

        re = tk.Frame(ri, bg=CORES["bg_secundario"])
        re.pack(side="left", fill="x", expand=True, padx=(0, 20))
        self._lbl_status = tk.Label(re, text="Pronto.",
                                    font=FONTE_STATUS,
                                    bg=CORES["bg_secundario"],
                                    fg=CORES["texto_secundario"], anchor="w")
        self._lbl_status.pack(fill="x", pady=(0, 6))
        self._barra_prog = ttk.Progressbar(
            re, orient="horizontal", mode="determinate",
            style="Amarelo.Horizontal.TProgressbar")
        self._barra_prog.pack(fill="x")

        # Botão parar (Canvas arredondado)
        self._btn_parar = RoundedButton(
            ri, text="■  Parar",
            command=self._parar,
            bg_normal=CORES["bg_campo"], bg_hover="#3D1A1A",
            fg=CORES["vermelho"],
            font=("Segoe UI", 9, "bold"),
            radius=10, width=100, height=40,
        )
        self._btn_parar.pack(side="right", padx=(0, 8))
        self._btn_parar.config_state(True)

        # Botão organizar
        self._btn_org = RoundedButton(
            ri, text="▶  ORGANIZAR NOTAS",
            command=self._iniciar_org,
            bg_normal=CORES["azul1"], bg_hover=CORES["azul2"],
            fg=CORES["texto_primario"],
            font=("Segoe UI", 11, "bold"),
            radius=12, width=220, height=44,
        )
        self._btn_org.pack(side="right")

    # ══════════════════════════════════════════════════════════════════════════
    # ABA 2 — SEPARAR CAPAS
    # ══════════════════════════════════════════════════════════════════════════
    def _aba_capas(self, parent):
        c = tk.Frame(parent, bg=CORES["bg_primario"])
        c.pack(fill="both", expand=True, padx=20, pady=12)

        esq = tk.Frame(c, bg=CORES["bg_primario"], width=360)
        esq.pack(side="left", fill="both", padx=(0, 12))
        esq.pack_propagate(False)

        # Card informativo
        info = tk.Frame(esq, bg=CORES["bg_card"],
                        highlightbackground=CORES["cyan_accent"],
                        highlightthickness=1)
        info.pack(fill="x", pady=(8, 12))
        tk.Label(info,
                 text=("  ℹ  Selecione o PDF com as capas de lote\n"
                       "  concatenadas. O sistema separa cada\n"
                       "  capa e cruza com as NFs pelo SID."),
                 font=("Segoe UI", 9), bg=CORES["bg_card"],
                 fg=CORES["texto_secundario"],
                 justify="left", anchor="w").pack(padx=8, pady=10)

        self._sec(esq, "📋  PDF DAS CAPAS DE LOTE")
        self._cp_cap_pdf = CampoPasta(esq, "Selecione o PDF de capas...",
                                      self._sel_pdf_capas, arquivo=True)
        self._cp_cap_pdf.pack(fill="x")

        self._sec(esq, "📁  PASTA COM AS NOTAS FISCAIS")
        self._cp_cap_nfs = CampoPasta(esq, "Pasta com as NFs para cruzar...",
                                      self._sel_nfs_capas)
        self._cp_cap_nfs.pack(fill="x")

        self._sec(esq, "📂  PASTA DE DESTINO")
        self._cp_cap_dest = CampoPasta(esq, "Onde criar as pastas de lote...",
                                       self._sel_dest_capas)
        self._cp_cap_dest.pack(fill="x")

        fp = tk.Frame(esq, bg=CORES["bg_primario"])
        fp.pack(fill="x", pady=(14, 0))
        self._var_copia_cap = tk.BooleanVar(value=True)
        self._chk(fp, "Manter cópia dos originais (recomendado)",
                  self._var_copia_cap)

        self._sec(esq, "📊  RESUMO")
        fs = tk.Frame(esq, bg=CORES["bg_card"],
                      highlightbackground=CORES["cyan_accent"],
                      highlightthickness=1)
        fs.pack(fill="x")
        fi2 = tk.Frame(fs, bg=CORES["bg_card"])
        fi2.pack(fill="x", padx=12, pady=12)
        self._cap_total = self._stat(fi2, "Capas",       "—", CORES["texto_primario"])
        self._cap_ok    = self._stat(fi2, "NFs achadas", "—", CORES["verde"])
        self._cap_no    = self._stat(fi2, "Não achadas", "—", CORES["vermelho"])

        tk.Frame(c, bg=CORES["borda"], width=1).pack(
            side="left", fill="y", pady=10)

        dir_ = tk.Frame(c, bg=CORES["bg_primario"])
        dir_.pack(side="left", fill="both", expand=True, padx=(12, 0))
        self._txt_log_capas = self._painel_log(dir_, "capas")

        rod = tk.Frame(parent, bg=CORES["bg_secundario"])
        rod.pack(fill="x", side="bottom")
        tk.Frame(rod, bg=CORES["cyan_accent"], height=2).pack(fill="x")
        ri = tk.Frame(rod, bg=CORES["bg_secundario"])
        ri.pack(fill="x", padx=20, pady=12)

        re = tk.Frame(ri, bg=CORES["bg_secundario"])
        re.pack(side="left", fill="x", expand=True, padx=(0, 20))
        self._lbl_status_cap = tk.Label(re, text="Pronto.",
                                        font=FONTE_STATUS,
                                        bg=CORES["bg_secundario"],
                                        fg=CORES["texto_secundario"], anchor="w")
        self._lbl_status_cap.pack(fill="x", pady=(0, 6))
        self._prog_cap = ttk.Progressbar(
            re, orient="horizontal", mode="indeterminate",
            style="Vermelho.Horizontal.TProgressbar")
        self._prog_cap.pack(fill="x")

        self._btn_sep = RoundedButton(
            ri, text="▶  SEPARAR CAPAS",
            command=self._iniciar_capas,
            bg_normal=CORES["cyan_accent"], bg_hover="#00D4FF",
            fg="#0A0F1E",
            font=("Segoe UI", 11, "bold"),
            radius=12, width=210, height=44,
        )
        self._btn_sep.pack(side="right")

    # ─── Helpers de UI ────────────────────────────────────────────────────────

    def _sec(self, parent, texto):
        f = tk.Frame(parent, bg=CORES["bg_primario"])
        f.pack(fill="x", pady=(16, 5))
        tk.Frame(f, bg=CORES["azul1"], width=3, height=14
                 ).pack(side="left", padx=(0, 8))
        tk.Label(f, text=texto,
                 font=("Segoe UI", 8, "bold"),
                 bg=CORES["bg_primario"],
                 fg=CORES["texto_secundario"],
                 anchor="w").pack(side="left")

    def _chk(self, parent, texto, var):
        tk.Checkbutton(parent, text=texto, variable=var,
                       font=FONTE_LABEL,
                       bg=CORES["bg_primario"],
                       fg=CORES["texto_primario"],
                       selectcolor=CORES["bg_campo"],
                       activebackground=CORES["bg_primario"],
                       activeforeground=CORES["azul3"],
                       cursor="hand2").pack(anchor="w")

    def _stat(self, parent, rotulo, valor, cor):
        f = tk.Frame(parent, bg=parent.cget("bg"))
        f.pack(side="left", fill="x", expand=True)
        tk.Label(f, text=rotulo,
                 font=("Segoe UI", 8),
                 bg=parent.cget("bg"),
                 fg=CORES["texto_secundario"]).pack()
        lbl = tk.Label(f, text=valor,
                       font=("Segoe UI", 16, "bold"),
                       bg=parent.cget("bg"), fg=cor)
        lbl.pack()
        return lbl

    def _painel_log(self, parent, ctx="info"):
        h = tk.Frame(parent, bg=CORES["bg_primario"])
        h.pack(fill="x", pady=(0, 6))
        tk.Label(h, text="  📋  LOG DE PROCESSAMENTO",
                 font=("Segoe UI", 8, "bold"),
                 bg=CORES["bg_primario"],
                 fg=CORES["texto_secundario"]).pack(side="left")

        RoundedButton(
            h, text="Limpar",
            command=lambda: None,
            bg_normal=CORES["bg_card"], bg_hover=CORES["bg_campo"],
            fg=CORES["texto_secundario"],
            font=("Segoe UI", 8), radius=7,
            width=70, height=26,
        ).pack(side="right")

        fl = tk.Frame(parent, bg=CORES["bg_card"],
                      highlightbackground=CORES["borda"],
                      highlightthickness=1)
        fl.pack(fill="both", expand=True)

        sb = tk.Scrollbar(fl, orient="vertical",
                          bg=CORES["bg_campo"],
                          troughcolor=CORES["bg_secundario"])
        sb.pack(side="right", fill="y")

        txt = tk.Text(fl, font=FONTE_LOG,
                      bg=CORES["bg_card"],
                      fg=CORES["texto_log"],
                      insertbackground=CORES["azul3"],
                      relief="flat", bd=10, state="disabled",
                      wrap="word", yscrollcommand=sb.set)
        txt.pack(fill="both", expand=True)
        sb.config(command=txt.yview)

        txt.tag_config("sucesso", foreground=CORES["verde"])
        txt.tag_config("erro",    foreground=CORES["vermelho"])
        txt.tag_config("info",    foreground=CORES["azul3"])
        txt.tag_config("normal",  foreground=CORES["texto_log"])

        def _limpar():
            txt.config(state="normal")
            txt.delete("1.0", "end")
            txt.config(state="disabled")

        for widget in h.winfo_children():
            if isinstance(widget, RoundedButton):
                widget._command = _limpar

        return txt

    def _campo_pasta(self, parent, placeholder, callback, arquivo=False):
        cp = CampoPasta(parent, placeholder, callback, arquivo)
        cp.pack(fill="x")
        return _CampoCompat(cp)

    def _set_campo(self, compat, valor):
        compat.set_valor(valor)

    # ─── Callbacks de seleção ─────────────────────────────────────────────────
    def _sel_origem(self):
        p = filedialog.askdirectory(title="Pasta com as Notas Fiscais")
        if p:
            self._pasta_origem = p
            self._cp_orig.set_valor(p)
            self._log("📁 Origem: " + p, "info")

    def _sel_destino(self):
        p = filedialog.askdirectory(title="Pasta de destino")
        if p:
            self._pasta_destino = p
            self._cp_dest.set_valor(p)
            self._log("📂 Destino: " + p, "info")

    def _sel_pdf_capas(self):
        p = filedialog.askopenfilename(
            title="PDF de Capas de Lote",
            filetypes=[("PDF", "*.pdf"), ("Todos", "*.*")])
        if p:
            self._caminho_capas = p
            self._cp_cap_pdf.set_valor(p)
            self._log_cap("📋 PDF de capas: " + p, "info")

    def _sel_nfs_capas(self):
        p = filedialog.askdirectory(title="Pasta com as Notas Fiscais")
        if p:
            self._pasta_nfs_capas = p
            self._cp_cap_nfs.set_valor(p)
            self._log_cap("📁 NFs: " + p, "info")

    def _sel_dest_capas(self):
        p = filedialog.askdirectory(title="Pasta de destino dos lotes")
        if p:
            self._pasta_destino_capas = p
            self._cp_cap_dest.set_valor(p)
            self._log_cap("📂 Destino: " + p, "info")

    # ─── Lógica Aba Organizar ─────────────────────────────────────────────────
    def _iniciar_org(self):
        if self._processando: return
        if not self._pasta_origem or not os.path.isdir(self._pasta_origem):
            messagebox.showerror("Atenção", "Selecione uma pasta de origem válida."); return
        if not self._pasta_destino:
            messagebox.showerror("Atenção", "Selecione uma pasta de destino."); return
        if self._pasta_origem == self._pasta_destino:
            messagebox.showerror("Atenção", "Origem e destino não podem ser iguais."); return

        self._processando = True
        self._parar_evento.clear()
        self._btn_org.config_state(True, text="Processando...")
        self._btn_parar.config_state(False)
        self._barra_prog["value"] = 0
        self._lbl_status.config(text="Iniciando...")
        self._st_total.config(text="—")
        self._st_ok.config(text="—")
        self._st_err.config(text="—")
        self._log("─" * 50, "normal")
        self._log(f"🚀 Iniciando — {self._var_org.get()}", "info")

        threading.Thread(
            target=self._exec_org,
            args=(self._var_org.get(), self._var_copia.get()),
            daemon=True
        ).start()

    def _exec_org(self, estrategia, manter):
        def on_prog(r, p, t):
            self._fila_log.put(("PROG", p, t, int(p / t * 100) if t else 0))
        def on_log(m):
            self._fila_log.put(("LOG", m))
        stats = organizar_lote(
            self._pasta_origem, self._pasta_destino,
            estrategia, manter, on_prog, on_log, self._parar_evento)
        detalhes = (
            f"Estratégia: {estrategia} | "
            f"Origem: {self._pasta_origem} | "
            f"Total: {stats.get('total',0)} | "
            f"OK: {stats.get('sucessos',0)} | "
            f"Erros: {stats.get('erros',0)}"
        )
        registrar_operacao(
            self._usuario_logado["username"], "ORGANIZAÇÃO_NOTAS", detalhes)
        self._fila_log.put(("FIM", stats))

    def _parar(self):
        self._parar_evento.set()
        self._log("⚠️ Parada solicitada...", "info")
        self._btn_parar.config_state(True)

    # ─── Lógica Aba Capas ─────────────────────────────────────────────────────
    def _iniciar_capas(self):
        if self._processando_capas: return
        if not self._caminho_capas or not os.path.isfile(self._caminho_capas):
            messagebox.showerror("Atenção", "Selecione o PDF de capas de lote."); return
        if not self._pasta_nfs_capas or not os.path.isdir(self._pasta_nfs_capas):
            messagebox.showerror("Atenção", "Selecione a pasta com as notas fiscais."); return
        if not self._pasta_destino_capas:
            messagebox.showerror("Atenção", "Selecione a pasta de destino."); return

        self._processando_capas = True
        self._btn_sep.config_state(True, text="Processando...")
        self._prog_cap.start(10)
        self._lbl_status_cap.config(text="Processando capas...")
        self._cap_total.config(text="—")
        self._cap_ok.config(text="—")
        self._cap_no.config(text="—")
        self._log_cap("─" * 50, "normal")
        self._log_cap("🚀 Iniciando separação de capas de lote...", "info")

        threading.Thread(
            target=self._exec_capas,
            args=(self._var_copia_cap.get(),),
            daemon=True
        ).start()

    def _exec_capas(self, manter):
        def on_log(m):
            self._fila_log_capas.put(("LOG", m))
        stats = processar_capas_de_lote(
            self._caminho_capas, self._pasta_nfs_capas,
            self._pasta_destino_capas, manter, on_log)
        detalhes = (
            f"PDF capas: {self._caminho_capas} | "
            f"Capas OK: {stats.get('capas_ok',0)} | "
            f"NFs encontradas: {stats.get('nfs_encontradas',0)} | "
            f"NFs não achadas: {stats.get('nfs_nao_encontradas',0)}"
        )
        registrar_operacao(
            self._usuario_logado["username"], "SEPARAÇÃO_LOTE", detalhes)
        self._fila_log_capas.put(("FIM", stats))

    # ─── Polling de filas ─────────────────────────────────────────────────────
    def _processar_fila_log(self):
        try:
            while True:
                item = self._fila_log.get_nowait()
                t = item[0]
                if t == "LOG":
                    self._log(item[1])
                elif t == "PROG":
                    _, p, total, pct = item
                    self._barra_prog["value"] = pct
                    self._lbl_status.config(
                        text=f"Processando... {p}/{total} ({pct}%)")
                elif t == "FIM":
                    s = item[1]
                    self._barra_prog["value"] = 100
                    self._st_total.config(text=str(s.get("total", 0)))
                    self._st_ok.config(text=str(s.get("sucessos", 0)))
                    self._st_err.config(text=str(s.get("erros", 0)))
                    self._lbl_status.config(text="✅ Concluído!")
                    self._btn_org.config_state(False, text="▶  ORGANIZAR NOTAS")
                    self._btn_parar.config_state(True)
                    self._processando = False
        except Exception:
            pass
        self.after(50, self._processar_fila_log)

    def _processar_fila_log_capas(self):
        try:
            while True:
                item = self._fila_log_capas.get_nowait()
                t = item[0]
                if t == "LOG":
                    self._log_cap(item[1])
                elif t == "FIM":
                    s = item[1]
                    self._prog_cap.stop()
                    self._prog_cap["value"] = 100
                    self._cap_total.config(text=str(s.get("capas_ok", 0)))
                    self._cap_ok.config(text=str(s.get("nfs_encontradas", 0)))
                    self._cap_no.config(text=str(s.get("nfs_nao_encontradas", 0)))
                    self._lbl_status_cap.config(text="✅ Concluído!")
                    self._btn_sep.config_state(False, text="▶  SEPARAR CAPAS")
                    self._processando_capas = False
        except Exception:
            pass
        self.after(50, self._processar_fila_log_capas)

    # ─── Log ──────────────────────────────────────────────────────────────────
    def _log(self, msg, tag="normal"):
        if tag == "normal":
            if msg.startswith("✅"):   tag = "sucesso"
            elif msg.startswith("❌"): tag = "erro"
            elif msg[:2] in ("🚀", "📁", "📂", "🏁", "⚠️"): tag = "info"
        self._txt_log.config(state="normal")
        self._txt_log.insert("end", msg + "\n", tag)
        self._txt_log.see("end")
        self._txt_log.config(state="disabled")

    def _log_cap(self, msg, tag="normal"):
        if tag == "normal":
            if msg.startswith("✅"):   tag = "sucesso"
            elif msg.startswith("❌"): tag = "erro"
            elif msg[:2] in ("🚀", "📋", "📁", "📂", "🏁", "⚠️", "🔍"): tag = "info"
        self._txt_log_capas.config(state="normal")
        self._txt_log_capas.insert("end", msg + "\n", tag)
        self._txt_log_capas.see("end")
        self._txt_log_capas.config(state="disabled")


# ─── Compat helper (para código que usa _ef_orig._entry etc) ─────────────────

class _CampoCompat:
    """Wrapper de compatibilidade para código legado que usa frame._entry."""
    def __init__(self, cp: CampoPasta):
        self._cp = cp
        self._entry = cp._entry
        self._ph = cp._placeholder

    def set_valor(self, valor):
        self._cp.set_valor(valor)