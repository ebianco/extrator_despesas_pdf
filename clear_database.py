import sqlite3
import os

DATABASE_FILE = os.path.join(os.path.dirname(__file__), 'despesas.db')

def clear_data():
    """Deleta todos os dados das tabelas 'despesas_cartao' and 'movimentacoes_bancarias'."""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        cursor.execute('DELETE FROM despesas_cartao')
        print(f"Todos os dados da tabela 'despesas_cartao' foram deletados.")

        cursor.execute('DELETE FROM movimentacoes_bancarias')
        print(f"Todos os dados da tabela 'movimentacoes_bancarias' foram deletados.")

        conn.commit()
        conn.close()
        print("\nOperação de limpeza concluída com sucesso.")

    except sqlite3.OperationalError as e:
        print(f"Erro operacional: {e}. Verifique se as tabelas existem.")
    except Exception as e:
        print(f"Ocorreu um erro: {e}")

if __name__ == '__main__':
    clear_data()
