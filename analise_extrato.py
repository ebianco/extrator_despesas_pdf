import pandas as pd

def classificar_transacao(descricao):
    """Classifica uma transação em Tipo e Categoria com base na descrição."""
    desc = str(descricao).upper().replace(' ', '')

    # Regras de classificação: (Categoria, Tipo, [palavras_chave], [palavras_negativas])
    regras = [
        # --- RECEITAS ---
        ('Salário', 'Salário', ['ACCENTURE', 'CREDITODESALARIO', 'ADIANTAMENTODESALARIO'], []),
        ('Salário', 'Férias', ['CREDITODELIQUIDODEFERIAS'], []),
        ('Receita', 'Aluguel Recebido', ['QUINTOANDAR', 'RUMOSULIMOVEIS'], ['PAGAMENTO']),
        ('Receita', 'Restituição IR', ['RESTITUICAOIMPOSTORENDA'], []),
        ('Receita', 'Cashback', ['MELIUZ'], []),
        ('Investimento', 'Rendimento', ['REMUNERACAOAPLICACAOAUTOMATICA', 'BANCORENDIMENTO'], ['PAGAMENTO']),
        ('Investimento', 'Câmbio', ['OPERACAODECAMBIO'], []),
        ('Venda', 'Venda', ['WISEBRASILCORRETORADE'], []),
        ('Estorno', 'Estorno', ['ESTORNO', 'DEVOLUCAOCOMPRA'], []),

        # --- DESPESAS ---
        # Moradia
        ('Moradia', 'Financiamento CEF', ['PIXENVIADOEDUARDODELBIANCO'], []),
        ('Moradia', 'Condomínio', ['CONDOMINIOBROOKFIELDHOM'], []),
        ('Moradia', 'Aluguel', ['PAULINAMARIANACUNHABUC'], []),
        ('Moradia', 'Consórcio', ['BRCONSORCIOS', 'PAGAMENTODECONSORCIO'], []),
        ('Moradia', 'Conta de Luz', ['ELETROPAULOMETROPOLITANA', 'AESELETROPAULO', 'ENEL'], []),
        ('Moradia', 'SABESP Vazamento', ['SABESPSAOPAULO'], []),

        # Educação
        ('Educação', 'Colégio', ['JARDIMESCOLAMAGICODEO'], []),
        ('Educação', 'Educação Magno', ['INSTITUTOMAGNODEEDUCAC', 'CENTROINTEDUCESPMAGNO'], []),
        ('Educação', 'Escola Projeto Kids', ['ESCOLAPROJETOKIDS'], []),

        # Contas e Serviços
        ('Serviços', 'CLARO', ['NETSERVICOS'], []),
        ('Serviços', 'VIVO', ['TELEFONICABRASILSA'], []),
        ('Serviços', 'Conta de Telefone', ['PGTOCONTADETELEFONE', 'PAGAMENTOCONTACELULAR'], []),
        ('Contas', 'Pagamento de Boleto', ['PAGAMENTODETITULO', 'PAGAMENTODOCONVENIO', 'PAGAMENTODECONTA', 'PAGAMENTODECIP', 'PAGAMENTODECONCESSIONARIA'], []),
        ('Contas', 'Débito Automático', ['DEBITOAUTORIZADO'], []),
        ('Contas', 'Pagamento de Contas', ['PAGAMENTODECONTAS', 'PGTOBOLETO'], []),

        # Alimentação
        ('Alimentação', 'iFood', ['IFOOD'], []),

        # Transporte
        ('Transporte', 'Sem Parar', ['SEMPARAR'], []),


        # Cartão
        ('Cartão', 'Pagamento de Cartão', ['PAGAMENTODEBOLETO-BANCOSANTANDER(BRASIL)', 'PAGAMENTODOCARTAO'], []),

        # Compras
        ('Compras', 'Compra no Débito', ['COMPRACARTAODEBMC', 'COMPRACOMDEBITO'], []),
        ('Compras Online', 'AliExpress', ['ALIPAYALIEXPRESSPIX'], []),
        ('Compras Online', 'Shopee', ['SHPPBRASILINSTITUICAOD'], []),

        # Transporte
        ('Transporte', 'Uber', ['UBER'], []),
        ('Transporte', 'Lavagem', ['PIXENVIADOMAYKMOREIRAMACEDO'], []),

        # Outros
        ('Pensão', 'Pensão', ['TATIANASOARESDELBIANCO'], []),
        ('Pessoal', 'Transferência Pessoal', ['DENISDELBIANCO'], []),
        ('Transferência', 'PIX Enviado', ['PIXENVIADO'], ['JUAREZDUARTEDESOUZA', 'ALIPAYALIEXPRESSPIX', 'SHPPBRASILINSTITUICAOD']),
        ('Despesa Pessoal', 'Pagamento Salários', ['PAGAMENTODESALARIOS'], []),
        ('Mercado', 'Juarez', ['PIXENVIADOJUAREZDUARTEDESOUZA'], []),
        ('Pets', 'Pets', ['PETSUPERMARKETCOMERCIOD'], []),
        ('Saque', 'Saque', ['SAQUEDINHEIRO', 'SAQUEBANCO24HS'], []),
        ('Transferência', 'Transferência', ['TRANSFERENCIAENTRECONTAS', 'TRANSFERENCIAELETRONICA', 'TRANSFERENCIAPIX'], []),
        ('Seguros', 'Seguro', ['SEGUROPRESTAMISTA'], []),
        ('Impostos', 'IOF', ['IOF'], []),
        ('Impostos', 'Tributos', ['PGTRIBUTOS'], []),
        ('Juros', 'Juros', ['JUROSSALDOUTILIZADO'], []),
        ('Vale', 'Vale', ['JOSEDOMINGOSAFONSO'], []),
    ]

    for categoria, tipo, palavras_chave, palavras_negativas in regras:
        # Verifica se alguma palavra-chave negativa está na descrição
        if any(negativa in desc for negativa in palavras_negativas):
            continue
        
        # Verifica se alguma palavra-chave positiva está na descrição
        if any(chave in desc for chave in palavras_chave):
            return tipo, categoria

    return 'TBD', 'TBD'

from database import get_db_connection

def analisar_e_atualizar_movimentacoes():
    """Lê, classifica e atualiza as movimentações bancárias no banco de dados."""
    conn = get_db_connection()
    # Seleciona apenas registros que ainda não foram classificados
    df = pd.read_sql_query("SELECT * FROM movimentacoes_bancarias WHERE tipo IS NULL OR categoria IS NULL", conn)

    if df.empty:
        print("Nenhuma nova movimentação para analisar.")
        conn.close()
        return

    print(f"Analisando {len(df)} novas movimentações...")

    # Aplica a função de classificação
    classificacoes = df['descricao'].apply(lambda x: pd.Series(classificar_transacao(x)))
    df['tipo'] = classificacoes[0]
    df['categoria'] = classificacoes[1]

    # Atualiza os registros no banco de dados
    cursor = conn.cursor()
    for _, row in df.iterrows():
        cursor.execute(
            "UPDATE movimentacoes_bancarias SET tipo = ?, categoria = ? WHERE id = ?",
            (row['tipo'], row['categoria'], row['id'])
        )
    
    conn.commit()
    conn.close()
    print("Análise e atualização concluídas com sucesso!")

if __name__ == '__main__':
    analisar_e_atualizar_movimentacoes()
