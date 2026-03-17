import pandas as pd
from database import get_db_connection
import os

# Caminhos para os arquivos CSV
DESPESAS_CSV = os.path.join('planilhas', 'despesas_analisadas.csv')
EXTRATO_CSV = os.path.join('planilhas', 'extrato_analisado.csv')

def limpar_tabelas():
    """Limpa todos os dados das tabelas de despesas e movimentações."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM despesas_cartao")
    cursor.execute("DELETE FROM movimentacoes_bancarias")
    # Reseta a sequência de autoincremento se houver
    cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('despesas_cartao', 'movimentacoes_bancarias')")
    conn.commit()
    conn.close()
    print("Tabelas 'despesas_cartao' e 'movimentacoes_bancarias' limpas.")

def carregar_despesas_cartao():
    """Carrega os dados do CSV de despesas do cartão para o banco de dados."""
    df = pd.read_csv(DESPESAS_CSV, sep=';', header=0)
    df.columns = ['data', 'descricao', 'valor', 'subcategoria', 'categoria']

    # Adiciona o ano de 2023 às datas no formato 'dd/mm'
    df['data'] = df['data'].astype(str) + '/2023'
    df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y', errors='coerce').dt.strftime('%Y-%m-%d')
    df['valor'] = df['valor'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False).astype(float)
    df['fonte_arquivo'] = 'despesas_analisadas.csv'

    df.dropna(subset=['data'], inplace=True)
    df.drop_duplicates(subset=['data', 'descricao', 'valor'], inplace=True)

    df_to_db = df[['data', 'descricao', 'valor', 'categoria', 'fonte_arquivo']]

    conn = get_db_connection()
    df_to_db.to_sql('despesas_cartao', conn, if_exists='append', index=False)
    conn.close()
    print(f"{len(df_to_db)} registros de despesas do cartão carregados.")

def carregar_movimentacoes_bancarias():
    """Carrega os dados do CSV do extrato bancário para o banco de dados."""
    df = pd.read_csv(EXTRATO_CSV, sep=';')
    df.columns = ['data', 'descricao', 'valor', 'subcategoria', 'categoria']
    df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y').dt.strftime('%Y-%m-%d')
    df['valor'] = df['valor'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False).astype(float)
    df['fonte_arquivo'] = 'extrato_analisado.csv'

    # Mantendo apenas as colunas que correspondem à tabela do banco de dados
    df_to_db = df[['data', 'descricao', 'valor', 'categoria', 'fonte_arquivo']]
    
    # Remove duplicatas antes de inserir
    df_to_db.drop_duplicates(subset=['data', 'descricao', 'valor'], inplace=True)

    conn = get_db_connection()
    df_to_db.to_sql('movimentacoes_bancarias', conn, if_exists='append', index=False)
    conn.close()
    print(f"{len(df_to_db)} registros de movimentações bancárias carregados.")

def main():
    """Função principal para orquestrar a limpeza e o carregamento dos dados."""
    limpar_tabelas()
    carregar_despesas_cartao()
    carregar_movimentacoes_bancarias()
    print("\nCarregamento de dados a partir dos arquivos CSV concluído com sucesso.")

if __name__ == '__main__':
    main()
