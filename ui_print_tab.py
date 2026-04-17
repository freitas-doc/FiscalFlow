# ui_print_tab.py
# Mixin com a aba de impressão — incluído no ui.py principal

import os, threading, queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Importado condicionalmente para não quebrar em Linux
try:
    from printer import (
        listar_impressoras, impressora_padrao,
        imprimir_lotes, listar_arquivos_lote,
        listar_bandejas, _encontrar_sumatra,
    )
    PRINTER_OK = True
except Exception:
    PRINTER_OK = False
    _encontrar_sumatra = lambda: None


def construir_aba_impressao(app, parent, CORES, FONTE_BOTAO, FONTE_BTN_PEQN,
                             FONTE_CAMPO, FONTE_LOG, FONTE_STATUS):
    """
    Constrói a aba de impressão em lote e injeta os atributos no objeto app.
    Chamado a partir do ui.py principal.
    """
    app._pastas_impressao = []          # pastas selecionadas para impressão
    app._processando_print = False
    app._parar_print = threading.Event()
    app._fila_print = queue.Queue()

    c = tk.Frame(parent, bg=CORES["bg_primario"])
    c.pack(fill="both", expand=True, padx=20, pady=10)

    # ── Coluna esquerda: configurações (com scroll vertical) ──────────────────
    esq_outer = tk.Frame(c, bg=CORES["bg_primario"], width=390)
    esq_outer.pack(side="left", fill="both", padx=(0, 10))
    esq_outer.pack_propagate(False)

    esq_canvas = tk.Canvas(esq_outer, bg=CORES["bg_primario"],
                           highlightthickness=0, width=375)
    esq_scroll = tk.Scrollbar(esq_outer, orient="vertical",
                              command=esq_canvas.yview)
    esq_canvas.configure(yscrollcommand=esq_scroll.set)
    esq_scroll.pack(side="right", fill="y")
    esq_canvas.pack(side="left", fill="both", expand=True)

    esq = tk.Frame(esq_canvas, bg=CORES["bg_primario"])
    esq_window = esq_canvas.create_window((0, 0), window=esq, anchor="nw")

    def _on_esq_configure(event):
        esq_canvas.configure(scrollregion=esq_canvas.bbox("all"))

    def _on_canvas_resize(event):
        esq_canvas.itemconfig(esq_window, width=event.width)

    esq.bind("<Configure>", _on_esq_configure)
    esq_canvas.bind("<Configure>", _on_canvas_resize)

    def _on_mousewheel(event):
        esq_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    esq_canvas.bind("<MouseWheel>", _on_mousewheel)
    esq.bind("<MouseWheel>", _on_mousewheel)

    def sec(t):
        tk.Label(esq, text=f"  {t}", font=("Segoe UI", 8, "bold"),
                 bg=CORES["bg_primario"], fg=CORES["texto_secundario"],
                 anchor="w").pack(fill="x", pady=(14, 4))

    # ── Aviso se win32 não disponível ─────────────────────────────────────────
    if not PRINTER_OK:
        fi = tk.Frame(esq, bg="#2a1a00",
                      highlightbackground="#F5A623", highlightthickness=1)
        fi.pack(fill="x", pady=(8, 0))
        tk.Label(fi,
                 text=("  ⚠️  Para usar impressão instale:\n"
                       "  pip install pywin32\n"
                       "  (requer Windows 10/11)"),
                 font=("Segoe UI", 9), bg="#2a1a00",
                 fg="#F5A623", justify="left", anchor="w").pack(padx=8, pady=8)

    # ── Aviso se SumatraPDF não está instalado (necessário para gavetas) ──────
    if PRINTER_OK and not _encontrar_sumatra():
        fs = tk.Frame(esq, bg="#1a1a2a",
                      highlightbackground="#3A6BC4", highlightthickness=1)
        fs.pack(fill="x", pady=(8, 0))
        tk.Label(fs,
                 text=("  ℹ️  Para usar gavetas separadas instale:\n"
                       "  SumatraPDF (gratuito)\n"
                       "  sumatrapdfreader.org"),
                 font=("Segoe UI", 9), bg="#1a1a2a",
                 fg="#7EB3F5", justify="left", anchor="w").pack(padx=8, pady=6)

        def _abrir_sumatra_site():
            import webbrowser
            webbrowser.open("https://www.sumatrapdfreader.org/download-free-pdf-viewer")

        tk.Button(fs, text="⬇  Baixar SumatraPDF",
                  font=("Segoe UI", 9, "bold"),
                  bg="#3A6BC4", fg="#FFFFFF",
                  relief="flat", cursor="hand2",
                  command=_abrir_sumatra_site
                  ).pack(fill="x", padx=8, pady=(0, 8))

    # ── Seleção de pasta raiz ─────────────────────────────────────────────────
    sec("📂  PASTA RAIZ DOS LOTES")
    app._ef_print_raiz = _campo_leitura(esq, "Selecione a pasta com os lotes...",
                                         CORES, FONTE_CAMPO,
                                         lambda: _sel_raiz(app, CORES))

    # ── Lista de pastas disponíveis ───────────────────────────────────────────
    sec("📋  LOTES DISPONÍVEIS  (selecione para imprimir)")

    frame_lista = tk.Frame(esq, bg=CORES["bg_campo"],
                           highlightbackground=CORES["borda"], highlightthickness=1)
    frame_lista.pack(fill="both", expand=True)

    sb_lista = tk.Scrollbar(frame_lista, bg=CORES["borda"])
    sb_lista.pack(side="right", fill="y")

    app._listbox = tk.Listbox(
        frame_lista,
        selectmode="extended",        # múltipla seleção com Ctrl/Shift
        font=("Consolas", 9),
        bg=CORES["bg_campo"],
        fg=CORES["texto_primario"],
        selectbackground=CORES["destaque"],
        selectforeground="#0F1117",
        activestyle="none",
        relief="flat",
        bd=6,
        yscrollcommand=sb_lista.set,
    )
    app._listbox.pack(fill="both", expand=True)
    sb_lista.config(command=app._listbox.yview)
    app._listbox.bind("<<ListboxSelect>>", lambda e: _atualizar_selecao(app, CORES))
    app._listbox.bind("<MouseWheel>", _on_mousewheel)

    # Botões Selecionar Todos / Limpar
    frame_btns_lista = tk.Frame(esq, bg=CORES["bg_primario"])
    frame_btns_lista.pack(fill="x", pady=(6, 0))

    def _sel_todos():
        app._listbox.select_set(0, "end")
        _atualizar_selecao(app, CORES)

    def _limpar_sel():
        app._listbox.selection_clear(0, "end")
        _atualizar_selecao(app, CORES)

    tk.Button(frame_btns_lista, text="Selecionar todos",
              font=FONTE_BTN_PEQN, bg=CORES["bg_campo"],
              fg=CORES["texto_secundario"], relief="flat", cursor="hand2",
              command=_sel_todos).pack(side="left", padx=(0, 6))
    tk.Button(frame_btns_lista, text="Limpar seleção",
              font=FONTE_BTN_PEQN, bg=CORES["bg_campo"],
              fg=CORES["texto_secundario"], relief="flat", cursor="hand2",
              command=_limpar_sel).pack(side="left")

    # ── Impressora ────────────────────────────────────────────────────────────
    sec("🖨️  IMPRESSORA")

    frame_imp = tk.Frame(esq, bg=CORES["bg_primario"])
    frame_imp.pack(fill="x")

    impressoras = listar_impressoras() if PRINTER_OK else []
    padrao = impressora_padrao() if PRINTER_OK else ""

    app._var_impressora = tk.StringVar(
        value=padrao if padrao else (impressoras[0] if impressoras else "Nenhuma disponível")
    )

    estilo = ttk.Style()
    estilo.configure("Print.TCombobox",
                     fieldbackground=CORES["bg_campo"],
                     background=CORES["bg_campo"],
                     foreground=CORES["texto_primario"],
                     arrowcolor=CORES["destaque"],
                     bordercolor=CORES["borda"],
                     selectbackground=CORES["bg_campo"],
                     selectforeground=CORES["texto_primario"])
    estilo.map("Print.TCombobox",
               fieldbackground=[("readonly", CORES["bg_campo"])],
               foreground=[("readonly", CORES["texto_primario"])])

    combo_imp = ttk.Combobox(
        frame_imp,
        textvariable=app._var_impressora,
        values=impressoras if impressoras else ["Nenhuma disponível"],
        state="readonly",
        style="Print.TCombobox",
        font=FONTE_CAMPO,
    )
    combo_imp.pack(fill="x", ipady=6)
    app._combo_impressora = combo_imp

    # Botão atualizar lista de impressoras
    tk.Button(frame_imp, text="↻ Atualizar impressoras",
              font=FONTE_BTN_PEQN, bg=CORES["bg_primario"],
              fg=CORES["texto_secundario"], relief="flat", cursor="hand2",
              command=lambda: _atualizar_impressoras(app, CORES)).pack(anchor="e", pady=(4, 0))

    # ── Bandeja dupla ─────────────────────────────────────────────────────────
    sec("📥  GAVETAS DE PAPEL")

    app._var_bandeja_dupla = tk.BooleanVar(value=False)

    frame_toggle = tk.Frame(esq, bg=CORES["bg_primario"])
    frame_toggle.pack(fill="x", pady=(0, 4))

    chk_bandeja = tk.Checkbutton(
        frame_toggle,
        text="  Usar gavetas separadas (Capa ≠ NFs)",
        variable=app._var_bandeja_dupla,
        font=("Segoe UI", 9),
        bg=CORES["bg_primario"], fg=CORES["texto_primario"],
        selectcolor=CORES["bg_campo"],
        activebackground=CORES["bg_primario"],
        activeforeground=CORES["destaque"],
        cursor="hand2",
        command=lambda: _toggle_bandeja_dupla(app, CORES),
    )
    chk_bandeja.pack(side="left")

    # Frame que contém os controles de bandeja (mostra/esconde conforme toggle)
    app._frame_bandejas = tk.Frame(esq, bg=CORES["bg_secundario"],
                                   highlightbackground=CORES["borda"],
                                   highlightthickness=1)
    # Começa oculto
    # Linha: Gaveta A (Capas — sulfite)
    frame_gav_a = tk.Frame(app._frame_bandejas, bg=CORES["bg_secundario"])
    frame_gav_a.pack(fill="x", padx=10, pady=(10, 4))

    tk.Label(frame_gav_a, text="🅐  Gaveta A — Capas (sulfite)",
             font=("Segoe UI", 9, "bold"),
             bg=CORES["bg_secundario"], fg=CORES["texto_primario"],
             anchor="w").pack(fill="x")

    app._var_bandeja_capa = tk.StringVar(value="")
    app._combo_bandeja_capa = ttk.Combobox(
        frame_gav_a,
        textvariable=app._var_bandeja_capa,
        values=["(selecione a impressora primeiro)"],
        state="readonly",
        style="Print.TCombobox",
        font=FONTE_CAMPO,
    )
    app._combo_bandeja_capa.pack(fill="x", ipady=5, pady=(4, 0))

    # Linha: Gaveta B (NFs — papel especial)
    frame_gav_b = tk.Frame(app._frame_bandejas, bg=CORES["bg_secundario"])
    frame_gav_b.pack(fill="x", padx=10, pady=(8, 4))

    tk.Label(frame_gav_b, text="🅑  Gaveta B — NFs (papel especial)",
             font=("Segoe UI", 9, "bold"),
             bg=CORES["bg_secundario"], fg=CORES["texto_primario"],
             anchor="w").pack(fill="x")

    app._var_bandeja_nfs = tk.StringVar(value="")
    app._combo_bandeja_nfs = ttk.Combobox(
        frame_gav_b,
        textvariable=app._var_bandeja_nfs,
        values=["(selecione a impressora primeiro)"],
        state="readonly",
        style="Print.TCombobox",
        font=FONTE_CAMPO,
    )
    app._combo_bandeja_nfs.pack(fill="x", ipady=5, pady=(4, 0))

    # Botão para recarregar bandejas da impressora selecionada
    tk.Button(
        app._frame_bandejas,
        text="↻ Detectar gavetas da impressora",
        font=FONTE_BTN_PEQN, bg=CORES["bg_secundario"],
        fg=CORES["destaque"], relief="flat", cursor="hand2",
        command=lambda: _carregar_bandejas(app, CORES),
    ).pack(anchor="e", padx=10, pady=(4, 10))

    # Guarda lista de bandejas [{numero, nome}] para leitura posterior
    app._bandejas_disponiveis = []

    # ── Intervalo entre lotes ─────────────────────────────────────────────────
    sec("⏱️  INTERVALO ENTRE LOTES (segundos)")
    frame_int = tk.Frame(esq, bg=CORES["bg_primario"])
    frame_int.pack(fill="x")

    app._var_intervalo = tk.DoubleVar(value=2.0)
    tk.Scale(frame_int, from_=0, to=10, resolution=0.5,
             orient="horizontal", variable=app._var_intervalo,
             bg=CORES["bg_primario"], fg=CORES["texto_primario"],
             troughcolor=CORES["bg_campo"], activebackground=CORES["destaque"],
             highlightthickness=0, showvalue=True, font=("Segoe UI", 9)
             ).pack(fill="x")

    # ── Separador e Log ───────────────────────────────────────────────────────
    tk.Frame(c, bg=CORES["borda"], width=1).pack(side="left", fill="y", pady=10)

    dir_ = tk.Frame(c, bg=CORES["bg_primario"])
    dir_.pack(side="left", fill="both", expand=True, padx=(10, 0))

    h = tk.Frame(dir_, bg=CORES["bg_primario"])
    h.pack(fill="x", pady=(14, 6))
    tk.Label(h, text="  📋  LOG DE IMPRESSÃO",
             font=("Segoe UI", 8, "bold"),
             bg=CORES["bg_primario"], fg=CORES["texto_secundario"]).pack(side="left")
    tk.Button(h, text="Limpar", font=FONTE_BTN_PEQN,
              bg=CORES["bg_primario"], fg=CORES["texto_secundario"],
              activebackground=CORES["bg_campo"], relief="flat", cursor="hand2",
              command=lambda: _limpar_log_print(app)).pack(side="right")

    fl = tk.Frame(dir_, bg=CORES["bg_campo"],
                  highlightbackground=CORES["borda"], highlightthickness=1)
    fl.pack(fill="both", expand=True)
    sb2 = tk.Scrollbar(fl, bg=CORES["borda"])
    sb2.pack(side="right", fill="y")
    app._txt_log_print = tk.Text(
        fl, font=FONTE_LOG, bg=CORES["bg_campo"], fg="#A0B0C0",
        insertbackground=CORES["destaque"], relief="flat", bd=8,
        state="disabled", wrap="word", yscrollcommand=sb2.set)
    app._txt_log_print.pack(fill="both", expand=True)
    sb2.config(command=app._txt_log_print.yview)
    app._txt_log_print.tag_config("sucesso", foreground="#27AE60")
    app._txt_log_print.tag_config("erro",    foreground="#E74C3C")
    app._txt_log_print.tag_config("info",    foreground="#F5A623")
    app._txt_log_print.tag_config("normal",  foreground="#A0B0C0")

    # ── Rodapé ────────────────────────────────────────────────────────────────
    rod = tk.Frame(parent, bg=CORES["bg_secundario"])
    rod.pack(fill="x", side="bottom")
    tk.Frame(rod, bg=CORES["borda"], height=1).pack(fill="x")

    ri = tk.Frame(rod, bg=CORES["bg_secundario"])
    ri.pack(fill="x", padx=20, pady=14)

    re = tk.Frame(ri, bg=CORES["bg_secundario"])
    re.pack(side="left", fill="x", expand=True, padx=(0, 20))

    app._lbl_status_print = tk.Label(
        re, text="Pronto.",
        font=FONTE_STATUS if hasattr(app, "_dummy") else ("Segoe UI", 9),
        bg=CORES["bg_secundario"], fg=CORES["texto_secundario"], anchor="w")
    app._lbl_status_print.pack(fill="x", pady=(0, 6))

    app._prog_print = ttk.Progressbar(re, orient="horizontal", mode="determinate",
                                       style="Laranja.Horizontal.TProgressbar")
    app._prog_print.pack(fill="x")

    app._lbl_sel_count = tk.Label(ri, text="0 lote(s) selecionado(s)",
                                   font=("Segoe UI", 9), bg=CORES["bg_secundario"],
                                   fg=CORES["texto_secundario"])
    app._lbl_sel_count.pack(side="right", padx=(0, 16))

    app._btn_parar_print = tk.Button(
        ri, text="■  Parar", font=FONTE_BTN_PEQN,
        bg=CORES["bg_campo"], fg="#E74C3C",
        activebackground=CORES["borda"], relief="flat",
        cursor="hand2", padx=12, pady=10, state="disabled",
        command=lambda: _parar_print(app))
    app._btn_parar_print.pack(side="right", padx=(0, 8))

    app._btn_imprimir = tk.Button(
        ri, text="🖨️  IMPRIMIR LOTES", font=FONTE_BOTAO,
        bg="#27AE60", fg="#FFFFFF",
        activebackground="#2ECC71", activeforeground="#FFFFFF",
        relief="flat", cursor="hand2", padx=22, pady=10,
        command=lambda: _iniciar_impressao(app))
    app._btn_imprimir.pack(side="right")

    # Inicia polling da fila de print
    _poll_fila_print(app)


# ─── Funções internas da aba ──────────────────────────────────────────────────

def _campo_leitura(parent, placeholder, CORES, fonte, callback):
    f = tk.Frame(parent, bg=CORES["bg_campo"],
                 highlightbackground=CORES["borda"], highlightthickness=1)
    f.pack(fill="x")
    entry = tk.Entry(f, font=fonte, bg=CORES["bg_campo"],
                     fg=CORES["texto_secundario"],
                     insertbackground=CORES["destaque"], relief="flat", bd=0)
    entry.insert(0, placeholder)
    entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(10, 0))
    entry.bind("<FocusIn>", lambda e, en=entry, ph=placeholder: (
        en.delete(0, "end") or en.config(fg=CORES["texto_primario"])
    ) if en.get() == ph else None)
    tk.Button(f, text="Selecionar", font=("Segoe UI", 9),
              bg=CORES["bg_secundario"], fg=CORES["destaque"],
              activebackground=CORES["borda"], activeforeground=CORES["destaque"],
              relief="flat", cursor="hand2", padx=12, command=callback
              ).pack(side="right", ipady=8)
    f._entry = entry
    return f


def _sel_raiz(app, CORES):
    pasta = filedialog.askdirectory(title="Selecione a pasta raiz com os lotes")
    if not pasta:
        return

    # Atualiza campo de texto
    e = app._ef_print_raiz._entry
    e.config(fg=CORES["texto_primario"])
    e.delete(0, "end")
    e.insert(0, pasta)

    # Popula a listbox com as subpastas (lotes)
    app._listbox.delete(0, "end")
    app._pastas_impressao = []

    subpastas = sorted(
        d for d in os.listdir(pasta)
        if os.path.isdir(os.path.join(pasta, d))
    )

    for sub in subpastas:
        caminho_completo = os.path.join(pasta, sub)
        # Conta PDFs na subpasta
        n_pdfs = sum(
            1 for f in os.listdir(caminho_completo)
            if f.lower().endswith(".pdf")
        )
        app._listbox.insert("end", f"{sub}  ({n_pdfs} PDF{'s' if n_pdfs != 1 else ''})")
        app._pastas_impressao.append(caminho_completo)

    _log_print(app, f"📂 {len(subpastas)} lote(s) encontrado(s) em: {pasta}", "info")
    _atualizar_selecao(app, CORES)


def _atualizar_selecao(app, CORES):
    indices = app._listbox.curselection()
    n = len(indices)
    app._lbl_sel_count.config(
        text=f"{n} lote(s) selecionado(s)",
        fg=CORES["destaque"] if n > 0 else CORES["texto_secundario"]
    )


def _atualizar_impressoras(app, CORES):
    if not PRINTER_OK:
        return
    from printer import listar_impressoras, impressora_padrao
    impressoras = listar_impressoras()
    app._combo_impressora.config(values=impressoras if impressoras else ["Nenhuma disponível"])
    padrao = impressora_padrao()
    if padrao:
        app._var_impressora.set(padrao)
    _log_print(app, f"🖨️  {len(impressoras)} impressora(s) encontrada(s).", "info")


def _iniciar_impressao(app):
    if app._processando_print:
        return

    if not PRINTER_OK:
        messagebox.showerror("Atenção",
                             "Instale pywin32 para usar impressão:\n\npip install pywin32")
        return

    indices = app._listbox.curselection()
    if not indices:
        messagebox.showwarning("Atenção", "Selecione pelo menos um lote para imprimir.")
        return

    pastas_selecionadas = [app._pastas_impressao[i] for i in indices]
    impressora = app._var_impressora.get()
    if impressora == "Nenhuma disponível":
        messagebox.showerror("Atenção", "Nenhuma impressora disponível.")
        return

    intervalo = app._var_intervalo.get()

    # Parâmetros de bandeja dupla
    usar_bandeja_dupla = app._var_bandeja_dupla.get()
    bandeja_capa_num = None
    bandeja_nfs_num = None

    if usar_bandeja_dupla:
        bandeja_capa_num = _numero_bandeja_selecionada(app, "capa")
        bandeja_nfs_num  = _numero_bandeja_selecionada(app, "nfs")

        if bandeja_capa_num is None or bandeja_nfs_num is None:
            messagebox.showerror(
                "Atenção",
                "Selecione as gavetas de papel para Capas e NFs\n"
                "antes de iniciar a impressão em modo duplo.\n\n"
                "Clique em '↻ Detectar gavetas da impressora' para carregar as opções."
            )
            return

    # Confirmação
    nomes = "\n".join(f"  • {os.path.basename(p)}" for p in pastas_selecionadas[:8])
    if len(pastas_selecionadas) > 8:
        nomes += f"\n  ... e mais {len(pastas_selecionadas) - 8}"

    modo_str = (
        f"\n\n📥 Modo GAVETAS SEPARADAS\n"
        f"   Capas (sulfite)  → Gaveta A  (bandeja {bandeja_capa_num})\n"
        f"   NFs (especial)   → Gaveta B  (bandeja {bandeja_nfs_num})"
        if usar_bandeja_dupla else ""
    )

    confirmar = messagebox.askyesno(
        "Confirmar Impressão",
        f"Enviar {len(pastas_selecionadas)} lote(s) para:\n🖨️  {impressora}\n\n{nomes}{modo_str}\n\nContinuar?"
    )
    if not confirmar:
        return

    app._processando_print = True
    app._parar_print.clear()
    app._btn_imprimir.config(state="disabled", bg="#2E3148", fg="#7B8299")
    app._btn_parar_print.config(state="normal")
    app._prog_print["value"] = 0
    app._lbl_status_print.config(text="Preparando impressão...")

    _log_print(app, "─" * 50, "normal")
    _log_print(app, f"🖨️  Iniciando impressão — {len(pastas_selecionadas)} lote(s)", "info")

    threading.Thread(
        target=_exec_impressao,
        args=(app, pastas_selecionadas, impressora, intervalo,
              usar_bandeja_dupla, bandeja_capa_num, bandeja_nfs_num),
        daemon=True,
    ).start()


def _exec_impressao(app, pastas, impressora, intervalo,
                    usar_bandeja_dupla=False, bandeja_capa=None, bandeja_nfs=None):
    total = len(pastas)

    def on_log(msg):
        app._fila_print.put(("LOG", msg))

    from printer import imprimir_lotes
    stats = imprimir_lotes(
        pastas=pastas,
        nome_impressora=impressora,
        intervalo_segundos=intervalo,
        callback_log=on_log,
        parar_evento=app._parar_print,
        usar_bandeja_dupla=usar_bandeja_dupla,
        bandeja_capa=bandeja_capa,
        bandeja_nfs=bandeja_nfs,
    )

    app._fila_print.put(("FIM", stats, total))


def _parar_print(app):
    app._parar_print.set()
    _log_print(app, "⚠️  Parada solicitada...", "info")
    app._btn_parar_print.config(state="disabled")


def _poll_fila_print(app):
    try:
        while True:
            item = app._fila_print.get_nowait()
            t = item[0]
            if t == "LOG":
                _log_print(app, item[1])
            elif t == "FIM":
                stats = item[1]
                total = item[2]
                pct = int(stats["enviados"] / total * 100) if total else 0
                app._prog_print["value"] = pct
                app._lbl_status_print.config(
                    text=f"✅ Concluído — {stats['enviados']}/{total} enviado(s)"
                )
                app._btn_imprimir.config(state="normal", bg="#27AE60", fg="#FFFFFF")
                app._btn_parar_print.config(state="disabled")
                app._processando_print = False
    except Exception:
        pass
    app.after(80, lambda: _poll_fila_print(app))


def _log_print(app, msg, tag="normal"):
    if tag == "normal":
        if msg.startswith("✅"):  tag = "sucesso"
        elif msg.startswith("❌"): tag = "erro"
        elif msg[:2] in ("🖨","📂","📦","🔄","📄","⚠️","🏁","⏳"): tag = "info"
    app._txt_log_print.config(state="normal")
    app._txt_log_print.insert("end", msg + "\n", tag)
    app._txt_log_print.see("end")
    app._txt_log_print.config(state="disabled")


def _limpar_log_print(app):
    app._txt_log_print.config(state="normal")
    app._txt_log_print.delete("1.0", "end")
    app._txt_log_print.config(state="disabled")


# ─── Funções de bandeja dupla ─────────────────────────────────────────────────

def _toggle_bandeja_dupla(app, CORES):
    """Mostra ou esconde o painel de gavetas conforme o checkbox."""
    if app._var_bandeja_dupla.get():
        app._frame_bandejas.pack(fill="x", pady=(0, 6))
        # Carrega bandejas automaticamente se ainda não carregou
        if not app._bandejas_disponiveis:
            _carregar_bandejas(app, CORES)
    else:
        app._frame_bandejas.pack_forget()


def _carregar_bandejas(app, CORES):
    """
    Consulta as bandejas da impressora selecionada e popula os comboboxes.
    """
    if not PRINTER_OK:
        return

    impressora = app._var_impressora.get()
    if not impressora or impressora == "Nenhuma disponível":
        messagebox.showwarning("Atenção", "Selecione uma impressora primeiro.")
        return

    from printer import listar_bandejas
    bandejas = listar_bandejas(impressora)
    app._bandejas_disponiveis = bandejas

    if not bandejas:
        _log_print(app,
                   f"⚠️  Nenhuma bandeja detectada em '{impressora}'. "
                   "Verifique o driver da impressora.", "info")
        opcoes = ["(nenhuma bandeja detectada)"]
    else:
        # Formato exibido: "Gaveta 1  (nº 1)"
        opcoes = [f"{b['nome']}  (nº {b['numero']})" for b in bandejas]
        _log_print(app,
                   f"📥  {len(bandejas)} gaveta(s) detectada(s) em '{impressora}'.",
                   "info")

    app._combo_bandeja_capa.config(values=opcoes)
    app._combo_bandeja_nfs.config(values=opcoes)

    # Pré-seleciona: primeira bandeja para capa, segunda para NFs (se existir)
    if opcoes and opcoes[0] != "(nenhuma bandeja detectada)":
        app._var_bandeja_capa.set(opcoes[0])
        app._var_bandeja_nfs.set(opcoes[1] if len(opcoes) > 1 else opcoes[0])


def _numero_bandeja_selecionada(app, tipo: str) -> "Optional[int]":
    """
    Lê o combobox de bandeja e retorna o número inteiro da gaveta selecionada.

    Args:
        tipo: "capa" ou "nfs"

    Returns:
        int com o número da bandeja, ou None se nada selecionado.
    """
    var = app._var_bandeja_capa if tipo == "capa" else app._var_bandeja_nfs
    texto = var.get()

    if not texto or "nenhuma" in texto.lower() or "selecione" in texto.lower():
        return None

    # Extrai o número entre "(nº " e ")"
    import re
    m = re.search(r'\(nº\s+(\d+)\)', texto)
    if m:
        return int(m.group(1))

    return None
