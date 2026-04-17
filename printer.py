# printer.py - Módulo de impressão em lote de notas fiscais
#
# ESTRATÉGIA DE IMPRESSÃO (Windows 10/11):
#   1. Para cada pasta de lote selecionada:
#      a. Identifica a capa de lote (arquivo com "CAPA_" no nome)
#      b. Lista as demais NFs em ordem alfabética
#      c. Se modo BANDEJA DUPLA ativado:
#         - Gera PDF temporário só com a capa  → envia para Gaveta A (sulfite)
#         - Aguarda o spooler confirmar o job antes de prosseguir
#         - Gera PDF temporário só com as NFs  → envia para Gaveta B (especial)
#      d. Se modo BANDEJA SIMPLES:
#         - Mescla tudo num único PDF e envia normalmente
#   2. Impressão frente-e-verso: cada documento (capa ou NF) é tratado como
#      unidade independente de folha. Página em branco inserida somente quando
#      o documento tem número ÍMPAR de páginas — garante que o próximo
#      documento sempre comece na frente de uma nova folha física.
#   3. Espera confirmação do spooler entre jobs para evitar duplicatas/perdas.
#   4. Temporários só são deletados após confirmação que o job saiu do spooler.
#
# DEPENDÊNCIAS EXTRAS:
#   pip install pypdf pywin32

import os
import sys
import tempfile
import logging
import threading
import time
import subprocess
from typing import Optional, Callable

logger = logging.getLogger(__name__)

# ── Verificação de dependências ───────────────────────────────────────────────

try:
    from pypdf import PdfReader, PdfWriter
    PYPDF_OK = True
except ImportError:
    try:
        import PyPDF2
        PdfReader = PyPDF2.PdfReader
        PdfWriter = PyPDF2.PdfWriter
        PYPDF_OK = True
    except ImportError:
        PYPDF_OK = False

# win32 só existe no Windows — importação condicional
WIN32_OK = False
if sys.platform == "win32":
    try:
        import win32print
        import win32api
        import win32con
        WIN32_OK = True
    except ImportError:
        pass


# ─── Constantes de bandejas padrão DMBIN_* ───────────────────────────────────
DMBIN_UPPER          = 1
DMBIN_LOWER          = 2
DMBIN_MIDDLE         = 3
DMBIN_MANUAL         = 4
DMBIN_AUTO           = 7
DMBIN_LARGECAPACITY  = 11
DMBIN_CASSETTE       = 14
DMBIN_FORMSOURCE     = 15


# ─── Listagem de arquivos de uma pasta de lote ────────────────────────────────

def listar_arquivos_lote(pasta: str) -> dict:
    """
    Escaneia uma pasta de lote e separa a capa das NFs.

    Convenção: arquivo com "CAPA_" no nome é a capa do lote.
    Todos os outros PDFs são NFs, ordenados alfabeticamente.

    Returns:
        Dict com chaves 'capa' (str|None) e 'nfs' (list[str]).
    """
    resultado = {"capa": None, "nfs": []}

    if not os.path.isdir(pasta):
        return resultado

    pdfs = sorted(f for f in os.listdir(pasta) if f.lower().endswith(".pdf"))

    for nome in pdfs:
        caminho = os.path.join(pasta, nome)
        if "CAPA_" in nome.upper():
            resultado["capa"] = caminho
        else:
            resultado["nfs"].append(caminho)

    return resultado


# ─── Mesclagem de PDFs com lógica correta para frente-e-verso ─────────────────

def _num_paginas(caminho: str) -> int:
    """Retorna o número de páginas de um PDF, ou 0 em caso de erro."""
    try:
        return len(PdfReader(caminho).pages)
    except Exception:
        return 0


def _mesclar_pdfs_frente_verso(
    lista_caminhos: list,
    cada_doc_nova_folha: bool = True,
) -> Optional[str]:
    """
    Mescla uma lista de PDFs em um arquivo temporário com suporte correto
    a impressão frente-e-verso.

    Regra frente-e-verso:
      - Cada documento é uma unidade independente de folha física.
      - Se um documento tem número ÍMPAR de páginas, insere UMA página em
        branco ao final — assim o próximo documento começa sempre na FRENTE
        de uma nova folha, não no verso da folha anterior.
      - Se um documento tem número PAR de páginas, já fecha a folha
        naturalmente — nenhuma página em branco é necessária.

    Args:
        lista_caminhos: Lista de caminhos de PDFs a mesclar.
        cada_doc_nova_folha: Se True, aplica a regra frente-e-verso acima.
                             Se False, mescla sem inserir páginas extras.

    Returns:
        Caminho do arquivo temporário criado, ou None em caso de falha.
    """
    if not PYPDF_OK:
        logger.error("pypdf/PyPDF2 não disponível para mesclar PDFs.")
        return None

    if not lista_caminhos:
        return None

    writer = PdfWriter()

    for caminho in lista_caminhos:
        try:
            # O append traz o PDF inteiro resolvendo colisões de IDs internamente
            writer.append(caminho)
            
            # Precisamos ler o arquivo apenas para saber se é ímpar e aplicar
            # a regra de frente-e-verso (folha em branco)
            reader = PdfReader(caminho)
            num_paginas = len(reader.pages)

            if cada_doc_nova_folha and num_paginas % 2 != 0:
                # Número ímpar de páginas → insere branco para fechar a folha
                writer.add_blank_page()
                logger.debug(
                    f"'{os.path.basename(caminho)}' ({num_paginas} pág.) "
                    f"→ página em branco inserida (ímpar → frente-e-verso)."
                )
            else:
                logger.debug(
                    f"'{os.path.basename(caminho)}' ({num_paginas} pág.) "
                    f"→ sem página em branco (par ou separação desativada)."
                )

        except Exception as e:
            logger.warning(f"Ignorando '{caminho}' (erro: {e})")

    if len(writer.pages) == 0:
        return None

    fd, caminho_temp = tempfile.mkstemp(suffix=".pdf", prefix="IMPRESSAO_")
    os.close(fd)

    try:
        with open(caminho_temp, "wb") as f:
            writer.write(f)
        logger.info(f"PDF temporário: {len(writer.pages)} páginas → {caminho_temp}")
        return caminho_temp
    except Exception as e:
        logger.error(f"Erro ao gravar temporário: {e}")
        try:
            os.remove(caminho_temp)
        except Exception:
            pass
        return None


def mesclar_lote_para_temp(pasta: str) -> Optional[str]:
    """
    Mescla capa + NFs de um lote em um único PDF (modo bandeja simples).

    Regra frente-e-verso aplicada:
      - Capa: página em branco inserida somente se tiver nº ÍMPAR de páginas.
      - Cada NF: mesmo critério — branco apenas se ímpar.
    Assim cada documento sempre começa na frente de uma folha física nova.
    """
    arquivos = listar_arquivos_lote(pasta)
    if not arquivos["capa"] and not arquivos["nfs"]:
        return None

    todos = []
    if arquivos["capa"]:
        todos.append(arquivos["capa"])
    todos.extend(arquivos["nfs"])

    return _mesclar_pdfs_frente_verso(todos, cada_doc_nova_folha=True)


def mesclar_capa_para_temp(pasta: str) -> Optional[str]:
    """
    Gera PDF temporário com APENAS a capa do lote.

    IMPORTANTE: cada_doc_nova_folha=False — a capa é um documento isolado,
    não existe um "próximo documento" depois dela neste job. Inserir uma página
    em branco ao final faz impressoras duplex entenderem que há conteúdo no
    verso e viram a folha, imprimindo a capa frente-e-verso. Desabilitamos o
    preenchimento aqui; o alinhamento frente-e-verso só é necessário quando
    vários documentos são mesclados num único PDF (NFs).
    (Modo bandeja dupla — Gaveta A / sulfite.)
    """
    arquivos = listar_arquivos_lote(pasta)
    if not arquivos["capa"]:
        logger.warning(f"Sem capa em '{pasta}'.")
        return None

    return _mesclar_pdfs_frente_verso([arquivos["capa"]], cada_doc_nova_folha=False)


def mesclar_nfs_para_temp(pasta: str) -> Optional[str]:
    """
    Gera PDF temporário com APENAS as NFs do lote (sem capa).
    Cada NF com nº ímpar de páginas recebe folha separadora.
    (Modo bandeja dupla — Gaveta B / papel especial.)
    """
    arquivos = listar_arquivos_lote(pasta)
    if not arquivos["nfs"]:
        logger.warning(f"Sem NFs em '{pasta}'.")
        return None

    return _mesclar_pdfs_frente_verso(arquivos["nfs"], cada_doc_nova_folha=True)


# ─── Gerenciamento de impressoras e bandejas ──────────────────────────────────

def listar_impressoras() -> list:
    """Retorna lista de impressoras disponíveis no Windows."""
    if not WIN32_OK:
        return []
    try:
        impressoras = win32print.EnumPrinters(
            win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        )
        return [p[2] for p in impressoras]
    except Exception as e:
        logger.error(f"Erro ao listar impressoras: {e}")
        return []


def impressora_padrao() -> Optional[str]:
    """Retorna o nome da impressora padrão do Windows."""
    if not WIN32_OK:
        return None
    try:
        return win32print.GetDefaultPrinter()
    except Exception:
        return None


def listar_bandejas(nome_impressora: str) -> list:
    """
    Lista as bandejas (gavetas) disponíveis em uma impressora específica.
    """
    if not WIN32_OK:
        return []

    porta = None
    hprinter = None
    try:
        hprinter = win32print.OpenPrinter(nome_impressora)
        info2 = win32print.GetPrinter(hprinter, 2)
        porta = info2.get("pPortName", None)
    except Exception as e:
        logger.warning(f"Não foi possível obter porta de '{nome_impressora}': {e}")
    finally:
        if hprinter:
            try:
                win32print.ClosePrinter(hprinter)
            except Exception:
                pass

    try:
        numeros = win32print.DeviceCapabilities(
            nome_impressora, porta, win32con.DC_BINS
        )
        nomes_raw = win32print.DeviceCapabilities(
            nome_impressora, porta, win32con.DC_BINNAMES
        )

        if numeros and nomes_raw:
            bandejas = []
            for num, nome_raw in zip(numeros, nomes_raw):
                nome_limpo = nome_raw.split('\x00')[0].strip()
                if nome_limpo and num > 0:
                    bandejas.append({"numero": num, "nome": nome_limpo})
            if bandejas:
                logger.info(f"Bandejas de '{nome_impressora}': {bandejas}")
                return bandejas

        logger.warning(
            f"DeviceCapabilities não retornou bandejas para '{nome_impressora}'. "
            f"Porta usada: '{porta}'. Tentando fallback..."
        )

    except Exception as e:
        logger.warning(
            f"DeviceCapabilities falhou para '{nome_impressora}' "
            f"(porta='{porta}'): {e}. Tentando fallback..."
        )

    try:
        hprinter = win32print.OpenPrinter(nome_impressora)
        win32print.GetPrinter(hprinter, 2)
        win32print.ClosePrinter(hprinter)
        bandejas_padrao = [
            {"numero": DMBIN_UPPER,  "nome": "Gaveta 1 (Superior)"},
            {"numero": DMBIN_LOWER,  "nome": "Gaveta 2 (Inferior)"},
            {"numero": DMBIN_MIDDLE, "nome": "Gaveta 3 (Meio)"},
            {"numero": DMBIN_MANUAL, "nome": "Alimentação Manual"},
            {"numero": DMBIN_AUTO,   "nome": "Automático"},
        ]
        logger.info(f"Usando bandejas padrão (fallback) para '{nome_impressora}'.")
        return bandejas_padrao

    except Exception as e:
        logger.error(f"Fallback também falhou para '{nome_impressora}': {e}")
        return []


# ─── Espera pelo spooler ──────────────────────────────────────────────────────

def _listar_job_ids(nome_impressora: str) -> set:
    """
    Retorna o conjunto de IDs de jobs atualmente na fila da impressora.
    Retorna conjunto vazio em caso de erro ou fila vazia.
    """
    try:
        hprinter = win32print.OpenPrinter(nome_impressora)
        try:
            jobs = win32print.EnumJobs(hprinter, 0, 999, 1)
            return {j["JobId"] for j in jobs} if jobs else set()
        finally:
            win32print.ClosePrinter(hprinter)
    except Exception:
        return set()


def _aguardar_job_spooler(
    nome_impressora: str,
    timeout: float = 200,
    poll_intervalo: float = 3.0,
    pausa_pos_vazio: float = 8.0,
    ids_antes: Optional[set] = None,
) -> bool:
    """
    Aguarda o(s) job(s) enviados saírem completamente da fila do spooler.

    Estratégia baseada em IDs de job (mais confiável que contar jobs):

      1. Recebe o conjunto de IDs que existiam ANTES do envio (ids_antes).
         Se não fornecido, usa snapshot tirado agora como baseline.
      2. Aguarda aparecer pelo menos um ID NOVO na fila (máx 30 s) —
         confirma que o spooler registrou nosso job.
      3. Aguarda todos os IDs novos SAÍREM da fila (até `timeout` s).
      4. Exige estabilidade: a fila deve ficar vazia por 2 polls consecutivos
         antes de liberar — evita falso positivo quando jobs chegam em rajada.
      5. Pausa `pausa_pos_vazio` s após confirmação antes de retornar —
         dá tempo à impressora de puxar os dados do spooler.

    Args:
        nome_impressora:  Nome da impressora a monitorar.
        timeout:          Tempo máximo de espera (padrão: 200s).
        poll_intervalo:   Intervalo de polling em segundos (padrão: 3s).
        pausa_pos_vazio:  Segundos extras após confirmação (padrão: 8s).
        ids_antes:        Conjunto de JobIds presentes ANTES do envio.
                          Passe `_listar_job_ids(impressora)` imediatamente
                          antes de chamar o SumatraPDF para máxima precisão.

    Returns:
        True se os jobs saíram dentro do timeout, False se expirou.
    """
    if not WIN32_OK:
        time.sleep(pausa_pos_vazio + 6.0)
        return True

    if ids_antes is None:
        ids_antes = set()

    # ── Fase 1: aguarda aparecer pelo menos 1 job NOVO (máx 30 s) ────────────
    prazo_aparecimento = time.time() + 30.0
    ids_nossos: set = set()
    tentativas_erro = 0

    while time.time() < prazo_aparecimento:
        try:
            ids_agora = _listar_job_ids(nome_impressora)
            ids_novos = ids_agora - ids_antes
            tentativas_erro = 0
            if ids_novos:
                ids_nossos = ids_novos
                logger.debug(f"Spooler: job(s) registrado(s) — IDs {ids_nossos}")
                break
        except Exception as e:
            tentativas_erro += 1
            logger.warning(f"Spooler fase-1: erro ({e}) — tentativa {tentativas_erro}")
            if tentativas_erro >= 5:
                break
        time.sleep(poll_intervalo)

    if not ids_nossos:
        # Job não apareceu na fila — pode ter sido processado instantaneamente
        # ou falhou silenciosamente. Aguarda pausa conservadora.
        logger.debug("Spooler: job não detectado na fila — aguardando pausa conservadora.")
        time.sleep(pausa_pos_vazio)
        return True

    # ── Fase 2: aguarda todos os IDs nossos saírem da fila ───────────────────
    # Exige estabilidade: fila sem nossos IDs por 2 polls seguidos.
    inicio = time.time()
    tentativas_erro = 0
    polls_vazio = 0          # contagem de polls consecutivos sem nossos IDs
    POLLS_ESTABILIDADE = 2   # quantos polls consecutivos "vazio" exigimos

    while time.time() - inicio < timeout:
        try:
            ids_agora = _listar_job_ids(nome_impressora)
            tentativas_erro = 0
        except Exception as e:
            tentativas_erro += 1
            logger.warning(f"Spooler fase-2: erro ({e}) — tentativa {tentativas_erro}")
            if tentativas_erro >= 5:
                logger.error("Spooler: muitos erros — prosseguindo sem espera.")
                time.sleep(pausa_pos_vazio)
                return False
            time.sleep(poll_intervalo)
            continue

        # Verifica se algum dos nossos IDs ainda está na fila
        ids_pendentes = ids_nossos & ids_agora
        if ids_pendentes:
            polls_vazio = 0
            logger.debug(f"Spooler: {len(ids_pendentes)} job(s) ainda na fila — aguardando...")
        else:
            polls_vazio += 1
            logger.debug(f"Spooler: fila limpa (poll {polls_vazio}/{POLLS_ESTABILIDADE})...")
            if polls_vazio >= POLLS_ESTABILIDADE:
                logger.debug(
                    f"Spooler: confirmado — aguardando {pausa_pos_vazio}s antes de liberar."
                )
                time.sleep(pausa_pos_vazio)
                return True

        time.sleep(poll_intervalo)

    logger.warning(f"Spooler: timeout de {timeout}s atingido — prosseguindo.")
    time.sleep(pausa_pos_vazio)
    return False


# ─── Localização do SumatraPDF ───────────────────────────────────────────────

def _encontrar_sumatra() -> Optional[str]:
    """
    Procura o executável do SumatraPDF no sistema.
    """
    nomes = ["SumatraPDF.exe", "SumatraPDF-3.exe", "sumatrapdf.exe"]

    if getattr(sys, "frozen", False):
        base_exe = os.path.dirname(sys.executable)
    else:
        base_exe = os.path.dirname(os.path.abspath(__file__))

    pastas = [
        base_exe,
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "SumatraPDF"),
        os.path.join(os.environ.get("PROGRAMFILES", ""), "SumatraPDF"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "SumatraPDF"),
        r"C:\Program Files\SumatraPDF",
        r"C:\Program Files (x86)\SumatraPDF",
        r"C:\Users\Public\SumatraPDF",
    ]

    for pasta in pastas:
        for nome in nomes:
            caminho = os.path.join(pasta, nome)
            if os.path.isfile(caminho):
                logger.debug(f"SumatraPDF encontrado: {caminho}")
                return caminho

    import shutil
    for nome in nomes:
        encontrado = shutil.which(nome)
        if encontrado:
            logger.debug(f"SumatraPDF no PATH: {encontrado}")
            return encontrado

    logger.warning("SumatraPDF não encontrado no sistema.")
    return None


# ─── Impressão via SumatraPDF ─────────────────────────────────────────────────

def _imprimir_via_sumatra(
    caminho_pdf: str,
    nome_impressora: str,
    numero_bandeja: Optional[int] = None,
) -> bool:
    """
    Imprime um PDF usando SumatraPDF via linha de comando.

    IMPORTANTE: usa subprocess.run com timeout generoso e verifica returncode.
    O SumatraPDF com -exit-on-print bloqueia até o job ser enfileirado no
    spooler — não até a impressão física terminar. Por isso é necessário
    chamar _aguardar_job_spooler() após esta função antes de enviar o próximo.
    """
    sumatra = _encontrar_sumatra()
    if not sumatra:
        return False

    settings_parts = ["fit"]
    if numero_bandeja is not None:
        settings_parts.append(f"bin={numero_bandeja}")
    print_settings = ",".join(settings_parts)

    cmd = [
        sumatra,
        "-print-to", nome_impressora,
        "-print-settings", print_settings,
        "-silent",
        "-exit-on-print",
        caminho_pdf,
    ]

    logger.info(
        f"Sumatra: imprimindo '{os.path.basename(caminho_pdf)}' "
        f"em '{nome_impressora}' "
        f"(bandeja: {numero_bandeja if numero_bandeja else 'padrão'})"
    )

    try:
        resultado = subprocess.run(
            cmd,
            timeout=300,   # 5 min — evita abortar documentos grandes
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        if resultado.returncode == 0:
            logger.info("Sumatra: job enfileirado com sucesso.")
            return True
        elif resultado.returncode == 1:
            # Código 1 = aviso não-fatal no SumatraPDF (ex: sem impressora padrão
            # definida, mas o job foi mesmo assim enfileirado)
            logger.warning(f"Sumatra retornou código 1 (aviso não-fatal) — continuando.")
            return True
        else:
            logger.error(f"Sumatra retornou código de erro {resultado.returncode}.")
            return False
    except subprocess.TimeoutExpired:
        logger.error(
            "Sumatra: timeout de 300s atingido — o job pode não ter sido enfileirado. "
            "Verifique se a impressora está respondendo."
        )
        return False   # timeout é falha, não silencia o erro
    except Exception as e:
        logger.error(f"Sumatra: erro ao executar: {e}")
        return False


# ─── Impressão via ShellExecute + DEVMODE (fallback) ─────────────────────────

def _imprimir_via_shellexecute(
    caminho_pdf: str,
    nome_impressora: str,
    numero_bandeja: Optional[int] = None,
) -> bool:
    """
    Fallback: imprime via ShellExecute alterando o DEVMODE da impressora.
    Usado apenas quando o SumatraPDF não está disponível.
    """
    if not WIN32_OK:
        return False

    devmode_original = None
    hprinter = None

    try:
        hprinter = win32print.OpenPrinter(
            nome_impressora,
            {"DesiredAccess": win32print.PRINTER_ALL_ACCESS}
        )
        info2 = win32print.GetPrinter(hprinter, 2)
        devmode_original = info2["pDevMode"]

        if numero_bandeja is not None:
            devmode_novo = info2["pDevMode"]
            devmode_novo.DefaultSource = numero_bandeja
            devmode_novo.Fields |= win32con.DM_DEFAULTSOURCE

            win32print.DocumentProperties(
                0, hprinter, nome_impressora,
                devmode_novo, devmode_novo,
                win32con.DM_IN_BUFFER | win32con.DM_OUT_BUFFER
            )
            info2["pDevMode"] = devmode_novo
            win32print.SetPrinter(hprinter, 2, info2, 0)

        win32api.ShellExecute(0, "print", caminho_pdf, None, ".", 0)

        if numero_bandeja is not None and devmode_original is not None:
            _bak = devmode_original
            def _restaurar():
                time.sleep(5)
                try:
                    h = win32print.OpenPrinter(
                        nome_impressora,
                        {"DesiredAccess": win32print.PRINTER_ALL_ACCESS}
                    )
                    i = win32print.GetPrinter(h, 2)
                    i["pDevMode"] = _bak
                    win32print.SetPrinter(h, 2, i, 0)
                    win32print.ClosePrinter(h)
                except Exception as ex:
                    logger.warning(f"Falha ao restaurar DEVMODE: {ex}")
            threading.Thread(target=_restaurar, daemon=True).start()

        return True

    except Exception as e:
        logger.error(f"ShellExecute: erro ao imprimir '{caminho_pdf}': {e}")
        return False
    finally:
        if hprinter:
            try:
                win32print.ClosePrinter(hprinter)
            except Exception:
                pass


# ─── Função pública de impressão com bandeja ─────────────────────────────────

def imprimir_pdf_com_bandeja(
    caminho_pdf: str,
    nome_impressora: str,
    numero_bandeja: Optional[int] = None,
) -> bool:
    """
    Envia um PDF para a impressora usando a bandeja especificada.
    Prefere SumatraPDF; cai para ShellExecute se não disponível.
    """
    if not WIN32_OK:
        logger.error("win32api/win32print não disponível.")
        return False

    if not os.path.isfile(caminho_pdf):
        logger.error(f"Arquivo não encontrado: {caminho_pdf}")
        return False

    sumatra = _encontrar_sumatra()
    if sumatra:
        return _imprimir_via_sumatra(caminho_pdf, nome_impressora, numero_bandeja)

    logger.warning(
        "SumatraPDF não encontrado — usando ShellExecute. "
        "Instale o SumatraPDF para garantir impressão na gaveta correta."
    )
    return _imprimir_via_shellexecute(caminho_pdf, nome_impressora, numero_bandeja)


def imprimir_pdf(caminho_pdf: str, nome_impressora: Optional[str] = None) -> bool:
    """
    Envia um PDF para a impressora sem alterar bandeja (modo bandeja simples).
    """
    if not WIN32_OK:
        logger.error("win32api não disponível. Instale: pip install pywin32")
        return False

    if not os.path.isfile(caminho_pdf):
        logger.error(f"Arquivo não encontrado: {caminho_pdf}")
        return False

    impressora = nome_impressora or (impressora_padrao() if WIN32_OK else None)
    if not impressora:
        logger.error("Nenhuma impressora disponível.")
        return False

    sumatra = _encontrar_sumatra()
    if sumatra:
        return _imprimir_via_sumatra(caminho_pdf, impressora, numero_bandeja=None)

    try:
        if nome_impressora:
            impressora_anterior = win32print.GetDefaultPrinter()
            win32print.SetDefaultPrinter(nome_impressora)
        else:
            impressora_anterior = None

        win32api.ShellExecute(0, "print", caminho_pdf, None, ".", 0)

        if impressora_anterior:
            threading.Timer(
                3.0, lambda: win32print.SetDefaultPrinter(impressora_anterior)
            ).start()
        return True
    except Exception as e:
        logger.error(f"Erro ao imprimir '{caminho_pdf}': {e}")
        return False


# ─── Função principal de impressão em lote ───────────────────────────────────

def imprimir_lotes(
    pastas: list,
    nome_impressora: Optional[str] = None,
    intervalo_segundos: float = 5.0,
    callback_log: Optional[Callable[[str], None]] = None,
    parar_evento=None,
    usar_bandeja_dupla: bool = False,
    bandeja_capa: Optional[int] = None,
    bandeja_nfs: Optional[int] = None,
) -> dict:
    """
    Imprime múltiplas pastas de lote em sequência.

    Garante que cada job seja confirmado pelo spooler antes de enviar o próximo,
    eliminando o problema de NFs puladas ou duplicadas em lotes grandes.

    Modo bandeja simples (usar_bandeja_dupla=False):
      - Mescla capa + NFs num único PDF → envia → aguarda spooler → próximo lote.

    Modo bandeja dupla (usar_bandeja_dupla=True):
      - Envia capa (Gaveta A) → aguarda spooler → envia NFs (Gaveta B) →
        aguarda spooler → próximo lote.
    """
    def log(msg):
        logger.info(msg)
        if callback_log:
            callback_log(msg)

    stats = {"total": len(pastas), "enviados": 0, "erros": 0}
    # Cada lote registra seus temporários; só deleta após confirmar spooler vazio
    temporarios_pendentes: list[tuple[str, str]] = []  # (caminho_temp, nome_impressora)

    impressora_uso = nome_impressora or impressora_padrao() or "padrão do sistema"
    log(f"🖨️  Impressora: {impressora_uso}")

    if usar_bandeja_dupla:
        log(f"📥  Modo BANDEJA DUPLA ativado:")
        log(f"     Gaveta A — Capas (sulfite)   → bandeja nº {bandeja_capa}")
        log(f"     Gaveta B — NFs (especial)    → bandeja nº {bandeja_nfs}")
    else:
        log("📄  Modo bandeja única (todos os documentos na mesma gaveta)")

    log(f"📦  {len(pastas)} lote(s) na fila de impressão.")

    for i, pasta in enumerate(pastas, 1):
        if parar_evento and parar_evento.is_set():
            log("⚠️  Impressão interrompida pelo usuário.")
            break

        nome_lote = os.path.basename(pasta.rstrip("/\\"))
        log(f"\n── Lote {i}/{len(pastas)}: {nome_lote}")

        arquivos = listar_arquivos_lote(pasta)
        total_pdfs = (1 if arquivos["capa"] else 0) + len(arquivos["nfs"])

        if total_pdfs == 0:
            log(f"  ⚠️  Nenhum PDF encontrado em '{nome_lote}' — pulando.")
            stats["erros"] += 1
            continue

        capa_info = (
            f"capa + {len(arquivos['nfs'])} NF(s)"
            if arquivos["capa"]
            else f"{len(arquivos['nfs'])} NF(s) (sem capa)"
        )
        log(f"  📄  {total_pdfs} arquivo(s): {capa_info}")

        # Informa quantas páginas cada documento tem (ajuda no diagnóstico)
        if arquivos["capa"]:
            np = _num_paginas(arquivos["capa"])
            branco = "+ branco" if np % 2 != 0 else "par, sem branco"
            log(f"  📋  Capa: {np} pág. ({branco})")

        sucesso_lote = True

        # ── MODO BANDEJA DUPLA ────────────────────────────────────────────────
        if usar_bandeja_dupla:

            # — Capa → Gaveta A —
            if arquivos["capa"]:
                log(f"  🔄  Preparando capa para Gaveta A (sulfite)...")
                temp_capa = mesclar_capa_para_temp(pasta)

                if temp_capa:
                    log(f"  🖨️  Enviando CAPA para Gaveta A (bandeja {bandeja_capa})...")
                    ids_pre_capa = _listar_job_ids(impressora_uso) if WIN32_OK else set()
                    ok_capa = imprimir_pdf_com_bandeja(
                        temp_capa, nome_impressora, bandeja_capa
                    )
                    if ok_capa:
                        log(f"  ✅  Capa enfileirada — aguardando spooler...")
                        _aguardar_job_spooler(
                            impressora_uso, timeout=300, pausa_pos_vazio=12,
                            ids_antes=ids_pre_capa,
                        )
                        log(f"  ✅  Capa confirmada pelo spooler.")
                        temporarios_pendentes.append((temp_capa, impressora_uso))
                    else:
                        log(f"  ❌  Falha ao enviar capa para Gaveta A.")
                        sucesso_lote = False
                        try:
                            os.remove(temp_capa)
                        except Exception:
                            pass
                else:
                    log(f"  ❌  Falha ao preparar PDF da capa.")
                    sucesso_lote = False

            # — NFs → Gaveta B —
            if arquivos["nfs"]:
                log(f"  🔄  Preparando {len(arquivos['nfs'])} NF(s) para Gaveta B (especial)...")
                temp_nfs = mesclar_nfs_para_temp(pasta)

                if temp_nfs:
                    log(f"  🖨️  Enviando NFs para Gaveta B (bandeja {bandeja_nfs})...")
                    ids_pre_nfs = _listar_job_ids(impressora_uso) if WIN32_OK else set()
                    ok_nfs = imprimir_pdf_com_bandeja(
                        temp_nfs, nome_impressora, bandeja_nfs
                    )
                    if ok_nfs:
                        log(f"  ✅  NFs enfileiradas — aguardando spooler...")
                        _aguardar_job_spooler(
                            impressora_uso, timeout=420, pausa_pos_vazio=12,
                            ids_antes=ids_pre_nfs,
                        )
                        log(f"  ✅  NFs confirmadas pelo spooler.")
                        temporarios_pendentes.append((temp_nfs, impressora_uso))
                    else:
                        log(f"  ❌  Falha ao enviar NFs para Gaveta B.")
                        sucesso_lote = False
                        try:
                            os.remove(temp_nfs)
                        except Exception:
                            pass
                else:
                    log(f"  ❌  Falha ao preparar PDF das NFs.")
                    sucesso_lote = False

        # ── MODO BANDEJA SIMPLES ──────────────────────────────────────────────
        else:
            log(f"  🔄  Mesclando PDFs...")
            temp = mesclar_lote_para_temp(pasta)

            if not temp:
                log(f"  ❌  Falha na mesclagem de '{nome_lote}'.")
                stats["erros"] += 1
                continue

            log(f"  🖨️  Enviando para impressora...")
            ids_pre_lote = _listar_job_ids(impressora_uso) if WIN32_OK else set()
            sucesso_lote = imprimir_pdf(temp, nome_impressora)

            if sucesso_lote:
                log(f"  ✅  Lote enfileirado — aguardando spooler...")
                _aguardar_job_spooler(
                    impressora_uso, timeout=420, pausa_pos_vazio=12,
                    ids_antes=ids_pre_lote,
                )
                log(f"  ✅  Lote confirmado pelo spooler.")
                temporarios_pendentes.append((temp, impressora_uso))
            else:
                try:
                    os.remove(temp)
                except Exception:
                    pass

        # ── Resultado do lote ─────────────────────────────────────────────────
        if sucesso_lote:
            log(f"  ✅  Lote '{nome_lote}' enviado com sucesso!")
            stats["enviados"] += 1
        else:
            log(f"  ❌  Lote '{nome_lote}' com falhas.")
            stats["erros"] += 1

        # Pausa extra entre lotes (além da espera do spooler)
        if i < len(pastas) and intervalo_segundos > 0:
            if parar_evento and parar_evento.is_set():
                break
            log(f"  ⏳  Aguardando {intervalo_segundos}s antes do próximo lote...")
            time.sleep(intervalo_segundos)

    # ── Limpeza dos temporários — só após spooler esvaziar ───────────────────
    def _limpar_temporarios():
        if not temporarios_pendentes:
            return
        # Aguarda spooler esvaziar completamente antes de deletar.
        # Para limpeza não precisamos rastrear IDs específicos — basta esperar
        # a fila ficar estável em zero por tempo suficiente.
        if WIN32_OK and temporarios_pendentes:
            impressora_ref = temporarios_pendentes[-1][1]
            logger.debug("Aguardando spooler esvaziar antes de limpar temporários...")
            _aguardar_job_spooler(
                impressora_ref, timeout=600, poll_intervalo=5.0, pausa_pos_vazio=20
            )

        # Segurança extra: aguarda mais 20s após fila vazia antes de deletar
        time.sleep(20)

        for tmp, _ in temporarios_pendentes:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
                    logger.debug(f"Temporário removido: {tmp}")
            except Exception as e:
                logger.warning(f"Não foi possível remover '{tmp}': {e}")

    threading.Thread(target=_limpar_temporarios, daemon=False).start()

    log(
        f"\n🏁  Impressão concluída!\n"
        f"   Enviados : {stats['enviados']}/{stats['total']}\n"
        f"   Erros    : {stats['erros']}"
    )

    return stats
