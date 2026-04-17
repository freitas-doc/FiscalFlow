# auth.py - Módulo de autenticação e histórico de operações
#
# Armazena usuários e histórico num banco SQLite compartilhado em rede.
#
# CONFIGURAÇÃO DO CAMINHO DO BANCO (ordem de prioridade):
#   1. Variável de ambiente NF_DB_PATH
#      Ex (Windows): set NF_DB_PATH=\\servidor\compartilhado\nf_organizer_dados.db
#
#   2. Arquivo "db_path.txt" na mesma pasta do executável/script
#      Conteúdo do arquivo (uma linha):
#        \\servidor\compartilhado\nf_organizer_dados.db
#
#   3. Constante CAMINHO_REDE_FIXO definida abaixo (edite antes de compilar)
#
#   4. Fallback: mesma pasta do executável (comportamento original — apenas local)
#
# Estrutura do banco:
#   tabela usuarios  : id, username, senha_hash, perfil, criado_em, criado_por
#   tabela historico : id, usuario, operacao, detalhes, data_hora

import os
import sys
import sqlite3
import hashlib
import secrets
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# ─── CONFIGURAÇÃO ─────────────────────────────────────────────────────────────

# Edite este caminho com o caminho real da pasta compartilhada na sua rede.
# Exemplo: r"\\SERVIDOR\Compartilhado\nf_organizer_dados.db"
# Deixe como string vazia ("") para usar apenas as opções 1, 2 e 4.
CAMINHO_REDE_FIXO = r""


# ─── Localização do banco ─────────────────────────────────────────────────────

def _caminho_banco() -> str:
    """
    Determina o caminho do banco de dados seguindo a ordem de prioridade:
      1. Variável de ambiente NF_DB_PATH
      2. Arquivo db_path.txt ao lado do executável/script
      3. Constante CAMINHO_REDE_FIXO definida acima
      4. Fallback local (mesma pasta do executável)
    """
    # ── 1. Variável de ambiente ──
    env = os.environ.get("NF_DB_PATH", "").strip()
    if env:
        pasta = os.path.dirname(env)
        if not pasta or os.path.isdir(pasta):
            logger.info(f"[DB] Usando caminho da variável de ambiente: {env}")
            return env

    # ── Base: pasta do executável ou do script ──
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))

    # ── 2. Arquivo db_path.txt ──
    arquivo_config = os.path.join(base, "db_path.txt")
    if os.path.isfile(arquivo_config):
        try:
            with open(arquivo_config, encoding="utf-8") as f:
                caminho = f.read().strip()
            if caminho:
                pasta = os.path.dirname(caminho)
                if not pasta or os.path.isdir(pasta):
                    logger.info(f"[DB] Usando caminho do db_path.txt: {caminho}")
                    return caminho
                else:
                    logger.warning(
                        f"[DB] Caminho no db_path.txt inacessível: {caminho}\n"
                        f"     Verifique se a pasta de rede está disponível."
                    )
        except Exception as e:
            logger.warning(f"[DB] Erro ao ler db_path.txt: {e}")

    # ── 3. Caminho fixo no código ──
    if CAMINHO_REDE_FIXO:
        pasta = os.path.dirname(CAMINHO_REDE_FIXO)
        if not pasta or os.path.isdir(pasta):
            logger.info(f"[DB] Usando caminho fixo: {CAMINHO_REDE_FIXO}")
            return CAMINHO_REDE_FIXO
        else:
            logger.warning(
                f"[DB] CAMINHO_REDE_FIXO inacessível: {CAMINHO_REDE_FIXO}\n"
                f"     Verifique a conexão com a rede."
            )

    # ── 4. Fallback local ──
    caminho_local = os.path.join(base, "nf_organizer_dados.db")
    logger.warning(
        f"[DB] Nenhum caminho de rede configurado ou acessível.\n"
        f"     Usando banco LOCAL: {caminho_local}\n"
        f"     Para compartilhar entre computadores, crie o arquivo db_path.txt\n"
        f"     na pasta do programa com o caminho da rede. Ex:\n"
        f"       \\\\SERVIDOR\\Compartilhado\\nf_organizer_dados.db"
    )
    return caminho_local


DB_PATH = _caminho_banco()


# ─── Inicialização do banco ───────────────────────────────────────────────────

def inicializar_banco():
    """
    Cria as tabelas se ainda não existirem.
    Se não houver nenhum usuário, cria o admin padrão (admin / admin123).
    """
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        cur = conn.cursor()

        cur.executescript("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT    NOT NULL UNIQUE COLLATE NOCASE,
                senha_hash  TEXT    NOT NULL,
                salt        TEXT    NOT NULL,
                perfil      TEXT    NOT NULL DEFAULT 'operador',
                criado_em   TEXT    NOT NULL,
                criado_por  TEXT    NOT NULL DEFAULT 'sistema'
            );

            CREATE TABLE IF NOT EXISTS historico (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario     TEXT    NOT NULL,
                operacao    TEXT    NOT NULL,
                detalhes    TEXT,
                data_hora   TEXT    NOT NULL
            );
        """)
        conn.commit()

        # Cria admin padrão se banco estiver vazio
        cur.execute("SELECT COUNT(*) FROM usuarios")
        if cur.fetchone()[0] == 0:
            _criar_usuario_db(cur, "admin", "admin123", "admin", "sistema")
            conn.commit()
            logger.info("Usuário admin padrão criado (admin / admin123).")

        conn.close()
        logger.info(f"[DB] Banco inicializado em: {DB_PATH}")

    except sqlite3.OperationalError as e:
        logger.error(
            f"[DB] ERRO ao conectar ao banco: {e}\n"
            f"     Caminho: {DB_PATH}\n"
            f"     Verifique se a pasta de rede está acessível e com permissão de escrita."
        )
        raise


# ─── Hash de senha ────────────────────────────────────────────────────────────

def _hash_senha(senha: str, salt: str) -> str:
    """Retorna SHA-256(salt + senha) em hexadecimal."""
    return hashlib.sha256((salt + senha).encode("utf-8")).hexdigest()


def _criar_usuario_db(cur, username: str, senha: str, perfil: str, criado_por: str):
    """Insere um usuário no banco (cursor já aberto)."""
    salt = secrets.token_hex(16)
    h = _hash_senha(senha, salt)
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute(
        "INSERT INTO usuarios (username, senha_hash, salt, perfil, criado_em, criado_por) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (username.strip(), h, salt, perfil, agora, criado_por)
    )


# ─── Conexão com timeout (evita travamento em rede) ──────────────────────────

def _conectar() -> sqlite3.Connection:
    """
    Abre uma conexão com o banco com timeout adequado para uso em rede.
    O timeout de 15s evita travamento quando outro PC está gravando.
    """
    return sqlite3.connect(DB_PATH, timeout=15)


# ─── API pública de usuários ──────────────────────────────────────────────────

def autenticar(username: str, senha: str) -> Optional[dict]:
    """
    Verifica credenciais.

    Returns:
        Dict com dados do usuário se autenticado, None caso contrário.
        Ex: {"id": 1, "username": "joao", "perfil": "operador"}
    """
    try:
        conn = _conectar()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username, senha_hash, salt, perfil FROM usuarios WHERE username = ?",
            (username.strip(),)
        )
        row = cur.fetchone()
        conn.close()

        if not row:
            return None

        id_, uname, senha_hash, salt, perfil = row
        if _hash_senha(senha, salt) == senha_hash:
            return {"id": id_, "username": uname, "perfil": perfil}
        return None

    except Exception as e:
        logger.error(f"Erro ao autenticar '{username}': {e}")
        return None


def criar_usuario(username: str, senha: str, perfil: str, criado_por: str) -> tuple:
    """
    Cria um novo usuário.

    Returns:
        (True, "") em caso de sucesso.
        (False, "mensagem de erro") em caso de falha.
    """
    if not username.strip():
        return False, "Nome de usuário não pode ser vazio."
    if len(senha) < 4:
        return False, "A senha deve ter pelo menos 4 caracteres."
    if perfil not in ("admin", "operador"):
        return False, "Perfil inválido."

    try:
        conn = _conectar()
        cur = conn.cursor()
        _criar_usuario_db(cur, username, senha, perfil, criado_por)
        conn.commit()
        conn.close()
        logger.info(f"Usuário '{username}' criado por '{criado_por}'.")
        return True, ""
    except sqlite3.IntegrityError:
        return False, f"Usuário '{username}' já existe."
    except Exception as e:
        return False, str(e)


def alterar_senha(username: str, senha_atual: str, senha_nova: str) -> tuple:
    """
    Altera a senha de um usuário após verificar a senha atual.

    Returns:
        (True, "") ou (False, "mensagem").
    """
    if len(senha_nova) < 4:
        return False, "A nova senha deve ter pelo menos 4 caracteres."

    usuario = autenticar(username, senha_atual)
    if not usuario:
        return False, "Senha atual incorreta."

    try:
        salt = secrets.token_hex(16)
        h = _hash_senha(senha_nova, salt)
        conn = _conectar()
        conn.execute(
            "UPDATE usuarios SET senha_hash=?, salt=? WHERE username=?",
            (h, salt, username)
        )
        conn.commit()
        conn.close()
        return True, ""
    except Exception as e:
        return False, str(e)


def redefinir_senha_admin(username_alvo: str, senha_nova: str, admin_username: str) -> tuple:
    """
    Admin redefine a senha de qualquer usuário sem precisar da senha atual.
    """
    if len(senha_nova) < 4:
        return False, "A senha deve ter pelo menos 4 caracteres."
    try:
        salt = secrets.token_hex(16)
        h = _hash_senha(senha_nova, salt)
        conn = _conectar()
        cur = conn.cursor()
        cur.execute(
            "UPDATE usuarios SET senha_hash=?, salt=? WHERE username=?",
            (h, salt, username_alvo)
        )
        if cur.rowcount == 0:
            conn.close()
            return False, f"Usuário '{username_alvo}' não encontrado."
        conn.commit()
        conn.close()
        logger.info(f"Senha de '{username_alvo}' redefinida por '{admin_username}'.")
        return True, ""
    except Exception as e:
        return False, str(e)


def excluir_usuario(username_alvo: str, admin_username: str) -> tuple:
    """Admin exclui um usuário."""
    if username_alvo.lower() == "admin":
        return False, "O usuário 'admin' não pode ser excluído."
    try:
        conn = _conectar()
        cur = conn.cursor()
        cur.execute("DELETE FROM usuarios WHERE username=?", (username_alvo,))
        if cur.rowcount == 0:
            conn.close()
            return False, f"Usuário '{username_alvo}' não encontrado."
        conn.commit()
        conn.close()
        logger.info(f"Usuário '{username_alvo}' excluído por '{admin_username}'.")
        return True, ""
    except Exception as e:
        return False, str(e)


def listar_usuarios() -> list:
    """
    Retorna lista de todos os usuários (sem senhas).

    Returns:
        Lista de dicts: [{"username", "perfil", "criado_em", "criado_por"}, ...]
    """
    try:
        conn = _conectar()
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT username, perfil, criado_em, criado_por FROM usuarios ORDER BY username"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Erro ao listar usuários: {e}")
        return []


# ─── API pública de histórico ─────────────────────────────────────────────────

def registrar_operacao(usuario: str, operacao: str, detalhes: str = ""):
    """
    Grava uma entrada no histórico de operações.

    Args:
        usuario:   Nome do usuário logado.
        operacao:  Tipo da operação. Ex: "SEPARACAO_LOTE", "ORGANIZACAO".
        detalhes:  Texto livre com detalhes da operação.
    """
    try:
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = _conectar()
        conn.execute(
            "INSERT INTO historico (usuario, operacao, detalhes, data_hora) VALUES (?,?,?,?)",
            (usuario, operacao, detalhes, agora)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Erro ao registrar operação: {e}")


def consultar_historico(usuario: str = None, limite: int = 200) -> list:
    """
    Retorna entradas do histórico, opcionalmente filtradas por usuário.

    Returns:
        Lista de dicts: [{"usuario", "operacao", "detalhes", "data_hora"}, ...]
    """
    try:
        conn = _conectar()
        conn.row_factory = sqlite3.Row

        if usuario:
            rows = conn.execute(
                "SELECT usuario, operacao, detalhes, data_hora FROM historico "
                "WHERE usuario=? ORDER BY data_hora DESC LIMIT ?",
                (usuario, limite)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT usuario, operacao, detalhes, data_hora FROM historico "
                "ORDER BY data_hora DESC LIMIT ?",
                (limite,)
            ).fetchall()

        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Erro ao consultar histórico: {e}")
        return []
