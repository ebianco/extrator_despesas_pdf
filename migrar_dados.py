import pandas as pd
import sqlite3
import os
from database import get_db_connection, DATABASE_FILE

# Caminhos para os arquivos CSV
PLANILHAS_DIR = os.path.join(os.path.dirname(__file__), 'planilhas')
DESPESAS_CSV = os.path.join(PLANILHAS_DIR, 'despesas_consolidadas.csv')
EXTRATO_CSV = os.path.join(PLANILHAS_DIR, 'extrato_consolidado.csv')

def migrar_despesas_cartao():
    """Lê o CSV de despesas do cartão e insere os dados no banco."""
    if not os.path.exists(DESPESAS_CSV):
        print(f"Arquivo não encontrado: {DESPESAS_CSV}")
        return

    print("Iniciando migração de despesas do cartão...")
    df = pd.read_csv(DESPESAS_CSV, delimiter=';')

    # Limpeza e transformação dos dados
    df['Valor'] = df['Valor (R$)'].str.replace('.', '', regex=False).str.replace(',', '.', regex=False).astype(float)
    # Adiciona o ano de 2023. O ideal seria extrair o ano do nome do arquivo original.
    df['Data'] = pd.to_datetime(df['Data'] + '/2023', format='%d/%m/%Y')

    conn = get_db_connection()
    cursor = conn.cursor()

    for _, row in df.iterrows():
        try:
            cursor.execute(
                "INSERT INTO despesas_cartao (data, descricao, valor) VALUES (?, ?, ?)",
                (row['Data'].strftime('%Y-%m-%d'), row['Descrição'], row['Valor'])
            )
        except sqlite3.IntegrityError:
            # Ignora a inserção se o registro já existir (baseado no índice único)
            continue

    conn.commit()
    conn.close()
    print("Migração de despesas do cartão concluída.")

def migrar_movimentacoes_bancarias():
    """Lê o CSV do extrato consolidado e insere os dados no banco."""
    if not os.path.exists(EXTRATO_CSV):
        print(f"Arquivo não encontrado: {EXTRATO_CSV}")
        return

    print("Iniciando migração de movimentações bancárias...")
    df = pd.read_csv(EXTRATO_CSV, delimiter=';')

    # Limpeza e transformação dos dados
    df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y')
    df['valor'] = pd.to_numeric(df['valor'])

    conn = get_db_connection()
    cursor = conn.cursor()

    for _, row in df.iterrows():
        try:
            cursor.execute(
                "INSERT INTO movimentacoes_bancarias (data, descricao, valor) VALUES (?, ?, ?)",
                (row['data'].strftime('%Y-%m-%d'), row['descricao'], row['valor'])
            )
        except sqlite3.IntegrityError:
            # Ignora a inserção se o registro já existir
            continue

    conn.commit()
    conn.close()
    print("Migração de movimentações bancárias concluída.")

if __name__ == '__main__':
    if os.path.exists(DATABASE_FILE):
        print("Iniciando processo de migração de dados para o SQLite.")
        migrar_despesas_cartao()
        migrar_movimentacoes_bancarias()
        print("Processo de migração finalizado.")
    else:
        print("Banco de dados não encontrado. Execute 'python database.py' primeiro.")
