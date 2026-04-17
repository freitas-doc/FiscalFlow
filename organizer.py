# organizer.py - Módulo de organização e movimentação de arquivos

import os
import shutil
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from config import (
    TRANSPORTADORAS,
    PASTA_ERRO,
    SID_PREFIX,
    MAX_THREADS,
    EXTENSAO_PDF,
)
from pdf_reader import ler_dados_pdf, DadosNota

logger = logging.getLogger(__name__)


# ─── Resultado de Processamento ───────────────────────────────────────────────

class ResultadoArquivo:
    """Resultado do processamento de um único arquivo PDF."""

    def __init__(self, arquivo: str):
        self.arquivo = arquivo               # Nome do arquivo
        self.destino: Optional[str] = None   # Pasta de destino
        self.sucesso: bool = False
        self.mensagem: str = ""
        self.dados: Optional[DadosNota] = None


# ─── Determinação de Destino ──────────────────────────────────────────────────

def _pasta_por_transportadora(dados: DadosNota) -> Optional[str]:
    """Retorna o nome da pasta baseado na transportadora."""
    return dados.transportadora  # None se não encontrada


def _pasta_por_data(dados: DadosNota) -> Optional[str]:
    """Retorna o nome da pasta baseado na data de emissão."""
    return dados.data_emissao  # None se não encontrada


def _pasta_por_sid(dados: DadosNota) -> Optional[str]:
    """Retorna o nome da pasta baseado no SID."""
    if dados.sid:
        return f"{SID_PREFIX}{dados.sid}"
    return None


def _pasta_transportadora_sid(dados: DadosNota) -> Optional[str]:
    """
    Retorna caminho relativo 'TRANSPORTADORA/SID_XXXX'.
    Usa os.path.join para compatibilidade cross-platform.
    """
    transp = _pasta_por_transportadora(dados)
    sid = _pasta_por_sid(dados)
    if transp and sid:
        return os.path.join(transp, sid)
    if transp:
        return transp
    if sid:
        return sid
    return None


def _pasta_transportadora_data(dados: DadosNota) -> Optional[str]:
    """Retorna caminho relativo 'TRANSPORTADORA/AAAA-MM-DD'."""
    transp = _pasta_por_transportadora(dados)
    data = _pasta_por_data(dados)
    if transp and data:
        return os.path.join(transp, data)
    if transp:
        return transp
    if data:
        return data
    return None


# Mapa de opções de organização → funções de determinação de pasta
ESTRATEGIAS = {
    "Organizar por Transportadora": _pasta_por_transportadora,
    "Organizar por Data":           _pasta_por_data,
    "Organizar por SID":            _pasta_por_sid,
    "Transportadora → SID":         _pasta_transportadora_sid,
    "Transportadora → Data":        _pasta_transportadora_data,
}


# ─── Processamento Individual ─────────────────────────────────────────────────

def processar_arquivo(
    caminho_origem: str,
    pasta_destino_raiz: str,
    estrategia: str,
    manter_copia: bool = True,
) -> ResultadoArquivo:
    """
    Processa um único arquivo PDF: lê os dados, determina o destino e copia/move.

    Args:
        caminho_origem: Caminho completo do arquivo PDF de origem.
        pasta_destino_raiz: Pasta raiz onde as subpastas serão criadas.
        estrategia: Nome da estratégia de organização (chave de ESTRATEGIAS).
        manter_copia: Se True, copia o arquivo (mantém original). Se False, move.

    Returns:
        ResultadoArquivo com o resultado da operação.
    """
    nome_arquivo = os.path.basename(caminho_origem)
    resultado = ResultadoArquivo(nome_arquivo)

    try:
        # 1. Lê os dados do PDF
        dados = ler_dados_pdf(caminho_origem, TRANSPORTADORAS)
        resultado.dados = dados

        # 2. Determina a subpasta de destino
        func_estrategia = ESTRATEGIAS.get(estrategia)
        if not func_estrategia:
            raise ValueError(f"Estratégia desconhecida: '{estrategia}'")

        # Se houve erro na leitura, vai para pasta de erro
        if dados.erro:
            subpasta = PASTA_ERRO
        else:
            subpasta = func_estrategia(dados)
            if not subpasta:
                # Dados insuficientes para a estratégia escolhida
                subpasta = PASTA_ERRO

        # 3. Cria a pasta de destino se não existir
        pasta_final = os.path.join(pasta_destino_raiz, subpasta)
        os.makedirs(pasta_final, exist_ok=True)

        # 4. Copia ou move o arquivo
        destino_completo = os.path.join(pasta_final, nome_arquivo)

        # Evita sobrescrever arquivos com mesmo nome
        destino_completo = _resolver_conflito(destino_completo)

        if manter_copia:
            shutil.copy2(caminho_origem, destino_completo)
            acao = "Copiado"
        else:
            shutil.move(caminho_origem, destino_completo)
            acao = "Movido"

        resultado.destino = pasta_final
        resultado.sucesso = True
        resultado.mensagem = f"{acao} → {subpasta}"

    except Exception as e:
        # Qualquer falha: tenta salvar na pasta de erro
        try:
            pasta_erro = os.path.join(pasta_destino_raiz, PASTA_ERRO)
            os.makedirs(pasta_erro, exist_ok=True)
            destino_erro = _resolver_conflito(os.path.join(pasta_erro, nome_arquivo))
            shutil.copy2(caminho_origem, destino_erro)
            resultado.destino = pasta_erro
        except Exception:
            pass

        resultado.sucesso = False
        resultado.mensagem = f"ERRO: {e}"
        logger.error(f"Falha ao processar '{nome_arquivo}': {e}")

    return resultado


def _resolver_conflito(caminho: str) -> str:
    """
    Se o arquivo já existir no destino, adiciona sufixo numérico ao nome.
    Ex: nota.pdf → nota_1.pdf → nota_2.pdf ...
    """
    if not os.path.exists(caminho):
        return caminho

    base, ext = os.path.splitext(caminho)
    contador = 1
    while os.path.exists(f"{base}_{contador}{ext}"):
        contador += 1
    return f"{base}_{contador}{ext}"


# ─── Processamento em Lote ────────────────────────────────────────────────────

def listar_pdfs(pasta_origem: str) -> list:
    """
    Lista todos os arquivos PDF na pasta de origem (recursivo).

    Args:
        pasta_origem: Caminho da pasta a escanear.

    Returns:
        Lista de caminhos completos dos PDFs encontrados.
    """
    pdfs = []
    for raiz, _, arquivos in os.walk(pasta_origem):
        for arquivo in arquivos:
            if arquivo.lower().endswith(EXTENSAO_PDF):
                pdfs.append(os.path.join(raiz, arquivo))
    return pdfs


def organizar_lote(
    pasta_origem: str,
    pasta_destino: str,
    estrategia: str,
    manter_copia: bool = True,
    callback_progresso: Optional[Callable[[ResultadoArquivo, int, int], None]] = None,
    callback_log: Optional[Callable[[str], None]] = None,
    parar_evento=None,
) -> dict:
    """
    Organiza todos os PDFs de uma pasta de origem em paralelo.

    Args:
        pasta_origem: Pasta com os PDFs embaralhados.
        pasta_destino: Pasta raiz onde a estrutura organizada será criada.
        estrategia: Nome da estratégia de organização.
        manter_copia: Se True, copia os arquivos (não apaga originais).
        callback_progresso: Função chamada após cada arquivo processado.
                            Assinatura: (resultado, processados, total)
        callback_log: Função para enviar mensagens de log para a UI.
        parar_evento: threading.Event — se definido e disparado, interrompe o lote.

    Returns:
        Dicionário com estatísticas: total, sucessos, erros.
    """
    pdfs = listar_pdfs(pasta_origem)
    total = len(pdfs)

    if total == 0:
        if callback_log:
            callback_log("Nenhum PDF encontrado na pasta de origem.")
        return {"total": 0, "sucessos": 0, "erros": 0}

    if callback_log:
        callback_log(f"📂 {total} arquivo(s) PDF encontrado(s). Iniciando organização...")

    estatisticas = {"total": total, "sucessos": 0, "erros": 0}
    processados = 0

    # Usa ThreadPoolExecutor para processar em paralelo
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futuros = {
            executor.submit(
                processar_arquivo,
                pdf,
                pasta_destino,
                estrategia,
                manter_copia,
            ): pdf
            for pdf in pdfs
        }

        for futuro in as_completed(futuros):
            # Verifica se o usuário pediu para parar
            if parar_evento and parar_evento.is_set():
                executor.shutdown(wait=False, cancel_futures=True)
                if callback_log:
                    callback_log("⚠️ Processamento interrompido pelo usuário.")
                break

            resultado = futuro.result()
            processados += 1

            if resultado.sucesso:
                estatisticas["sucessos"] += 1
                msg = f"✅ {resultado.arquivo} → {resultado.mensagem}"
            else:
                estatisticas["erros"] += 1
                msg = f"❌ {resultado.arquivo} — {resultado.mensagem}"

            if callback_log:
                callback_log(msg)

            if callback_progresso:
                callback_progresso(resultado, processados, total)

    if callback_log:
        callback_log(
            f"\n🏁 Concluído! "
            f"✅ {estatisticas['sucessos']} sucesso(s) | "
            f"❌ {estatisticas['erros']} erro(s)"
        )

    return estatisticas
