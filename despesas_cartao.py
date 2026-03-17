import pdfplumber
import pandas as pd
import os
import re
import shutil
import sqlite3
from database import get_db_connection

# Diretórios
FATURAS_DIR = 'faturas/'
PROCESSADAS_DIR = 'faturas_processadas/'

def extrair_dados_fatura(caminho_pdf):
    # (A função extrair_dados_fatura permanece a mesma)
    despesas = []
    ultima_data = ""
    ano = ""
    regex_transacao = r"(\d{2}\/\d{2})\s+(.+?)\s+(-?(?:\d{1,3}(?:\.\d{3})*|\d+),\d{2})"
    PALAVRAS_CHAVE_IGNORAR = [
        'PAGAMENTO', 'SALDO ANTERIOR', 'TOTAL', 'CRÉDITO', 'FATURA',
        'ENCARGOS', 'VENCIMENTO', 'LIMITE', 'COMPRA DATA DESCRIÇÃO'
    ]

    with pdfplumber.open(caminho_pdf) as pdf:
        texto_completo = "".join(p.extract_text() for p in pdf.pages if p.extract_text() if p.extract_text())

        # Tenta extrair o ano da data de vencimento, que é mais confiável
        match_ano = re.search(r'Vencimento[\n\s]*\d{2}\/\d{2}\/(\d{4})', texto_completo)
        if match_ano:
            ano = match_ano.group(1)
        else:
            # Se não encontrar no vencimento, procura qualquer data no formato DD/MM/YYYY
            match_ano_fallback = re.search(r'\d{2}\/\d{2}\/(\d{4})', texto_completo)
            if match_ano_fallback:
                ano = match_ano_fallback.group(1)

        for pagina in pdf.pages:
            col_esquerda = pagina.crop((0, 0, pagina.width * 0.5, pagina.height))
            col_direita = pagina.crop((pagina.width * 0.5, 0, pagina.width, pagina.height))

            for coluna in [col_esquerda, col_direita]:
                texto_coluna = coluna.extract_text(x_tolerance=2)
                if not texto_coluna:
                    continue

                for linha in texto_coluna.split('\n'):
                    if any(keyword in linha.upper() for keyword in PALAVRAS_CHAVE_IGNORAR):
                        continue
                    
                    transacoes_encontradas = re.findall(regex_transacao, linha)
                    for data_curta, descricao, valor in transacoes_encontradas:
                        data_completa = f"{data_curta}/{ano}" if ano else data_curta
                        ultima_data = data_completa
                        descricao_limpa = re.sub(r'\s+\d{1,2}\/\d{1,2}$', '', descricao).strip()
                        descricao_limpa = re.sub(r'^\d+\s+', '', descricao_limpa).strip()
                        despesas.append({
                            'Data': data_completa,
                            'Descrição': descricao_limpa,
                            'Valor (R$)': valor
                        })

    texto_completo = "".join(p.extract_text() for p in pdf.pages if p.extract_text())
    match_iof = re.search(r"(IOFDESPESANOEXTERIOR|IOF\s+DESPESA[\w\s]+EXTERIOR)\s+([\d,]+)", texto_completo, re.IGNORECASE)
    if match_iof:
        valor_iof = match_iof.group(2)
        if not any(d['Descrição'] == 'IOF DESPESA NO EXTERIOR' for d in despesas):
            despesas.append({
                'Data': ultima_data, 
                'Descrição': 'IOF DESPESA NO EXTERIOR',
                'Valor (R$)': valor_iof
            })

    return despesas

def salvar_despesas_no_banco(despesas, nome_arquivo_fonte):
    """Salva uma lista de despesas no banco de dados SQLite."""
    if not despesas:
        return 0

    conn = get_db_connection()
    cursor = conn.cursor()
    registros_inseridos = 0

    for despesa in despesas:
        try:
            # Limpeza e conversão de dados
            # A extração de 'ano' agora é mais confiável, então usamos diretamente.
            # A data já vem com o ano correto de extrair_dados_fatura
            data_formatada = pd.to_datetime(despesa['Data'], format='%d/%m/%Y').strftime('%Y-%m-%d')
            valor_float = float(despesa['Valor (R$)'].replace('.', '').replace(',', '.'))

            cursor.execute(
                "INSERT INTO despesas_cartao (data, descricao, valor, fonte_arquivo) VALUES (?, ?, ?, ?)",
                (data_formatada, despesa['Descrição'], valor_float, nome_arquivo_fonte)
            )
            registros_inseridos += 1
        except sqlite3.IntegrityError:
            # Ignora o registro se ele já existir (duplicado)
            continue
        except Exception as e:
            print(f"Erro ao inserir registro: {despesa} - {e}")

    conn.commit()
    conn.close()
    return registros_inseridos

def main():
    """Função principal que orquestra a extração e salvamento dos dados."""
    for diretorio in [FATURAS_DIR, PROCESSADAS_DIR]:
        if not os.path.exists(diretorio):
            os.makedirs(diretorio)
            print(f"Diretório '{diretorio}' criado.")

    try:
        arquivos_pdf = [f for f in os.listdir(FATURAS_DIR) if f.lower().endswith('.pdf')]
    except FileNotFoundError:
        os.makedirs(FATURAS_DIR)
        print(f"Erro: Diretório '{FATURAS_DIR}' não encontrado. Foi criado para você.")
        return

    if not arquivos_pdf:
        print(f"Nenhum arquivo PDF encontrado em '{FATURAS_DIR}'.")
        return

    print(f"Encontrados {len(arquivos_pdf)} arquivos PDF para processar.")
    total_registros_inseridos = 0

    for nome_arquivo in arquivos_pdf:
        caminho_origem = os.path.join(FATURAS_DIR, nome_arquivo)
        caminho_destino = os.path.join(PROCESSADAS_DIR, nome_arquivo)
        
        print(f"\nProcessando arquivo: {nome_arquivo}...")
        
        try:
            despesas_extraidas = extrair_dados_fatura(caminho_origem)
            registros_inseridos = salvar_despesas_no_banco(despesas_extraidas, nome_arquivo)
            total_registros_inseridos += registros_inseridos
            
            print(f"{registros_inseridos} novos registros inseridos no banco de dados.")

            shutil.move(caminho_origem, caminho_destino)
            print(f"Arquivo '{nome_arquivo}' processado e movido para '{PROCESSADAS_DIR}'.")
            
        except Exception as e:
            print(f"Erro ao processar o arquivo {nome_arquivo}: {e}")

    print(f"\nProcessamento concluído. Total de {total_registros_inseridos} novos registros inseridos.")

if __name__ == "__main__":
    main()
