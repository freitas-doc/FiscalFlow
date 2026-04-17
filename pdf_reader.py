# pdf_reader.py - Módulo responsável pela leitura e extração de dados dos PDFs

import re
import os
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Tenta importar pdfplumber (preferencial) e PyPDF2 como fallback
try:
    import pdfplumber
    PDFPLUMBER_DISPONIVEL = True
except ImportError:
    PDFPLUMBER_DISPONIVEL = False
    logger.warning("pdfplumber não disponível. Tentando PyPDF2...")

try:
    import PyPDF2
    PYPDF2_DISPONIVEL = True
except ImportError:
    PYPDF2_DISPONIVEL = False
    logger.warning("PyPDF2 não disponível.")


class DadosNota:
    """Estrutura de dados para armazenar informações extraídas de uma nota fiscal."""

    def __init__(self):
        self.transportadora: Optional[str] = None
        self.data_emissao: Optional[str] = None   # formato AAAA-MM-DD
        self.sid: Optional[str] = None
        self.texto_completo: str = ""
        self.erro: Optional[str] = None

    def __repr__(self):
        return (
            f"DadosNota(transportadora={self.transportadora}, "
            f"data={self.data_emissao}, sid={self.sid})"
        )


def extrair_texto_pdf(caminho_pdf: str) -> str:
    """
    Extrai todo o texto de um arquivo PDF.
    Tenta primeiro com pdfplumber, depois com PyPDF2 como fallback.

    Args:
        caminho_pdf: Caminho completo para o arquivo PDF.

    Returns:
        String com todo o texto extraído do PDF.

    Raises:
        RuntimeError: Se nenhuma biblioteca estiver disponível ou a leitura falhar.
    """
    texto = ""

    # Tentativa 1: pdfplumber (melhor extração de texto)
    if PDFPLUMBER_DISPONIVEL:
        try:
            with pdfplumber.open(caminho_pdf) as pdf:
                for pagina in pdf.pages:
                    texto_pagina = pagina.extract_text()
                    if texto_pagina:
                        texto += texto_pagina + "\n"
            if texto.strip():
                return texto
        except Exception as e:
            logger.debug(f"pdfplumber falhou em '{caminho_pdf}': {e}")

    # Tentativa 2: PyPDF2 como fallback
    if PYPDF2_DISPONIVEL:
        try:
            with open(caminho_pdf, "rb") as f:
                leitor = PyPDF2.PdfReader(f)
                for pagina in leitor.pages:
                    texto_pagina = pagina.extract_text()
                    if texto_pagina:
                        texto += texto_pagina + "\n"
            if texto.strip():
                return texto
        except Exception as e:
            logger.debug(f"PyPDF2 falhou em '{caminho_pdf}': {e}")

    # Nenhuma biblioteca conseguiu extrair o texto
    raise RuntimeError(
        f"Não foi possível extrair texto de '{caminho_pdf}'. "
        "Verifique se pdfplumber ou PyPDF2 estão instalados."
    )


def detectar_transportadora(texto: str, transportadoras: list) -> Optional[str]:
    """
    Detecta o nome de uma transportadora no texto do PDF.

    A busca é case-insensitive e procura pela transportadora como palavra
    ou sequência de palavras no texto.

    Args:
        texto: Texto extraído do PDF.
        transportadoras: Lista de nomes de transportadoras para buscar.

    Returns:
        Nome da transportadora encontrada (em maiúsculas) ou None.
    """
    texto_upper = texto.upper()
    for transportadora in transportadoras:
        # Busca pelo nome da transportadora como palavra isolada ou sequência
        padrao = r'\b' + re.escape(transportadora.upper()) + r'\b'
        if re.search(padrao, texto_upper):
            return transportadora.upper()
    return None


def detectar_data_emissao(texto: str) -> Optional[str]:
    """
    Detecta e extrai a data de emissão de uma nota fiscal no texto.

    Tenta múltiplos padrões de data comuns em notas fiscais brasileiras.

    Args:
        texto: Texto extraído do PDF.

    Returns:
        Data no formato 'AAAA-MM-DD' ou None se não encontrada.
    """
    # Padrões de data que podem aparecer em notas fiscais brasileiras
    padroes = [
        # DD/MM/AAAA precedido de "emissão", "emitido", "data"
        r'(?:data\s*de\s*emiss[aã]o|emiss[aã]o|emitido\s*em)[:\s]*(\d{2})[/\-\.](\d{2})[/\-\.](\d{4})',
        # DD/MM/AAAA genérico
        r'(\d{2})[/\-\.](\d{2})[/\-\.](\d{4})',
        # AAAA-MM-DD (ISO)
        r'(\d{4})[/\-\.](\d{2})[/\-\.](\d{2})',
        # DD de Mês de AAAA (ex: 14 de março de 2026)
        r'(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})',
    ]

    meses_pt = {
        'janeiro': '01', 'fevereiro': '02', 'março': '03', 'marco': '03',
        'abril': '04', 'maio': '05', 'junho': '06', 'julho': '07',
        'agosto': '08', 'setembro': '09', 'outubro': '10',
        'novembro': '11', 'dezembro': '12',
    }

    texto_lower = texto.lower()

    # Padrão específico para "Data de Emissão" (mais confiável)
    match = re.search(padroes[0], texto_lower)
    if match:
        dia, mes, ano = match.group(1), match.group(2), match.group(3)
        try:
            data = datetime.strptime(f"{dia}/{mes}/{ano}", "%d/%m/%Y")
            return data.strftime("%Y-%m-%d")
        except ValueError:
            pass

    # Padrão DD/MM/AAAA genérico
    for match in re.finditer(padroes[1], texto):
        dia, mes, ano = match.group(1), match.group(2), match.group(3)
        try:
            data = datetime.strptime(f"{dia}/{mes}/{ano}", "%d/%m/%Y")
            # Filtra datas claramente inválidas (ex: números de NF, CNPJ)
            if 2000 <= data.year <= 2099:
                return data.strftime("%Y-%m-%d")
        except ValueError:
            continue

    # Padrão ISO AAAA-MM-DD
    for match in re.finditer(padroes[2], texto):
        ano, mes, dia = match.group(1), match.group(2), match.group(3)
        try:
            data = datetime.strptime(f"{ano}-{mes}-{dia}", "%Y-%m-%d")
            if 2000 <= data.year <= 2099:
                return data.strftime("%Y-%m-%d")
        except ValueError:
            continue

    # Padrão "DD de Mês de AAAA"
    match = re.search(padroes[3], texto_lower)
    if match:
        dia = match.group(1).zfill(2)
        mes_nome = match.group(2).lower()
        ano = match.group(3)
        mes_num = meses_pt.get(mes_nome)
        if mes_num:
            try:
                data = datetime.strptime(f"{dia}/{mes_num}/{ano}", "%d/%m/%Y")
                if 2000 <= data.year <= 2099:
                    return data.strftime("%Y-%m-%d")
            except ValueError:
                pass

    return None


def detectar_sid(texto: str) -> Optional[str]:
    """
    Detecta o SID (identificador de lote) no texto do PDF.

    Busca por padrões como "SID 12345", "SID: 12345", "SID_12345" etc.

    Args:
        texto: Texto extraído do PDF.

    Returns:
        String com o número do SID (ex: "45873") ou None.
    """
    texto_upper = texto.upper()

    # Padrões comuns de SID em documentos logísticos
    padroes_sid = [
        r'SID[\s:_\-#]+(\d{4,10})',           # SID: 12345 | SID 12345 | SID_12345
        r'LOTE[\s:_\-#]+SID[\s:_\-#]*(\d+)',   # LOTE SID: 12345
        r'\bSID\b[\s:]*(\d+)',                  # SID genérico
        r'N[uú]MERO\s+(?:DO\s+)?SID[\s:]+(\d+)',  # NÚMERO DO SID: 12345
    ]

    for padrao in padroes_sid:
        match = re.search(padrao, texto_upper)
        if match:
            return match.group(1)

    return None


def ler_dados_pdf(caminho_pdf: str, transportadoras: list) -> DadosNota:
    """
    Lê um arquivo PDF e extrai todos os dados relevantes para organização.

    Args:
        caminho_pdf: Caminho completo para o arquivo PDF.
        transportadoras: Lista de transportadoras para identificar.

    Returns:
        Objeto DadosNota com os dados extraídos.
    """
    dados = DadosNota()

    try:
        texto = extrair_texto_pdf(caminho_pdf)
        dados.texto_completo = texto

        dados.transportadora = detectar_transportadora(texto, transportadoras)
        dados.data_emissao = detectar_data_emissao(texto)
        dados.sid = detectar_sid(texto)

        logger.debug(
            f"'{os.path.basename(caminho_pdf)}' → "
            f"Transp: {dados.transportadora} | "
            f"Data: {dados.data_emissao} | "
            f"SID: {dados.sid}"
        )

    except Exception as e:
        dados.erro = str(e)
        logger.error(f"Erro ao processar '{caminho_pdf}': {e}")

    return dados
