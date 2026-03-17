from flask import Flask, jsonify, render_template
import pandas as pd
from database import get_db_connection

app = Flask(__name__)

@app.route('/')
def index():
    """Serve a página principal do dashboard."""
    return render_template('index.html')

@app.route('/transacoes')
def transacoes():
    """Serve a página de listagem de transações completas."""
    return render_template('transacoes.html')

@app.route('/api/gastos_por_categoria')
def gastos_por_categoria():
    """Fornece dados de gastos agregados por categoria."""
    from flask import request
    mes = request.args.get('mes')
    ano = request.args.get('ano')
    
    conn = get_db_connection()
    query = """
        WITH todas_movimentacoes AS (
            SELECT data, descricao, valor, categoria FROM movimentacoes_bancarias
            UNION ALL
            SELECT data, descricao, -valor, categoria FROM despesas_cartao
        )
        SELECT categoria, SUM(valor) as total
        FROM todas_movimentacoes
        WHERE categoria IS NOT NULL
    """
    params = []
    if ano:
        query += " AND strftime('%Y', data) = ?"
        params.append(ano)
    if mes:
        # Assuming mes is '01', '02', etc.
        query += " AND strftime('%m', data) = ?"
        params.append(mes)
        
    query += """
        GROUP BY categoria
        ORDER BY total DESC
    """
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return jsonify(df.to_dict(orient='records'))

@app.route('/api/despesas_recentes')
def despesas_recentes():
    """Fornece as 10 despesas mais recentes."""
    from flask import request
    mes = request.args.get('mes')
    ano = request.args.get('ano')

    conn = get_db_connection()
    query = """
        WITH todas_movimentacoes AS (
            SELECT data, descricao, categoria, valor, 'Extrato Bancário' as origem FROM movimentacoes_bancarias
            UNION ALL
            SELECT data, descricao, categoria, -valor as valor, 'Cartão de Crédito' as origem FROM despesas_cartao
        )
        SELECT data, descricao, categoria, origem, printf('%.2f', valor) as valor
        FROM todas_movimentacoes
        WHERE 1=1
    """
    params = []
    if ano:
        query += " AND strftime('%Y', data) = ?"
        params.append(ano)
    if mes:
        query += " AND strftime('%m', data) = ?"
        params.append(mes)
        
    query += """
        ORDER BY data DESC
        LIMIT 10
    """
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return jsonify(df.to_dict(orient='records'))

@app.route('/api/gastos_evolucao_tempo')
def gastos_evolucao_tempo():
    """Fornece dados para o gráfico de evolução de gastos, com meses preenchidos."""
    from flask import request
    ano = request.args.get('ano')
    
    conn = get_db_connection()
    query = """
        WITH todas_movimentacoes AS (
            SELECT data, descricao, valor, categoria FROM movimentacoes_bancarias
            UNION ALL
            SELECT data, descricao, -valor as valor, categoria FROM despesas_cartao
        )
        SELECT 
            strftime('%Y-%m', data) as mes,
            categoria,
            SUM(valor) as total
        FROM todas_movimentacoes
        WHERE categoria IS NOT NULL
    """
    params = []
    if ano:
        query += " AND strftime('%Y', data) = ?"
        params.append(ano)
        
    query += """
        GROUP BY mes, categoria
    """
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()

    if df.empty:
        return jsonify([])

    # Pivotar os dados para ter meses como índice e categorias como colunas
    pivot_df = df.pivot(index='mes', columns='categoria', values='total').fillna(0)

    # Criar um range completo de meses
    start_date = pd.to_datetime(df['mes'].min() + '-01')
    end_date = pd.to_datetime(df['mes'].max() + '-01')
    all_months = pd.date_range(start_date, end_date, freq='MS').strftime('%Y-%m')

    # Reindexar o DataFrame para incluir todos os meses, preenchendo com 0
    pivot_df = pivot_df.reindex(all_months, fill_value=0)

    # Desfazer o pivot para o formato original (long format)
    result_df = pivot_df.reset_index().melt(id_vars='index', var_name='categoria', value_name='total')
    result_df.rename(columns={'index': 'mes'}, inplace=True)

    return jsonify(result_df.to_dict(orient='records'))

@app.route('/api/sankey_data')
def sankey_data():
    """Fornece dados para o gráfico de Sankey, mostrando o fluxo de renda para despesas."""
    from flask import request
    mes = request.args.get('mes')
    ano = request.args.get('ano')
    
    conn = get_db_connection()
    query = """
        WITH todas_movimentacoes AS (
            SELECT data, descricao, valor, categoria FROM movimentacoes_bancarias
            UNION ALL
            SELECT data, descricao, -valor as valor, categoria FROM despesas_cartao
        )
        SELECT categoria, SUM(valor) as total 
        FROM todas_movimentacoes 
        WHERE categoria IS NOT NULL
    """
    params = []
    if ano:
        query += " AND strftime('%Y', data) = ?"
        params.append(ano)
    if mes:
        query += " AND strftime('%m', data) = ?"
        params.append(mes)
        
    query += " GROUP BY categoria"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()

    # Separa receitas e despesas
    receitas = df[df['total'] > 0]
    despesas = df[df['total'] < 0]

    # Formata os dados para o gráfico de Sankey
    sankey_links = []
    # Conecta fontes de renda a um nó central 'Renda'
    for index, row in receitas.iterrows():
        sankey_links.append([row['categoria'], 'Renda', row['total']])
    
    # Conecta 'Renda' às categorias de despesa
    for index, row in despesas.iterrows():
        # O valor da despesa deve ser positivo para o gráfico
        sankey_links.append(['Renda', row['categoria'], -row['total']])

    return jsonify(sankey_links)

@app.route('/api/transacoes')
def listar_transacoes():
    """Fornece a lista paginada e filtrada de todas as transações."""
    from flask import request
    
    # Parâmetros de Paginação
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 50))
    offset = (page - 1) * limit
    
    # Parâmetros de Filtro
    search = request.args.get('search', '').lower()
    mes = request.args.get('mes')
    ano = request.args.get('ano')
    categoria = request.args.get('categoria')
    origem = request.args.get('origem') # 'Cartão de Crédito' ou 'Extrato Bancário'

    conn = get_db_connection()
    
    base_query = """
        WITH todas_movimentacoes AS (
            SELECT id, data, descricao, categoria, valor, 'Extrato Bancário' as origem FROM movimentacoes_bancarias
            UNION ALL
            SELECT id, data, descricao, categoria, -valor as valor, 'Cartão de Crédito' as origem FROM despesas_cartao
        )
        SELECT * FROM todas_movimentacoes
        WHERE 1=1
    """
    
    params = []
    
    if search:
        base_query += " AND LOWER(descricao) LIKE ?"
        params.append(f"%{search}%")
    if ano:
        base_query += " AND strftime('%Y', data) = ?"
        params.append(ano)
    if mes:
        base_query += " AND strftime('%m', data) = ?"
        params.append(mes)
    if categoria:
        if categoria.upper() == 'TBD':
            base_query += " AND (categoria IS NULL OR categoria = 'TBD')"
        else:
            base_query += " AND categoria = ?"
            params.append(categoria)
    if origem:
        base_query += " AND origem = ?"
        params.append(origem)

    # Conta o total de registros com os filtros aplicados
    count_query = f"SELECT COUNT(*) as total FROM ({base_query})"
    total_records = conn.execute(count_query, params).fetchone()['total']
    
    # Aplica ordenação e paginação
    data_query = base_query + " ORDER BY data DESC LIMIT ? OFFSET ?"
    params.extend([int(limit), int(offset)])
    
    df = pd.read_sql_query(data_query, conn, params=params)
    conn.close()

    return jsonify({
        'data': df.to_dict(orient='records'),
        'total': total_records,
        'page': page,
        'limit': limit,
        'total_pages': (total_records + limit - 1) // limit
    })

if __name__ == '__main__':
    app.run(debug=True)
