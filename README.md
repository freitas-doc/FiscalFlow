# FiscalFlow
📦 Organizador Automático de Notas Fiscais (NF Organizer) Olá! Bem-vindo ao repositório do NF Organizer. Desenvolvi esta aplicação desktop para resolver um gargalo operacional real na esteira logística: o processamento, separação e impressão em lote de Notas Fiscais (NFs) e Capas de Lote.

🎯 O Problema:
 - No dia a dia de uma operação logística de grande volume, a separação de documentos consome muitas horas manuais.
    O processo padrão envolvia:
 - Receber um único arquivo PDF gigantesco contendo múltiplas "Capas de Lote" (documentos que listam quais NFs pertencem a qual carregamento/SID).
 - Receber dezenas ou centenas de arquivos PDFs de Notas Fiscais avulsas e embaralhadas.

O trabalho braçal: 
 - Um operador precisava ler capa por capa, descobrir o número do SID (Shipment ID), procurar os arquivos das NFs correspondentes uma a uma, e organizá-las para enviar para a expedição.

O problema físico:

 - Várias capas de lotes e Muito desperdício de papel pois eram perdidas algumas capas de lote e notas fiscais, assim contrariando políticas ambientais da empresa.
 - Com o trabalho humano, era possível cometer erros como a entrega de notas erradas em uma capa de lote devido a pressa ou algum descuido.


🚀 A Solução Criei este aplicativo para automatizar 100% dessa triagem. 
O que o App faz:

 - Leitura Inteligente

O sistema "lê" o PDF gigante de capas, divide em páginas individuais e usa expressões regulares (Regex) para extrair dados cruciais (Transportadora, SID e a lista de NFs daquele lote).

Cruzamento de Dados:
 - Ele varre a pasta de NFs avulsas, encontra exatamente os arquivos listados na capa e os agrupa.

Organização de Diretórios:

 - Cria automaticamente uma estrutura de pastas organizada por Transportadora -> SID.
 - Impressão Inteligente (Bandeja Dupla):

O aplicativo se comunica com a API do Windows para mandar a Capa do Lote para a Gaveta A da impressora (Sulfite) e as NFs correspondentes para a Gaveta B (Papel Especial), adicionando páginas em branco no final de arquivos ímpares para evitar impressões no verso errado.

Anulação da possibilidade de enviar notas erradas para um caminhão.


💻 Linguagem e Tecnologias Utilizadas Escolhi Python para este projeto por ser a linguagem definitiva para automação de tarefas e manipulação de arquivos, além de possuir um ecossistema excelente para lidar com PDFs.

Aqui estão as principais ferramentas que utilizei no código e o porquê:

 - Manipulação de PDF (pdfplumber e PyPDF2):

Utilizei essas bibliotecas no meu módulo pdf_reader.py para extrair o texto bruto dos documentos. Como layouts de notas fiscais podem variar, construí lógicas baseadas em Regex (re) para caçar padrões específicos (ex: blocos de 9 dígitos para NFs, ou o padrão SID_XXXX). O PyPDF2 também foi essencial no módulo printer.py para mesclar os PDFs e injetar páginas em branco dinamicamente antes da impressão.


Interface Gráfica (tkinter):

 - A aplicação foi feita para rodar nos computadores da operação (Windows). Escolhi o tkinter por ser nativo do Python, muito leve e não exigir instalações pesadas. O usuário interage com uma interface amigável, seleciona as pastas de origem/destino e acompanha o progresso em tempo real.


Processamento Paralelo (concurrent.futures):

 - Processar e mover 500 PDFs sequencialmente congelaria a interface do usuário. Para resolver isso, implementei o ThreadPoolExecutor no módulo organizer.py. Isso permite que o aplicativo processe múltiplos arquivos simultaneamente em diferentes threads, tornando a organização drasticamente mais rápida sem travar o aplicativo.


Comunicação de Hardware (pywin32 e SumatraPDF):

 - Esse foi o maior desafio técnico do projeto. Leitor de PDF padrão do Windows costuma ignorar comandos para trocar de bandeja na impressora. Utilizei o pywin32 para listar e interagir com o DevMode das impressoras locais, e integrei o aplicativo via linha de comando com o SumatraPDF, garantindo que os comandos de bin=1 (Gaveta 1) ou bin=2 (Gaveta 2) sejam respeitados pelo hardware.


CONSIDERAÇÕES FINAIS

Para um primeiro projeto que realmenteresolveria um problema, foi gratificante perceber como estava funcinando e deixando resultados visíveis desde o primeiro uso.
Espero que esse projeto inspire vocês, eu agradeço a atenção de todos !
