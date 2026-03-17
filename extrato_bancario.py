import pdfplumber
import os
import re
import shutil
import sqlite3
from collections import defaultdict
from datetime import datetime
from database import get_db_connection

# Diretórios
EXTRATOS_DIR = 'extratos/'
PROCESSADOS_DIR = 'extratos_processados/'

def extrair_dados_extrato(caminho_pdf):
    transacoes = []
    ano_extrato = None
    ultima_data = ""
    nome_arquivo = os.path.basename(caminho_pdf)

    with pdfplumber.open(caminho_pdf) as pdf:
        all_words = []
        for page in pdf.pages:
            extracted_words = page.extract_words(x_tolerance=2, y_tolerance=2)
            for word in extracted_words:
                word['page_number'] = page.page_number
                all_words.append(word)

        lines_by_page_top = defaultdict(list)
        for word in all_words:
            key = (word['page_number'], round(word['top'], 2))
            lines_by_page_top[key].append(word)

        for page in pdf.pages:
            texto_pagina = page.extract_text()
            if texto_pagina:
                match_ano = re.search(r'\w+\/(\d{4})', texto_pagina)
                if match_ano:
                    ano_extrato = match_ano.group(1)
                    break
        if not ano_extrato: return []

        all_lines = sorted(lines_by_page_top.items(), key=lambda item: (item[0][0], item[0][1]))
        raw_transaction_lines = []
        in_transaction_block = False

        for (pn, top), line_words in all_lines:
            line_words.sort(key=lambda w: w['x0'])
            line_text = ' '.join(w['text'] for w in line_words).strip()

            if not in_transaction_block:
                if all(keyword in line_text for keyword in ['Data', 'Descrição', 'NºDocumento', 'Movimento(R$)']):
                    in_transaction_block = True
                continue

            if 'SALDO' in line_text.upper() and 'EM' in line_text.upper():
                if not raw_transaction_lines:
                    continue
                else:
                    break
            
            raw_transaction_lines.append(((pn, top), line_words))

        for (pn, top), line_words in raw_transaction_lines:
            line_text = ' '.join(w['text'] for w in line_words).strip()
            if not line_text: continue

            date_match = re.match(r'^(\d{2}/\d{2})', line_text)
            if date_match:
                ultima_data = f"{date_match.group(1)}/{ano_extrato}"
                line_text = line_text[len(date_match.group(0)):].strip()

            valores_encontrados = re.findall(r'(-?\d{1,3}(?:\.\d{3})*?,\d{2}-?)', line_text)

            if valores_encontrados:
                valor_str = valores_encontrados[0]
                descricao = line_text
                for v in valores_encontrados:
                    descricao = descricao.replace(v, '')
                
                if 'TEDRECEBIDAGRPQALTDA' in descricao:
                    descricao = 'TED RECEBIDA GRPQA LTDA'
                else:
                    noise_marker = 'Extrato_PF_A4_Inteligente'
                    if noise_marker in descricao:
                        descricao = descricao.split(noise_marker)[0]

                valor = float(valor_str.replace('.', '').replace(',', '.').replace('-', ''))
                if '-' in valor_str: valor *= -1
                
                if descricao.strip() and not descricao.strip().isdigit():
                    transacoes.append({'data': ultima_data, 'descricao': descricao.strip(), 'valor': valor, 'arquivo_origem': nome_arquivo})
            elif transacoes and transacoes[-1]['descricao'] != 'TED RECEBIDA GRPQA LTDA':
                transacoes[-1]['descricao'] += ' ' + line_text
    
    return transacoes

def salvar_movimentacoes_no_banco(transacoes):
    """Salva as transações do extrato no banco de dados SQLite."""
    if not transacoes:
        return 0

    conn = get_db_connection()
    cursor = conn.cursor()
    registros_inseridos = 0

    for transacao in transacoes:
        try:
            data_obj = datetime.strptime(transacao['data'], '%d/%m/%Y')
            data_formatada = data_obj.strftime('%Y-%m-%d')

            cursor.execute(
                "INSERT INTO movimentacoes_bancarias (data, descricao, valor, fonte_arquivo) VALUES (?, ?, ?, ?)",
                (data_formatada, transacao['descricao'], transacao['valor'], transacao['arquivo_origem'])
            )
            registros_inseridos += 1
        except sqlite3.IntegrityError:
            # Ignora registros duplicados
            continue
        except Exception as e:
            print(f"Erro ao inserir registro: {transacao} - {e}")

    conn.commit()
    conn.close()
    return registros_inseridos

def main():
    """Orquestra a extração de dados e salvamento no banco de dados."""
    for diretorio in [EXTRATOS_DIR, PROCESSADOS_DIR]:
        if not os.path.exists(diretorio):
            os.makedirs(diretorio)

    try:
        arquivos_pdf = [f for f in os.listdir(EXTRATOS_DIR) if f.lower().endswith('.pdf')]
    except FileNotFoundError:
        print(f"Erro: O diretório '{EXTRATOS_DIR}' não foi encontrado.")
        return

    if not arquivos_pdf:
        print(f"Nenhum PDF encontrado em '{EXTRATOS_DIR}'.")
        return

    print(f"Encontrados {len(arquivos_pdf)} extratos para processar.")
    total_registros_inseridos = 0

    for arquivo_pdf in arquivos_pdf:
        print(f"\nProcessando arquivo: {arquivo_pdf}...")
        caminho_origem = os.path.join(EXTRATOS_DIR, arquivo_pdf)
        dados_extrato = extrair_dados_extrato(caminho_origem)
        
        if dados_extrato:
            registros_inseridos = salvar_movimentacoes_no_banco(dados_extrato)
            total_registros_inseridos += registros_inseridos
            print(f"{registros_inseridos} novos registros inseridos no banco de dados.")

            caminho_destino = os.path.join(PROCESSADOS_DIR, arquivo_pdf)
            shutil.move(caminho_origem, caminho_destino)
            print(f"Arquivo '{arquivo_pdf}' processado e movido para '{PROCESSADOS_DIR}'.")

    if total_registros_inseridos > 0:
        print(f"\nProcessamento concluído. Total de {total_registros_inseridos} novos registros inseridos.")
    else:
        print("\nNenhum dado novo foi extraído ou inserido.")

if __name__ == "__main__":
    main()
