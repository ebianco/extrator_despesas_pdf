from flask import Flask, jsonify, render_template
import pandas as pd
from database import get_db_connection

app = Flask(__name__)

@app.route('/')
def index():
    """Serve a página principal do dashboard."""
    return render_template('index.html')

@app.route('/api/atualizar_categoria', methods=['POST'])
def atualizar_categoria():
    """Recebe classificação manual do usuário e atualiza banco em lote, inferindo a categoria pelo tipo."""
    from flask import request
    dados = request.json
    descricao = dados.get('descricao')
    nova_tipo = dados.get('nova_tipo')
    nova_categoria = dados.get('nova_categoria') # Para manter compatibilidade com frontends antigos

    if not descricao or not nova_tipo:
        return jsonify({"error": "Descrição e nova_tipo são obrigatórios"}), 400

    from database import salvar_regra_usuario, get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Infere a categoria a partir do tipo
    if nova_tipo:
        cursor.execute("SELECT categoria FROM categoria_tipo WHERE tipo = ?", (nova_tipo,))
        row = cursor.fetchone()
        if row:
            nova_categoria = row['categoria']
    
    # Salva a regra do usuário (a própria função agora tenta inferir a categoria, mas já fizemos aqui)
    salvar_regra_usuario(descricao, nova_categoria, nova_tipo)
    
    # Atualiza em lote 
    cursor.execute("""
        UPDATE movimentacoes_bancarias 
        SET categoria = ?, tipo = ?
        WHERE descricao = ? AND (categoria IS NULL OR categoria = 'TBD')
    """, (nova_categoria, nova_tipo, descricao))
    updated_bancarias = cursor.rowcount

    cursor.execute("""
        UPDATE despesas_cartao
        SET categoria = ?, tipo = ?
        WHERE descricao = ? AND (categoria IS NULL OR categoria = 'TBD')
    """, (nova_categoria, nova_tipo, descricao))
    updated_cartao = cursor.rowcount

    conn.commit()
    conn.close()

    total_updated = updated_bancarias + updated_cartao
    return jsonify({"status": "success", "updated_count": total_updated})

@app.route('/transacoes')
def transacoes():
    """Serve a página de listagem de transações completas."""
    return render_template('transacoes.html')

@app.route('/fluxo')
def fluxo():
    """Serve a página de Fluxo Financeiro (Tree Table)."""
    return render_template('fluxo.html')

@app.route('/consulta_db')
def consulta_db():
    """Serve a página de Consulta Direta ao DB."""
    return render_template('consulta_db.html')

@app.route('/categorias_tipos')
def categorias_tipos():
    """Serve a página de manutenção de Categorias e Tipos."""
    return render_template('categorias_tipos.html')

@app.route('/api/categorias_tipos', methods=['GET'])
def listar_categorias_tipos():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM categoria_tipo ORDER BY categoria, tipo", conn)
    conn.close()
    return jsonify(df.to_dict(orient='records'))

@app.route('/api/categorias_tipos', methods=['POST'])
def salvar_categoria_tipo():
    from flask import request
    dados = request.json
    categoria = dados.get('categoria')
    tipo = dados.get('tipo')
    
    if not categoria or not tipo:
         return jsonify({"error": "Categoria e tipo são obrigatórios"}), 400
         
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO categoria_tipo (categoria, tipo) VALUES (?, ?)", (categoria, tipo))
        conn.commit()
        ret_id = cursor.lastrowid
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 400
        
    conn.close()
    return jsonify({"status": "success", "id": ret_id})

@app.route('/api/categorias_tipos/<int:id>', methods=['DELETE'])
def remover_categoria_tipo(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM categoria_tipo WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

# ─── Associação Fatura ─────────────────────────────────────────────────────────

@app.route('/associacao_faturas')
def associacao_faturas():
    """Serve a página de associação entre pagamento de fatura e mês da fatura do cartão."""
    return render_template('associacao_faturas.html')

@app.route('/api/fatura_associacoes', methods=['GET'])
def listar_fatura_associacoes():
    """Retorna todos os pagamentos de fatura do extrato, com a associação persistida (se houver)."""
    conn = get_db_connection()

    # Busca pagamentos de fatura: categoria "Finanças e seguros" + tipo "Cartão de crédito"
    pagamentos = conn.execute("""
        SELECT mb.id, mb.data, mb.descricao, mb.valor, mb.tipo, mb.categoria,
               fa.id AS assoc_id, fa.fatura_ano, fa.fatura_mes, fa.confirmado
        FROM movimentacoes_bancarias mb
        LEFT JOIN fatura_associacao fa ON fa.movimentacao_id = mb.id
        WHERE INSTR(LOWER(COALESCE(mb.categoria,'')), 'finan') > 0
          AND INSTR(LOWER(COALESCE(mb.categoria,'')), 'seguro') > 0
          AND INSTR(LOWER(COALESCE(mb.tipo,'')), 'cart') > 0
        ORDER BY mb.data DESC
    """).fetchall()

    # Para cada mês de fatura do cartão, busca o total declarado e a contagem de itens
    totais_fatura = conn.execute("""
        SELECT 
            strftime('%Y', vencimento) AS ano, 
            strftime('%m', vencimento) AS mes,
            SUM(total_declarado) AS total,
            (
                SELECT COUNT(*) 
                FROM despesas_cartao dc 
                JOIN totais_fatura_cartao t2 ON dc.fonte_arquivo = t2.fonte_arquivo
                WHERE strftime('%Y-%m', t2.vencimento) = strftime('%Y-%m', t.vencimento)
            ) AS qtd
        FROM totais_fatura_cartao t
        GROUP BY ano, mes
        ORDER BY ano DESC, mes DESC
    """).fetchall()
    totais_map = {f"{r['ano']}-{r['mes']}": {'total': r['total'], 'qtd': r['qtd']} for r in totais_fatura}

    conn.close()

    result = []
    for p in pagamentos:
        row = dict(p)
        assoc_key = None
        fatura_total = None
        fatura_qtd = None
        if row.get('fatura_ano') and row.get('fatura_mes'):
            assoc_key = f"{row['fatura_ano']}-{row['fatura_mes'].zfill(2)}"
            info = totais_map.get(assoc_key, {})
            fatura_total = info.get('total')
            fatura_qtd = info.get('qtd')
        row['fatura_total'] = fatura_total
        row['fatura_qtd'] = fatura_qtd
        row['diferenca'] = round(abs(row['valor']) - abs(fatura_total), 2) if fatura_total is not None else None
        result.append(row)

    return jsonify(result)

@app.route('/api/fatura_associacoes', methods=['POST'])
def salvar_fatura_associacao():
    """Cria ou atualiza a associação entre um pagamento de fatura e um mês de fatura do cartão."""
    from flask import request
    dados = request.json
    movimentacao_id = dados.get('movimentacao_id')
    fatura_ano = dados.get('fatura_ano')
    fatura_mes = dados.get('fatura_mes')
    confirmado = dados.get('confirmado', 1)

    if not movimentacao_id or not fatura_ano or not fatura_mes:
        return jsonify({'error': 'movimentacao_id, fatura_ano e fatura_mes são obrigatórios'}), 400

    conn = get_db_connection()
    conn.execute("""
        INSERT INTO fatura_associacao (movimentacao_id, fatura_ano, fatura_mes, confirmado)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(movimentacao_id) DO UPDATE SET
            fatura_ano=excluded.fatura_ano,
            fatura_mes=excluded.fatura_mes,
            confirmado=excluded.confirmado
    """, (movimentacao_id, fatura_ano, fatura_mes, confirmado))
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok'})

@app.route('/api/fatura_associacoes/<int:id>', methods=['DELETE'])
def remover_fatura_associacao(id):
    """Remove uma associação de fatura."""
    conn = get_db_connection()
    conn.execute("DELETE FROM fatura_associacao WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok'})

@app.route('/api/fatura_meses_disponiveis', methods=['GET'])
def fatura_meses_disponiveis():
    """Retorna os meses disponíveis baseados no vencimento da fatura (tabela totais_fatura_cartao).
    Filtra meses que já estão associados a algum pagamento no extrato.
    Se o parâmetro 'except_mov_id' for passado, inclui o mês associado àquela movimentação.
    """
    from flask import request
    except_mov_id = request.args.get('except_mov_id')
    
    conn = get_db_connection()
    
    query = """
        SELECT 
            strftime('%Y', vencimento) AS ano, 
            strftime('%m', vencimento) AS mes,
            SUM(total_declarado) AS total,
            (
                SELECT COUNT(*) 
                FROM despesas_cartao dc 
                JOIN totais_fatura_cartao t2 ON dc.fonte_arquivo = t2.fonte_arquivo
                WHERE strftime('%Y-%m', t2.vencimento) = strftime('%Y-%m', t.vencimento)
            ) AS qtd
        FROM totais_fatura_cartao t
        WHERE strftime('%Y-%m', vencimento) <= strftime('%Y-%m', 'now')
          AND (
              NOT EXISTS (
                  SELECT 1 FROM fatura_associacao fa 
                  WHERE fa.fatura_ano = strftime('%Y', t.vencimento) 
                    AND fa.fatura_mes = strftime('%m', t.vencimento)
              )
              OR (
                  ? IS NOT NULL AND EXISTS (
                      SELECT 1 FROM fatura_associacao fa2
                      WHERE fa2.movimentacao_id = ?
                        AND fa2.fatura_ano = strftime('%Y', t.vencimento)
                        AND fa2.fatura_mes = strftime('%m', t.vencimento)
                  )
              )
          )
        GROUP BY ano, mes
        ORDER BY ano DESC, mes DESC
    """
    rows = conn.execute(query, (except_mov_id, except_mov_id)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

# ─── Validação Cartão ──────────────────────────────────────────────────────────

@app.route('/validacao_cartao')
def validacao_cartao():
    """Serve a página de validação de dados extraídos das faturas de cartão."""
    return render_template('validacao_cartao.html')

@app.route('/api/validacao_cartao', methods=['GET'])
def api_validacao_cartao():
    """Retorna por arquivo: total declarado vs total extraído, com status e alertas."""
    conn = get_db_connection()

    # Total declarado por arquivo (da nova tabela)
    totais_decl = conn.execute("""
        SELECT fonte_arquivo, total_declarado, vencimento, data_processamento
        FROM totais_fatura_cartao
        ORDER BY vencimento DESC, fonte_arquivo DESC
    """).fetchall()

    # Total extraído por arquivo (excluindo parcelas futuras)
    totais_extr = conn.execute("""
        SELECT fonte_arquivo,
               SUM(valor) AS total_extraido,
               COUNT(*) AS qtd_total,
               SUM(CASE WHEN strftime('%Y-%m', data) > strftime('%Y-%m', 'now') THEN 1 ELSE 0 END) AS qtd_futuras,
               MIN(data) AS data_min,
               MAX(data) AS data_max
        FROM despesas_cartao
        GROUP BY fonte_arquivo
    """).fetchall()
    extr_map = {r['fonte_arquivo']: dict(r) for r in totais_extr}

    # Arquivos sem totais declarados (processados mas sem entrada em totais_fatura_cartao)
    todos_arquivos = conn.execute("""
        SELECT DISTINCT fonte_arquivo FROM despesas_cartao
    """).fetchall()
    conn.close()

    # Constrói resultado a partir de totais_fatura_cartao
    resultado = []
    arquivos_com_total = set()

    for row in totais_decl:
        nome = row['fonte_arquivo']
        arquivos_com_total.add(nome)
        extr = extr_map.get(nome, {})
        total_decl = row['total_declarado']
        total_extr = extr.get('total_extraido')
        diferenca = None
        if total_decl is not None and total_extr is not None:
            diferenca = round(total_decl - total_extr, 2)
        if total_decl is None:
            status = 'SEM_TOTAL'
        elif diferenca is not None and abs(diferenca) < 0.05:
            status = 'OK'
        else:
            status = 'DIVERGENTE'
        resultado.append({
            'fonte_arquivo': nome,
            'vencimento': row['vencimento'],
            'data_processamento': row['data_processamento'],
            'total_declarado': total_decl,
            'total_extraido': total_extr,
            'diferenca': diferenca,
            'qtd_total': extr.get('qtd_total'),
            'qtd_futuras': extr.get('qtd_futuras', 0),
            'data_min': extr.get('data_min'),
            'data_max': extr.get('data_max'),
            'status': status
        })

    # Arquivos que têm transações mas nenhum total declarado registrado
    for row in todos_arquivos:
        nome = row['fonte_arquivo']
        if nome not in arquivos_com_total:
            extr = extr_map.get(nome, {})
            resultado.append({
                'fonte_arquivo': nome,
                'vencimento': None,
                'data_processamento': None,
                'total_declarado': None,
                'total_extraido': extr.get('total_extraido'),
                'diferenca': None,
                'qtd_total': extr.get('qtd_total'),
                'qtd_futuras': extr.get('qtd_futuras', 0),
                'data_min': extr.get('data_min'),
                'data_max': extr.get('data_max'),
                'status': 'SEM_TOTAL'
            })

    resultado.sort(key=lambda x: x['vencimento'] or x['fonte_arquivo'], reverse=True)
    return jsonify(resultado)

@app.route('/api/validacao_cartao/detalhes/<path:filename>', methods=['GET'])
def api_validacao_cartao_detalhes(filename):
    """Retorna todos os lançamentos de um arquivo específico, ordenados por data."""
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT data, descricao, valor, categoria, tipo
        FROM despesas_cartao
        WHERE fonte_arquivo = ?
        ORDER BY data ASC
    """, (filename,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/auditoria')
def auditoria():
    """Serve a página de Auditoria de Conciliação."""
    return render_template('auditoria.html')


@app.route('/api/auditoria_detalhada')
def api_auditoria_detalhada():
    """Retorna dados de conciliação mensal: saldo inicial, créditos, débitos e saldo final."""
    conn = get_db_connection()
    
    # Busca todos os meses que possuem saldo registrado
    query_saldos = "SELECT ano, mes, saldo_inicial, saldo_final FROM saldos_mes ORDER BY ano DESC, mes DESC"
    df_saldos = pd.read_sql_query(query_saldos, conn)
    
    resultados = []
    
    for _, row in df_saldos.iterrows():
        ano = row['ano']
        mes = row['mes']
        saldo_inicial = row['saldo_inicial'] or 0.0
        saldo_final = row['saldo_final'] or 0.0
        
        # Filtro de data para o mês
        data_inicio = f"{ano}-{mes}-01"
        data_fim = f"{ano}-{mes}-31"
        
        # Soma créditos (valores positivos)
        query_creditos = "SELECT SUM(valor) as total FROM movimentacoes_bancarias WHERE data >= ? AND data <= ? AND valor > 0"
        res_cred = conn.execute(query_creditos, (data_inicio, data_fim)).fetchone()
        creditos = res_cred['total'] or 0.0
        
        # Soma débitos (valores negativos)
        query_debitos = "SELECT SUM(valor) as total FROM movimentacoes_bancarias WHERE data >= ? AND data <= ? AND valor < 0"
        res_deb = conn.execute(query_debitos, (data_inicio, data_fim)).fetchone()
        debitos = res_deb['total'] or 0.0
        
        # Cálculo de verificação
        saldo_calculado = saldo_inicial + creditos + debitos
        diferenca = saldo_calculado - saldo_final
        batch_match = abs(diferenca) < 0.01  # Tolerância para ponto flutuante
        
        resultados.append({
            'ano': ano,
            'mes': mes,
            'saldo_inicial': saldo_inicial,
            'creditos': creditos,
            'debitos': debitos,
            'saldo_final': saldo_final,
            'saldo_calculado': saldo_calculado,
            'diferenca': diferenca,
            'status': 'OK' if batch_match else 'ERRO'
        })
        
    conn.close()
    return jsonify(resultados)

@app.route('/api/fluxo_financeiro')
def api_fluxo_financeiro():
    """Retorna os dados hierárquicos do fluxo financeiro por período."""
    from flask import request
    
    # Parâmetros de início e fim
    mes_inicio = request.args.get('mes_inicio')
    ano_inicio = request.args.get('ano_inicio')
    mes_fim = request.args.get('mes_fim')
    ano_fim = request.args.get('ano_fim')
    
    # Fallback para compatibilidade se usar os antigos mes/ano
    if not mes_inicio: mes_inicio = request.args.get('mes')
    if not ano_inicio: ano_inicio = request.args.get('ano')
    if not mes_fim: mes_fim = mes_inicio
    if not ano_fim: ano_fim = ano_inicio

    conn = get_db_connection()
    
    saldo_inicial = None
    saldo_final = None
    
    # Saldo Inicial do período (baseado no mês de início)
    if ano_inicio and mes_inicio:
        row_init = conn.execute("SELECT saldo_inicial FROM saldos_mes WHERE ano = ? AND mes = ?", (ano_inicio, mes_inicio)).fetchone()
        if row_init:
            saldo_inicial = row_init['saldo_inicial']
    
    # Saldo Final do período (baseado no mês de fim)
    if ano_fim and mes_fim:
        row_end = conn.execute("SELECT saldo_final FROM saldos_mes WHERE ano = ? AND mes = ?", (ano_fim, mes_fim)).fetchone()
        if row_end:
            saldo_final = row_end['saldo_final']
    
    # Filtro de data range para as queries
    # Formato esperado para comparação: 'YYYY-MM-DD'
    data_inicio = f"{ano_inicio}-{mes_inicio}-01" if ano_inicio and mes_inicio else "1900-01-01"
    # Para o fim do período, vamos até o final do mês. 
    # Simplificação: comparamos com 'YYYY-MM-31' ou usamos strftime
    data_fim = f"{ano_fim}-{mes_fim}-31" if ano_fim and mes_fim else "2100-12-31"

    query_banco = "SELECT id, data, descricao, categoria, tipo, valor FROM movimentacoes_bancarias WHERE data >= ? AND data <= ?"
    params_banco = [data_inicio, data_fim]
    query_banco += " ORDER BY data ASC"
    df_banco = pd.read_sql_query(query_banco, conn, params=params_banco)
    
    # As despesas do cartão mostradas no drill-down são do MÊS ANTERIOR ao período do extrato,
    # pois o pagamento feito no mês N (vencimento dia 5) quita a fatura de lançamentos do mês N-1.
    from datetime import date
    def mes_anterior(ano_str, mes_str):
        ano_i, mes_i = int(ano_str), int(mes_str)
        if mes_i == 1:
            return str(ano_i - 1), '12'
        else:
            return str(ano_i), str(mes_i - 1).zfill(2)

    # A função mes_anterior será usada dentro do loop para fallbacks se necessário
    def mes_anterior(ano_str, mes_str):
        ano_i, mes_i = int(ano_str), int(mes_str)
        if mes_i == 1:
            return str(ano_i - 1), '12'
        else:
            return str(ano_i), str(mes_i - 1).zfill(2)

    conn.close()
    
    bank_txs = df_banco.to_dict(orient='records')

    # Busca todas as associações do banco para o range de movimentações
    mov_ids = [tx['id'] for tx in bank_txs]
    assoc_map = {}
    if mov_ids:
        conn_assoc = get_db_connection()
        placeholders = ', '.join(['?'] * len(mov_ids))
        query_assoc = f"SELECT movimentacao_id, fatura_ano, fatura_mes FROM fatura_associacao WHERE movimentacao_id IN ({placeholders})"
        rows_assoc = conn_assoc.execute(query_assoc, mov_ids).fetchall()
        assoc_map = {r['movimentacao_id']: (r['fatura_ano'], r['fatura_mes']) for r in rows_assoc}
        conn_assoc.close()

    # Processa cada movimentação bancária
    for tx in bank_txs:
        tx['children'] = []
        tx['has_children'] = False
        
        # Verifica se o tipo é Cartão de Crédito (normalização robusta)
        tipo = str(tx.get('tipo', '') or '').upper()
        
        # Procura por CART e CREDIT/CREDIT para ser resiliente a acentos (CARTÃO, CRÉDITO)
        is_cartao = 'CART' in tipo and ('CREDIT' in tipo or 'CREDIT' in tipo.replace('É','E'))
        
        if is_cartao:
            # Busca associação (explícita ou tenta fallback automático se preferir, 
            # mas conforme solicitado, vamos focar na associação ou padrão)
            ano_f, mes_f = None, None
            if tx['id'] in assoc_map:
                ano_f, mes_f = assoc_map[tx['id']]
            else:
                # Fallback automático: mês anterior (opcional, mas ajuda se o usuário ainda não associou tudo)
                ano_f, mes_f = mes_anterior(tx['data'][:4], tx['data'][5:7])

            if ano_f and mes_f:
                conn_c = get_db_connection()
                # Busca despesas cujo arquivo de origem tenha vencimento no mês/ano associado
                query_c = """
                    SELECT dc.id, dc.data, dc.descricao, dc.categoria, dc.tipo, -dc.valor as valor 
                    FROM despesas_cartao dc
                    JOIN totais_fatura_cartao tfc ON dc.fonte_arquivo = tfc.fonte_arquivo
                    WHERE strftime('%Y', tfc.vencimento) = ? AND strftime('%m', tfc.vencimento) = ?
                    ORDER BY dc.data ASC
                """
                df_c = pd.read_sql_query(query_c, conn_c, params=[ano_f, mes_f.zfill(2)])
                conn_c.close()
                
                if not df_c.empty:
                    tx['children'] = df_c.to_dict(orient='records')
                    tx['has_children'] = True
                    tx['is_fatura'] = True

    # O anterior já inicializa children e has_children para todas as transações

    return jsonify({
        'data': bank_txs,
        'saldos': {
            'saldo_inicial': saldo_inicial,
            'saldo_final': saldo_final
        }
    })



@app.route('/api/gastos_por_categoria')
def gastos_por_categoria():
    """Fornece dados de gastos agregados por categoria."""
    from flask import request
    mes = request.args.get('mes')
    ano = request.args.get('ano')
    origem = request.args.get('origem')
    
    conn = get_db_connection()
    query = """
        WITH todas_movimentacoes AS (
            SELECT data, descricao, valor, categoria, 'Extrato Bancário' as origem FROM movimentacoes_bancarias
            UNION ALL
            SELECT data, descricao, -valor, categoria, 'Cartão de Crédito' as origem FROM despesas_cartao
        )
        SELECT categoria, tipo, SUM(valor) as total
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
    if origem:
        query += " AND origem = ?"
        params.append(origem)
        
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

    origem = request.args.get('origem')

    conn = get_db_connection()
    query = """
        WITH todas_movimentacoes AS (
            SELECT data, descricao, categoria, tipo, valor, 'Extrato Bancário' as origem FROM movimentacoes_bancarias
            UNION ALL
            SELECT data, descricao, categoria, tipo, -valor as valor, 'Cartão de Crédito' as origem FROM despesas_cartao
        )
        SELECT data, descricao, categoria, tipo, origem, printf('%.2f', valor) as valor
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
    if origem:
        query += " AND origem = ?"
        params.append(origem)
        
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
    origem = request.args.get('origem')
    
    conn = get_db_connection()
    query = """
        WITH todas_movimentacoes AS (
            SELECT data, descricao, valor, categoria, tipo, 'Extrato Bancário' as origem FROM movimentacoes_bancarias
            UNION ALL
            SELECT data, descricao, -valor as valor, categoria, tipo, 'Cartão de Crédito' as origem FROM despesas_cartao
        )
        SELECT 
            strftime('%Y-%m', data) as mes,
            categoria,
            tipo,
            SUM(valor) as total
        FROM todas_movimentacoes
        WHERE categoria IS NOT NULL
    """
    params = []
    if ano:
        query += " AND strftime('%Y', data) = ?"
        params.append(ano)
    if origem:
        query += " AND origem = ?"
        params.append(origem)
        
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
    origem = request.args.get('origem')
    
    conn = get_db_connection()
    query = """
        WITH todas_movimentacoes AS (
            SELECT data, descricao, valor, categoria, tipo, 'Extrato Bancário' as origem FROM movimentacoes_bancarias
            UNION ALL
            SELECT data, descricao, -valor as valor, categoria, tipo, 'Cartão de Crédito' as origem FROM despesas_cartao
        )
        SELECT categoria, tipo, SUM(valor) as total 
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
    if origem:
        query += " AND origem = ?"
        params.append(origem)
        
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

    tipo_filtro = request.args.get('tipo')
    sort_by = request.args.get('sort', 'data')
    order = request.args.get('order', 'desc').upper()

    # Mapeamento de colunas permitidas e seus nomes reais no DB/CTE
    allowed_columns = {
        'data': 'data',
        'descricao': 'descricao',
        'categoria': 'categoria',
        'tipo': 'tipo',
        'origem': 'origem',
        'valor': 'valor'
    }

    if sort_by not in allowed_columns:
        sort_by = 'data'
    if order not in ['ASC', 'DESC']:
        order = 'DESC'

    sort_column = allowed_columns[sort_by]

    conn = get_db_connection()
    
    base_query = """
        WITH todas_movimentacoes AS (
            SELECT id, data, descricao, categoria, tipo, valor, 'Extrato Bancário' as origem FROM movimentacoes_bancarias
            UNION ALL
            SELECT id, data, descricao, categoria, tipo, -valor as valor, 'Cartão de Crédito' as origem FROM despesas_cartao
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
    if tipo_filtro:
        base_query += " AND tipo = ?"
        params.append(tipo_filtro)
    if origem:
        base_query += " AND origem = ?"
        params.append(origem)

    # Conta o total de registros com os filtros aplicados
    count_query = f"SELECT COUNT(*) as total FROM ({base_query})"
    total_records = conn.execute(count_query, params).fetchone()['total']
    
    # Aplica ordenação e paginação
    data_query = base_query + f" ORDER BY {sort_column} {order} LIMIT ? OFFSET ?"
    params.extend([int(limit), int(offset)])
    
    df = pd.read_sql_query(data_query, conn, params=params)
    
    # Carregar regras existentes para sugestão
    try:
        regras_df = pd.read_sql_query("SELECT descricao, categoria, tipo FROM regras_usuario", conn)
        regras_dict = {}
        for _, r in regras_df.iterrows():
            regras_dict[str(r['descricao']).upper()] = {
                'categoria': r['categoria'],
                'tipo': r['tipo']
            }
    except Exception:
        regras_dict = {}

    conn.close()

    records = df.to_dict(orient='records')

    # Motor simples de sugestões para itens TBD
    for row in records:
        if row.get('categoria') == 'TBD' or not row.get('categoria'):
            desc = str(row.get('descricao', '')).upper()
            row['sugestao'] = None
            
            # 1. Substring matching
            for regra_desc, regra_data in regras_dict.items():
                if regra_desc in desc or desc in regra_desc:
                    row['sugestao'] = regra_data['categoria']
                    row['sugestao_tipo'] = regra_data['tipo']
                    break
            
            # 2. Primeira palavra matching (se não achou)
            if not row.get('sugestao'):
                primeira_palavra = desc.split()[0] if desc else ''
                if len(primeira_palavra) > 3:
                    for regra_desc, regra_data in regras_dict.items():
                        if primeira_palavra in regra_desc:
                            row['sugestao'] = regra_data['categoria']
                            row['sugestao_tipo'] = regra_data['tipo']
                            break

    return jsonify({
        'data': records,
        'total': total_records,
        'page': page,
        'limit': limit,
        'total_pages': (total_records + limit - 1) // limit
    })


@app.route('/api/consulta_direta')
def api_consulta_direta():
    """Retorna todos os registros e colunas de uma origem para um mês específico."""
    from flask import request
    mes = request.args.get('mes')
    ano = request.args.get('ano')
    origem = request.args.get('origem')  # 'Extrato Bancário' ou 'Cartão de Crédito'

    if not mes or not ano or not origem:
        return jsonify({"error": "Mês, ano e origem são obrigatórios"}), 400

    conn = get_db_connection()
    
    data_inicio = f"{ano}-{mes}-01"
    data_fim = f"{ano}-{mes}-31"

    if origem == 'Extrato Bancário':
        query = "SELECT * FROM movimentacoes_bancarias WHERE data >= ? AND data <= ? ORDER BY data ASC"
        df = pd.read_sql_query(query, conn, params=[data_inicio, data_fim])
        
        # Buscar saldos
        row_saldos = conn.execute("SELECT saldo_inicial, saldo_final FROM saldos_mes WHERE ano = ? AND mes = ?", (ano, mes)).fetchone()
        saldos = {
            'saldo_inicial': row_saldos['saldo_inicial'] if row_saldos else None,
            'saldo_final': row_saldos['saldo_final'] if row_saldos else None
        }
    else:
        query = "SELECT * FROM despesas_cartao WHERE data >= ? AND data <= ? ORDER BY data ASC"
        df = pd.read_sql_query(query, conn, params=[data_inicio, data_fim])
        saldos = None

    conn.close()
    
    return jsonify({
        'data': df.to_dict(orient='records'),
        'saldos': saldos
    })


if __name__ == '__main__':
    app.run(debug=True)
