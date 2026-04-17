# lote_splitter.py - Separação de arquivo de capas de lote e cruzamento com notas fiscais
#
# PROBLEMA QUE ESTE MÓDULO RESOLVE:
# O sistema recebe um único PDF contendo MÚLTIPLAS capas de lote.
# Cada capa pode ocupar MAIS DE UMA PÁGINA (cabeçalho + páginas de continuação).
# Este módulo:
#   1. Abre o PDF de capas e identifica grupos de páginas por SID
#   2. Agrupa páginas de continuação à capa anterior (mesmo SID)
#   3. Para cada capa, cria uma pasta Modal_SIDXXXXX no destino
#   4. Salva TODAS as páginas da capa como um único PDF dentro da pasta
#   5. Cruza os números de NF com os arquivos de notas na pasta de origem
#      e move/copia cada nota para a pasta do seu SID

import os
import re
import shutil
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)

# Tenta importar as bibliotecas de PDF
try:
    import pdfplumber
    PDFPLUMBER_OK = True
except ImportError:
    PDFPLUMBER_OK = False

try:
    from pypdf import PdfReader, PdfWriter
    PYPDF_OK = True
except ImportError:
    try:
        import PyPDF2 as pypdf_compat
        PdfReader = pypdf_compat.PdfReader
        PdfWriter = pypdf_compat.PdfWriter
        PYPDF_OK = True
    except ImportError:
        PYPDF_OK = False


# ─── Estrutura de dados de uma Capa de Lote ───────────────────────────────────

@dataclass
class CapaDeLote:
    """Representa os dados extraídos de uma capa de lote (pode ter múltiplas páginas)."""
    pagina_inicio: int                   # Índice da primeira página (0-based)
    paginas: List[int] = field(default_factory=list)  # Todas as páginas desta capa
    modal: Optional[str] = None          # Ex: "FAVORITA", "PATRUS"
    sid: Optional[str] = None            # Ex: "316878"
    transportadora_nome: Optional[str] = None
    numeros_nf: list = field(default_factory=list)
    texto_bruto: str = ""
    erro: Optional[str] = None

    @property
    def nome_pasta(self) -> str:
        """Retorna o nome da pasta que será criada para este lote."""
        if self.modal and self.sid:
            return f"{self.modal}_SID{self.sid}"
        if self.sid:
            return f"SID{self.sid}"
        return f"CAPA_PAGINA_{self.pagina_inicio + 1}"


# ─── Extração de texto de uma página ──────────────────────────────────────────

def _extrair_texto_pagina(caminho_pdf: str, indice_pagina: int) -> str:
    """Extrai o texto de uma página específica do PDF."""
    texto = ""

    if PDFPLUMBER_OK:
        try:
            with pdfplumber.open(caminho_pdf) as pdf:
                if indice_pagina < len(pdf.pages):
                    t = pdf.pages[indice_pagina].extract_text()
                    if t:
                        texto = t
        except Exception as e:
            logger.debug(f"pdfplumber falhou na página {indice_pagina}: {e}")

    if not texto and PYPDF_OK:
        try:
            reader = PdfReader(caminho_pdf)
            if indice_pagina < len(reader.pages):
                t = reader.pages[indice_pagina].extract_text()
                if t:
                    texto = t
        except Exception as e:
            logger.debug(f"pypdf falhou na página {indice_pagina}: {e}")

    return texto


# ─── Detecção de cabeçalho de nova capa ───────────────────────────────────────

def _tem_cabecalho_capa(texto: str) -> bool:
    """
    Verifica se uma página contém um cabeçalho de nova capa de lote,
    ou seja, se possui Modal e SID definidos.

    Uma página de CONTINUAÇÃO não terá "Modal:" nem "Shipment: SID..." —
    ela apenas continua a tabela de NFs da capa anterior.
    """
    tem_modal = bool(re.search(r'Modal\s*[:\s]+[A-Z]{3,20}', texto, re.IGNORECASE))
    tem_sid   = bool(re.search(r'(?:Shipment\s*[:\s]+)?SID\s*\d{4,10}', texto, re.IGNORECASE))
    return tem_modal or tem_sid


# ─── Agrupamento de páginas em capas ──────────────────────────────────────────

def _agrupar_paginas_em_capas(
    caminho_pdf: str,
    total_paginas: int,
) -> List[Tuple[List[int], str]]:
    """
    Percorre todas as páginas do PDF e agrupa as que pertencem à mesma capa.

    Regra de agrupamento:
    - Se a página tem Modal ou SID → início de nova capa
    - Se não tem → continuação da capa anterior (acumula na mesma)

    Returns:
        Lista de tuplas (lista_de_indices_paginas, texto_concatenado)
    """
    grupos: List[Tuple[List[int], str]] = []
    paginas_atuais: List[int] = []
    texto_atual = ""

    for i in range(total_paginas):
        texto = _extrair_texto_pagina(caminho_pdf, i)

        if _tem_cabecalho_capa(texto):
            # Salva o grupo anterior (se existir)
            if paginas_atuais:
                grupos.append((paginas_atuais, texto_atual))
            # Inicia novo grupo
            paginas_atuais = [i]
            texto_atual = texto
        else:
            # Página de continuação — acumula no grupo atual
            if paginas_atuais:
                paginas_atuais.append(i)
                texto_atual += "\n" + texto
            else:
                # Página antes de qualquer cabeçalho — trata como capa avulsa
                grupos.append(([i], texto))

    # Salva o último grupo
    if paginas_atuais:
        grupos.append((paginas_atuais, texto_atual))

    return grupos


# ─── Parsing do texto consolidado de uma capa ─────────────────────────────────

def _parsear_capa(texto: str, paginas: List[int]) -> CapaDeLote:
    """
    Extrai Modal, SID, transportadora e lista de NFs do texto consolidado
    de todas as páginas de uma capa.
    """
    capa = CapaDeLote(
        pagina_inicio=paginas[0],
        paginas=paginas,
        texto_bruto=texto,
    )

    # ── 1. Modal ──
    match_modal = re.search(
        r'Modal\s*[:\s]+([A-Z]{3,20})',
        texto, re.IGNORECASE
    )
    if match_modal:
        capa.modal = match_modal.group(1).strip().upper()

    # ── 2. SID ──
    match_sid = re.search(
        r'(?:Shipment\s*[:\s]+)?SID\s*0*(\d{4,10})',
        texto, re.IGNORECASE
    )
    if match_sid:
        capa.sid = match_sid.group(1).strip()

    # ── 3. Nome completo da transportadora ──
    match_transp = re.search(
        r'Transportadora\s*[:\s]+(.+?)(?:\n|$)',
        texto, re.IGNORECASE
    )
    if match_transp:
        capa.transportadora_nome = match_transp.group(1).strip()

    # ── 4. Números de NF (9 dígitos começando com 0) ──
    numeros_encontrados = re.findall(r'\b(0\d{8})\b', texto)
    vistos = set()
    for nf in numeros_encontrados:
        if nf not in vistos:
            vistos.add(nf)
            capa.numeros_nf.append(nf)

    logger.info(
        f"  Páginas {[p+1 for p in paginas]}: Modal={capa.modal} | "
        f"SID={capa.sid} | NFs={len(capa.numeros_nf)}"
    )

    return capa


# ─── Salvar múltiplas páginas como um único PDF ───────────────────────────────

def _salvar_paginas_pdf(
    caminho_pdf_origem: str,
    indices_paginas: List[int],
    caminho_destino: str,
) -> bool:
    """
    Salva um conjunto de páginas (pode ser mais de uma) como um único PDF.
    """
    if not PYPDF_OK:
        logger.error("pypdf/PyPDF2 não disponível.")
        return False

    try:
        reader = PdfReader(caminho_pdf_origem)
        writer = PdfWriter()
        for i in indices_paginas:
            writer.add_page(reader.pages[i])
        with open(caminho_destino, "wb") as f:
            writer.write(f)
        return True
    except Exception as e:
        logger.error(f"Erro ao salvar páginas {indices_paginas}: {e}")
        return False


# ─── Busca de arquivo de NF ───────────────────────────────────────────────────

def _encontrar_arquivo_nf(numero_nf: str, pasta_origem: str) -> Optional[str]:
    """
    Procura o arquivo PDF de uma NF específica na pasta de origem.
    Aceita o número com ou sem zeros à esquerda.
    """
    numero_sem_zeros = numero_nf.lstrip('0')

    for raiz, _, arquivos in os.walk(pasta_origem):
        for arquivo in arquivos:
            if not arquivo.lower().endswith('.pdf'):
                continue
            nome_sem_ext = os.path.splitext(arquivo)[0]
            if numero_nf in nome_sem_ext or numero_sem_zeros in nome_sem_ext:
                return os.path.join(raiz, arquivo)

    return None


# ─── Função principal de processamento ───────────────────────────────────────

def processar_capas_de_lote(
    caminho_pdf_capas: str,
    pasta_origem_nfs: str,
    pasta_destino: str,
    manter_copia: bool = True,
    callback_log=None,
) -> dict:
    """
    Processa um PDF de capas de lote com suporte a capas multi-página:
    - Agrupa páginas de continuação à capa correspondente
    - Cria uma pasta por capa (Modal_SIDxxxxxx)
    - Salva TODAS as páginas da capa num único PDF dentro da pasta
    - Cruza e move/copia as NFs correspondentes

    Args:
        caminho_pdf_capas: Caminho do PDF com todas as capas concatenadas.
        pasta_origem_nfs: Pasta onde as notas fiscais PDF estão embaralhadas.
        pasta_destino: Pasta raiz onde a estrutura organizada será criada.
        manter_copia: Se True, copia os arquivos (não apaga originais).
        callback_log: Função opcional para enviar mensagens de log para a UI.

    Returns:
        Dicionário com estatísticas do processamento.
    """
    def log(msg):
        logger.info(msg)
        if callback_log:
            callback_log(msg)

    stats = {
        "total_capas": 0,
        "capas_ok": 0,
        "nfs_encontradas": 0,
        "nfs_nao_encontradas": 0,
        "erros": 0,
    }

    if not os.path.isfile(caminho_pdf_capas):
        log(f"❌ Arquivo de capas não encontrado: {caminho_pdf_capas}")
        return stats

    if not PYPDF_OK:
        log("❌ Instale pypdf ou PyPDF2 para usar o separador de capas.")
        return stats

    try:
        reader = PdfReader(caminho_pdf_capas)
        total_paginas = len(reader.pages)
    except Exception as e:
        log(f"❌ Erro ao abrir PDF de capas: {e}")
        return stats

    log(f"📋 PDF de capas: {total_paginas} página(s) encontrada(s).")

    # ── Agrupar páginas em capas ──
    grupos = _agrupar_paginas_em_capas(caminho_pdf_capas, total_paginas)
    log(f"📦 {len(grupos)} capa(s) identificada(s) (capas multi-página agrupadas).")
    stats["total_capas"] = len(grupos)

    # ── Processar cada capa ──
    for idx, (paginas, texto) in enumerate(grupos):
        desc_pags = f"p.{paginas[0]+1}" if len(paginas) == 1 else f"p.{paginas[0]+1}–{paginas[-1]+1}"
        log(f"\n── Processando capa {idx + 1}/{len(grupos)} ({desc_pags})...")

        if not texto.strip():
            log(f"  ⚠️ Capa {idx + 1}: sem texto extraível — pulando.")
            stats["erros"] += 1
            continue

        capa = _parsear_capa(texto, paginas)

        # Criar pasta de destino
        pasta_lote = os.path.join(pasta_destino, capa.nome_pasta)
        os.makedirs(pasta_lote, exist_ok=True)

        # Salvar todas as páginas da capa como um único PDF
        nome_capa_pdf = f"CAPA_{capa.nome_pasta}.pdf"
        caminho_capa_destino = os.path.join(pasta_lote, nome_capa_pdf)
        salvou = _salvar_paginas_pdf(caminho_pdf_capas, paginas, caminho_capa_destino)
        if salvou:
            npags = len(paginas)
            log(f"  ✅ Capa salva ({npags} pág.) → {capa.nome_pasta}/{nome_capa_pdf}")
        else:
            log(f"  ⚠️ Não foi possível salvar a capa PDF.")

        # Cruzar NFs
        if not capa.numeros_nf:
            log(f"  ℹ️ Nenhum número de NF identificado nesta capa.")
        else:
            log(f"  🔍 Procurando {len(capa.numeros_nf)} NF(s): {', '.join(capa.numeros_nf)}")

        for numero_nf in capa.numeros_nf:
            arquivo_nf = _encontrar_arquivo_nf(numero_nf, pasta_origem_nfs)

            if arquivo_nf:
                nome_arquivo = os.path.basename(arquivo_nf)
                destino_nf = os.path.join(pasta_lote, nome_arquivo)

                if os.path.exists(destino_nf):
                    base, ext = os.path.splitext(destino_nf)
                    contador = 1
                    while os.path.exists(f"{base}_{contador}{ext}"):
                        contador += 1
                    destino_nf = f"{base}_{contador}{ext}"

                try:
                    if manter_copia:
                        shutil.copy2(arquivo_nf, destino_nf)
                        acao = "Copiada"
                    else:
                        shutil.move(arquivo_nf, destino_nf)
                        acao = "Movida"

                    log(f"    ✅ NF {numero_nf} — {acao} → {capa.nome_pasta}/")
                    stats["nfs_encontradas"] += 1

                except Exception as e:
                    log(f"    ❌ NF {numero_nf} — Erro ao mover/copiar: {e}")
                    stats["erros"] += 1
            else:
                log(f"    ⚠️ NF {numero_nf} — arquivo não encontrado na pasta de origem.")
                stats["nfs_nao_encontradas"] += 1

        stats["capas_ok"] += 1

    log(
        f"\n🏁 Separação de capas concluída!\n"
        f"   Capas processadas : {stats['capas_ok']}/{stats['total_capas']}\n"
        f"   NFs encontradas   : {stats['nfs_encontradas']}\n"
        f"   NFs não achadas   : {stats['nfs_nao_encontradas']}\n"
        f"   Erros             : {stats['erros']}"
    )

    return stats
