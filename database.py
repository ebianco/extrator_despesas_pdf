import sqlite3
import os

DATABASE_FILE = os.path.join(os.path.dirname(__file__), 'despesas.db')

def get_db_connection():
    """Cria e retorna uma conexão com o banco de dados SQLite."""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def create_tables():
    """Cria as tabelas no banco de dados, se elas não existirem."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Tabela para despesas do cartão de crédito
    cursor.execute('''CREATE TABLE IF NOT EXISTS despesas_cartao (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        data TEXT,
                        descricao TEXT,
                        valor REAL,
                        fonte_arquivo TEXT,
                        tipo TEXT,
                        categoria TEXT,
                        UNIQUE(data, descricao, valor)
                    )''')

    # Tabela para movimentações do extrato bancário
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movimentacoes_bancarias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data DATE NOT NULL,
            descricao TEXT NOT NULL,
            valor REAL NOT NULL,
            fonte_arquivo TEXT
        )
    ''')

    # Adiciona colunas 'tipo' e 'categoria' se não existirem
    try:
        cursor.execute('ALTER TABLE movimentacoes_bancarias ADD COLUMN tipo TEXT')
    except sqlite3.OperationalError:
        pass  # A coluna já existe

    try:
        cursor.execute('ALTER TABLE movimentacoes_bancarias ADD COLUMN categoria TEXT')
    except sqlite3.OperationalError:
        pass  # A coluna já existe

    # Adiciona colunas à tabela despesas_cartao se não existirem
    try:
        cursor.execute('ALTER TABLE despesas_cartao ADD COLUMN tipo TEXT')
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute('ALTER TABLE despesas_cartao ADD COLUMN categoria TEXT')
    except sqlite3.OperationalError:
        pass

    # Adiciona um índice único para evitar duplicatas
    cursor.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_despesa_unica 
        ON despesas_cartao(data, descricao, valor)
    ''')

    cursor.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_movimentacao_unica 
        ON movimentacoes_bancarias(data, descricao, valor)
    ''')

    conn.commit()
    conn.close()

if __name__ == '__main__':
    print(f"Verificando e criando tabelas no banco de dados '{DATABASE_FILE}'...")
    create_tables()
    print("Tabelas prontas.")
