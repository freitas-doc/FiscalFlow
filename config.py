# config.py - Configurações globais do sistema de organização de notas fiscais

# Lista de transportadoras reconhecidas pelo sistema
TRANSPORTADORAS = [
    "RETIRA",
    "PATRUS",
    "URBANO",
    "TRANSLOVATO",
    "TERMACO",
    "FAVORITA",
]

# Pasta padrão para arquivos com erro de leitura
PASTA_ERRO = "ERRO_DE_LEITURA"

# Opções de organização disponíveis na interface
OPCOES_ORGANIZACAO = [
    "Organizar por Transportadora",
    "Organizar por Data",
    "Organizar por SID",
    "Transportadora → SID",
    "Transportadora → Data",
]

# Prefixo usado nas pastas de SID
SID_PREFIX = "SID_"

# Formato de data para criação de pastas (AAAA-MM-DD)
FORMATO_DATA = "%Y-%m-%d"

# Número máximo de threads para processamento paralelo
MAX_THREADS = 8

# Extensão dos arquivos aceitos
EXTENSAO_PDF = ".pdf"
