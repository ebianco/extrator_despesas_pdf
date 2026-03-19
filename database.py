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

    # Tabela para a memória das escolhas manuais do usuário
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS regras_usuario (
            descricao TEXT PRIMARY KEY,
            categoria TEXT NOT NULL,
            tipo TEXT
        )
    ''')

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

    # Tabela para saldos iniciais e finais de cada mês
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS saldos_mes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ano TEXT NOT NULL,
            mes TEXT NOT NULL,
            saldo_inicial REAL,
            saldo_final REAL,
            UNIQUE(ano, mes)
        )
    ''')
    
    # Nova tabela para o mapeamento obrigatório entre Categoria e Tipo
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categoria_tipo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            categoria TEXT NOT NULL,
            tipo TEXT NOT NULL,
            UNIQUE(categoria, tipo)
        )
    ''')

    # Tabela para associação explícita entre pagamento de fatura (extrato) e mês da fatura do cartão
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fatura_associacao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            movimentacao_id INTEGER NOT NULL,
            fatura_ano TEXT NOT NULL,
            fatura_mes TEXT NOT NULL,
            confirmado INTEGER DEFAULT 0,
            UNIQUE(movimentacao_id),
            FOREIGN KEY(movimentacao_id) REFERENCES movimentacoes_bancarias(id) ON DELETE CASCADE
        )
    ''')

    # Tabela para o total declarado em cada arquivo PDF de fatura de cartão
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS totais_fatura_cartao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fonte_arquivo TEXT NOT NULL UNIQUE,
            total_declarado REAL,
            vencimento TEXT,
            data_processamento TEXT DEFAULT (datetime('now','localtime'))
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
    try:
        cursor.execute('ALTER TABLE despesas_cartao ADD COLUMN parent_transaction_id INTEGER')
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute('ALTER TABLE movimentacoes_bancarias ADD COLUMN parent_transaction_id INTEGER')
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute('ALTER TABLE regras_usuario ADD COLUMN tipo TEXT')
    except sqlite3.OperationalError:
        pass

    # Adiciona um índice único para evitar duplicatas
    try:
        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_movimentacao_unica 
            ON movimentacoes_bancarias(data, descricao, valor)
        ''')
    except sqlite3.OperationalError:
        pass
    except sqlite3.IntegrityError:
        pass

    conn.commit()
    
    # Carga inicial da tabela categoria_tipo se estiver vazia
    cursor.execute('SELECT COUNT(*) FROM categoria_tipo')
    if cursor.fetchone()[0] == 0:
        carga_inicial = [
            ('Moradia', 'Aluguel'), ('Moradia', 'Condomínio'), ('Moradia', 'IPTU'), ('Moradia', 'Financiamento imobiliário'), ('Moradia', 'Seguro residencial'), ('Moradia', 'Reformas e manutenção'),
            ('Alimentação', 'Supermercado'), ('Alimentação', 'Feira / hortifrúti'), ('Alimentação', 'Açougue / peixaria'), ('Alimentação', 'Padaria'), ('Alimentação', 'Restaurante'), ('Alimentação', 'Delivery / iFood'), ('Alimentação', 'Lanchonete'),
            ('Transporte', 'Combustível'), ('Transporte', 'Estacionamento'), ('Transporte', 'Manutenção do veículo'), ('Transporte', 'IPVA / seguro auto'), ('Transporte', 'Transporte público'), ('Transporte', 'Táxi / Uber'), ('Transporte', 'Pedágio'),
            ('Saúde', 'Plano de saúde'), ('Saúde', 'Consultas médicas'), ('Saúde', 'Exames'), ('Saúde', 'Medicamentos'), ('Saúde', 'Plano odontológico'), ('Saúde', 'Academia / esportes'), ('Saúde', 'Psicólogo / terapia'),
            ('Educação', 'Escola / mensalidade'), ('Educação', 'Faculdade'), ('Educação', 'Cursos e idiomas'), ('Educação', 'Material escolar'), ('Educação', 'Livros'), ('Educação', 'Plataformas educativas'),
            ('Lazer', 'Streaming'), ('Lazer', 'Assinaturas digitais'), ('Lazer', 'Cinema / teatro'), ('Lazer', 'Viagens'), ('Lazer', 'Passeios e eventos'), ('Lazer', 'Hobbies'), ('Lazer', 'Brinquedos / games'),
            ('Vestuário', 'Roupas adulto'), ('Vestuário', 'Roupas infantil'), ('Vestuário', 'Calçados'), ('Vestuário', 'Acessórios'), ('Vestuário', 'Uniforme escolar'),
            ('Serviços domésticos', 'Energia elétrica'), ('Serviços domésticos', 'Água e esgoto'), ('Serviços domésticos', 'Gás'), ('Serviços domésticos', 'Internet / telefone fixo'), ('Serviços domésticos', 'Celular'), ('Serviços domésticos', 'TV a cabo / satélite'), ('Serviços domésticos', 'Diarista / faxineira'),
            ('Finanças e seguros', 'Cartão de crédito'), ('Finanças e seguros', 'Empréstimo pessoal'), ('Finanças e seguros', 'Seguro de vida'), ('Finanças e seguros', 'Previdência privada'), ('Finanças e seguros', 'Investimentos'), ('Finanças e seguros', 'Juros / tarifas bancárias'),
            ('Cuidado pessoal', 'Salão / barbearia'), ('Cuidado pessoal', 'Produtos de higiene'), ('Cuidado pessoal', 'Cosméticos / perfumaria'), ('Cuidado pessoal', 'Farmácia (não médica)'),
            ('Pets', 'Ração'), ('Pets', 'Veterinário'), ('Pets', 'Banho e tosa'), ('Pets', 'Medicamentos pet'), ('Pets', 'Acessórios pet'),
            ('Doações e presentes', 'Presentes'), ('Doações e presentes', 'Doações'), ('Doações e presentes', 'Mesada / ajuda a familiares')
        ]
        cursor.executemany('INSERT INTO categoria_tipo (categoria, tipo) VALUES (?, ?)', carga_inicial)
        conn.commit()

    conn.close()

def salvar_regra_usuario(descricao, categoria=None, tipo=None):
    """Salva ou atualiza uma regra de classificação do usuário. Inferindo a categoria pelo tipo se ausente."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Se o tipo é fornecido mas não a categoria, buscar categoria do mapeamento
    if tipo and not categoria:
        cursor.execute("SELECT categoria FROM categoria_tipo WHERE tipo = ?", (tipo,))
        row = cursor.fetchone()
        if row:
            categoria = row['categoria']
            
    cursor.execute('''
        INSERT INTO regras_usuario (descricao, categoria, tipo)
        VALUES (?, ?, ?)
        ON CONFLICT(descricao) DO UPDATE SET 
            categoria=excluded.categoria,
            tipo=excluded.tipo
    ''', (descricao, categoria, tipo))
    conn.commit()
    conn.close()

if __name__ == '__main__':
    print(f"Verificando e criando tabelas no banco de dados '{DATABASE_FILE}'...")
    create_tables()
    print("Tabelas prontas.")
