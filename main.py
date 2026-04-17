# main.py - Ponto de entrada do Organizador de Notas Fiscais

import logging
import sys
import psycopg2
from dotenv import load_dotenv
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


def verificar_dependencias():
    dependencias = {
        "pdfplumber": "pip install pdfplumber",
        "PyPDF2":     "pip install PyPDF2",
    }
    faltando = []
    for lib, cmd in dependencias.items():
        try:
            __import__(lib)
        except ImportError:
            faltando.append((lib, cmd))

    if faltando and len(faltando) == len(dependencias):
        print("\n⚠️  ATENÇÃO: Nenhuma biblioteca de leitura de PDF encontrada!")
        for lib, cmd in faltando:
            print(f"   {cmd}")
        print()
    elif faltando:
        for lib, cmd in faltando:
            logger.warning(f"Biblioteca '{lib}' não encontrada. Instale com: {cmd}")


def main():
    verificar_dependencias()

    try:
        # ── 1. Inicializa banco de dados (cria se não existir) ────────────────
        from auth import inicializar_banco
        inicializar_banco()

        # ── 2. Exibe tela de login ────────────────────────────────────────────
        from ui_login import LoginDialog
        login = LoginDialog()
        login.mainloop()

        # Se o usuário fechou sem logar, encerra
        if not login.usuario_logado:
            logger.info("Login cancelado — encerrando.")
            sys.exit(0)

        usuario_logado = login.usuario_logado
        logger.info(
            f"Login: {usuario_logado['username']} "
            f"(perfil: {usuario_logado['perfil']})"
        )

        from auth import registrar_operacao
        registrar_operacao(usuario_logado['username'], "TESTE_CONEXAO", "Testando gravação no banco nuvem")

        # ── 3. Abre a aplicação principal passando o usuário logado ───────────
        from ui import AplicacaoOrganizador
        app = AplicacaoOrganizador(usuario_logado=usuario_logado)
        logger.info("Aplicação iniciada.")
        app.mainloop()
        logger.info("Aplicação encerrada.")

    except ImportError as e:
        print(f"\n❌ Erro ao importar módulos: {e}")
        print("   Verifique se todos os arquivos do projeto estão na mesma pasta.")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Erro inesperado: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

# ─── Configuração do Supabase / Postgres (executado após o app fechar ou importação) ───

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

# Pega a URL do banco a partir da variável de ambiente definida no .env (ex: DATABASE_URL)
DATABASE_URL = os.getenv("DATABASE_URL")

# Tenta conectar ao banco apenas se a URL foi configurada
if DATABASE_URL:
    try:
        connection = psycopg2.connect(DATABASE_URL)
        logger.info("Conectado ao Supabase/PostgreSQL com sucesso.")
    except Exception as e:
        logger.error(f"Erro ao conectar ao Supabase/PostgreSQL: {e}")
else:
    logger.warning("DATABASE_URL não encontrada no arquivo .env")