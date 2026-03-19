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

    with pdfplumber.open(caminho_pdf, password="08700599719") as pdf:
        texto_completo = "".join(p.extract_text() for p in pdf.pages if p.extract_text())

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
                    if transacoes_encontradas:
                        for data_curta, descricao, valor in transacoes_encontradas:
                            data_completa = f"{data_curta}/{ano}" if ano else data_curta
                            ultima_data = data_completa
                            # Remove apenas números iniciais se houver (alguns PDFs trazem um contador)
                            descricao_limpa = re.sub(r'^\d+\s+', '', descricao).strip()
                            despesas.append({
                                'Data': data_completa,
                                'Descrição': descricao_limpa,
                                'Valor (R$)': valor
                            })
                    else:
                        # Caso especial: IOF sem data na linha (usa a data da transação anterior)
                        # Regex mais flexível para capturar variações com ou sem espaços
                        # Usando um padrão mais estrito para o valor para evitar capturar dígitos adjacentes (ex: 2,944 ao invés de 2,94)
                        regex_valor = r"(-?(?:\d{1,3}(?:\.\d{3})*|\d+),\d{2})"
                        regex_iof = rf"(IOF\s*DESPESA\s*NO\s*EXTERIOR|IOFDESPESANOEXTERIOR)\s+{regex_valor}"
                        match_iof = re.search(regex_iof, linha, re.IGNORECASE)
                        if match_iof and ultima_data:
                            # Se este valor já foi capturado nesta linha (para evitar duplicatas se a linha tiver múltiplos matches?)
                            # Normalmente é um por linha.
                            despesas.append({
                                'Data': ultima_data,
                                'Descrição': 'IOF DESPESA NO EXTERIOR',
                                'Valor (R$)': match_iof.group(2)
                            })

    # Backup: Busca global no texto completo
    texto_total = "".join(p.extract_text() for p in pdf.pages if p.extract_text())
    regex_valor = r"(-?(?:\d{1,3}(?:\.\d{3})*|\d+),\d{2})"
    matches_globais = re.findall(rf"(IOF\s*DESPESA\s*NO\s*EXTERIOR|IOFDESPESANOEXTERIOR)\s+{regex_valor}", texto_total, re.IGNORECASE)
    
    for _, valor_iof in matches_globais:
        # Se este valor exato para IOF ainda não está na lista de despesas, adicionamos como segurança
        if not any(d['Descrição'] == 'IOF DESPESA NO EXTERIOR' and d['Valor (R$)'] == valor_iof for d in despesas):
            despesas.append({
                'Data': ultima_data, 
                'Descrição': 'IOF DESPESA NO EXTERIOR',
                'Valor (R$)': valor_iof
            })

    return despesas

def extrair_total_e_vencimento(texto_completo, nome_arquivo=""):
    """Extrai o total declarado ('Total a Pagar') e o vencimento do texto completo do PDF."""
    total_declarado = None
    vencimento = None

    # Padrões para "Total a Pagar" — cobre PDFs com e sem espaços (pdfplumber às vezes concatena)
    padroes_total = [
        r'Total\s*a\s*Pagar[\s\n]+R\$\s*([\d.,]+)',      # "Total a Pagar\nR$ 9.276,90"
        r'Total\s*a\s*Pagar\s+R\$\s*([\d.,]+)',           # "Total a Pagar R$ 9.276,90" (inline)
        r'TotalaPagar\s+R\$\s*([\d.,]+)',                  # "TotalaPagar R$ 16.027,69" (sem espaços)
        r'TotalaPagar[\s\n]+R\$\s*([\d.,]+)',
        r'Pagamento\s*Total\s+R\$\s*([\d.,]+)',            # "PagamentoTotal R$16.027,69"
        r'PagamentoTotal\s+R\$\s*([\d.,]+)',
        r'1\s+Pagamento\s*Total\s+R\$([\d.,]+)',           # "1 PagamentoTotal R$16.027,69"
    ]
    for padrao in padroes_total:
        m = re.search(padrao, texto_completo, re.IGNORECASE)
        if m:
            try:
                total_declarado = float(m.group(1).replace('.', '').replace(',', '.'))
            except ValueError:
                pass
            break

    # Padrão para vencimento — aceita tanto no mesmo linha quanto na linha seguinte
    padroes_venc = [
        r'Vencimento[\s\n]+(\d{2}/\d{2}/\d{4})',
        r'Vencimento\s+(\d{2}/\d{2}/\d{4})',
        r'R\$\s*[\d.,]+\s+(\d{2}/\d{2}/\d{4})', # "R$ 16.027,69 05/12/2024"
    ]
    for padrao in padroes_venc:
        m_venc = re.search(padrao, texto_completo, re.IGNORECASE)
        if m_venc:
            try:
                vencimento = pd.to_datetime(m_venc.group(1), format='%d/%m/%Y').strftime('%Y-%m-%d')
            except Exception:
                pass
            if vencimento: break

    # Fallback para vencimento: linha contendo "TotalaPagar ... DD/MM/YYYY"
    if not vencimento:
        m_fallback = re.search(r'TotalaPagar[\s\wА-я]*\s+(\d{2}/\d{2}/\d{4})', texto_completo, re.IGNORECASE)
        if m_fallback:
            try:
                vencimento = pd.to_datetime(m_fallback.group(1), format='%d/%m/%Y').strftime('%Y-%m-%d')
            except Exception:
                pass

    # Fallback 2: Tentar extrair do nome do arquivo (padrao fatura-YYYYMMDD ou fatura_YYYYMMDD)
    if not vencimento:
        m_name = re.search(r'fatura[_-](\d{4})(\d{2})(\d{2})', nome_arquivo, re.IGNORECASE)
        if m_name:
            vencimento = f"{m_name.group(1)}-{m_name.group(2)}-{m_name.group(3)}"

    return total_declarado, vencimento


def salvar_total_fatura(nome_arquivo, total_declarado, vencimento):
    """Persiste o total declarado e vencimento de um PDF de fatura na tabela totais_fatura_cartao."""
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO totais_fatura_cartao (fonte_arquivo, total_declarado, vencimento)
        VALUES (?, ?, ?)
        ON CONFLICT(fonte_arquivo) DO UPDATE SET
            total_declarado=excluded.total_declarado,
            vencimento=excluded.vencimento,
            data_processamento=datetime('now','localtime')
    ''', (nome_arquivo, total_declarado, vencimento))
    conn.commit()
    conn.close()


def salvar_despesas_no_banco(despesas, nome_arquivo_fonte):
    """Salva uma lista de despesas no banco de dados SQLite."""
    if not despesas:
        return 0

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Remove registros anteriores do mesmo arquivo para evitar duplicatas ao reprocessar,
    # permitindo agora que itens idênticos (mesma data/desc/valor) coexistam se vierem do mesmo PDF
    cursor.execute("DELETE FROM despesas_cartao WHERE fonte_arquivo = ?", (nome_arquivo_fonte,))
    
    registros_inseridos = 0

    for despesa in despesas:
        try:
            data_formatada = pd.to_datetime(despesa['Data'], format='%d/%m/%Y').strftime('%Y-%m-%d')
            valor_float = float(despesa['Valor (R$)'].replace('.', '').replace(',', '.'))

            cursor.execute(
                "INSERT INTO despesas_cartao (data, descricao, valor, fonte_arquivo) VALUES (?, ?, ?, ?)",
                (data_formatada, despesa['Descrição'], valor_float, nome_arquivo_fonte)
            )
            registros_inseridos += 1
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

            # Extrai e salva o total declarado e vencimento da fatura
            with pdfplumber.open(caminho_origem, password="08700599719") as pdf:
                texto = "".join(p.extract_text() for p in pdf.pages if p.extract_text())
            total_decl, vencimento = extrair_total_e_vencimento(texto, nome_arquivo)
            salvar_total_fatura(nome_arquivo, total_decl, vencimento)
            if total_decl:
                print(f"  Total declarado: R$ {total_decl:,.2f} | Vencimento: {vencimento}")
            else:
                print(f"  ⚠ Total declarado não encontrado no PDF.")

            print(f"{registros_inseridos} novos registros inseridos no banco de dados.")

            shutil.move(caminho_origem, caminho_destino)
            print(f"Arquivo '{nome_arquivo}' processado e movido para '{PROCESSADAS_DIR}'.")

        except Exception as e:
            print(f"Erro ao processar o arquivo {nome_arquivo}: {e}")

    print(f"\nProcessamento concluído. Total de {total_registros_inseridos} novos registros inseridos.")


if __name__ == "__main__":
    main()
