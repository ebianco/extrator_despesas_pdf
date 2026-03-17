import pandas as pd
import argparse
from database import get_db_connection

def execute_query(query):
    """
    Executa uma consulta SQL no banco de dados e exibe o resultado.

    Args:
        query (str): A consulta SQL a ser executada.
    """
    try:
        conn = get_db_connection()
        df = pd.read_sql_query(query, conn)
        conn.close()

        if df.empty:
            print("A consulta não retornou resultados.")
        else:
            # Configura o pandas para exibir todas as colunas e linhas
            pd.set_option('display.max_rows', None)
            pd.set_option('display.max_columns', None)
            pd.set_option('display.width', None)
            pd.set_option('display.max_colwidth', None)
            print(df)

    except Exception as e:
        print(f"Ocorreu um erro ao executar a consulta: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Execute uma consulta SQL no banco de dados de despesas.',
        epilog='Exemplo de uso: python query.py "SELECT * FROM despesas_cartao WHERE categoria = \'Refeição\' LIMIT 10"'
    )
    parser.add_argument('query', type=str, help='A consulta SQL a ser executada entre aspas.')

    args = parser.parse_args()
    execute_query(args.query)
