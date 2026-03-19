import sqlite3
import pandas as pd
import re
from database import get_db_connection

def normalize(text):
    """Remove caracteres não alfanuméricos e converte para maiúsculas."""
    if not text: return ""
    return re.sub(r'[^A-Z0-9]', '', str(text).upper())

def extract_keywords(text):
    """Extrai palavras grandes que provavelmente são nomes de estabelecimentos."""
    # Remove barulhos comuns de bancos antes de tokenizar
    desc = str(text).upper()
    noise = ['COMPRACARTAODEBMC', 'INTERNET BANKING', 'PIX ENVIADO', 'PIX RECEBIDO', 'PAGAMENTO DE BOLETO']
    for n in noise:
        desc = desc.replace(n, ' ')
    
    tokens = re.findall(r'[A-Z]{3,}', desc)
    return [t for t in tokens if t not in ['DE', 'DO', 'DA', 'LTDA', 'SA', 'COM', 'CIA', 'BR', 'BANCO', 'SANTANDER']]

def classificar_automatico():
    """Aplica as regras_usuario a todas as transações não classificadas usando lógica robusta."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Carregar regras do usuário
    try:
        regras_df = pd.read_sql_query("SELECT descricao, categoria, tipo FROM regras_usuario", conn)
        regras_list = []
        for _, row in regras_df.iterrows():
            desc = row['descricao'].upper()
            regras_list.append({
                'original': desc,
                'normalized': normalize(desc),
                'keywords': extract_keywords(desc),
                'tipo': row['tipo'],
                'categoria': row['categoria']
            })
        print(f"Carregadas {len(regras_list)} regras do usuário.")
    except Exception as e:
        print(f"Erro ao carregar regras: {e}")
        regras_list = []

    if not regras_list:
        conn.close()
        return

    # 2. Carregar mapeamento tipo -> categoria
    try:
        mapeamento_df = pd.read_sql_query("SELECT tipo, categoria FROM categoria_tipo", conn)
        mapeamento = {row['tipo']: row['categoria'] for _, row in mapeamento_df.iterrows()}
    except Exception as e:
        print(f"Erro ao carregar mapeamento tipo-categoria: {e}")
        mapeamento = {}

    tabelas = ['movimentacoes_bancarias', 'despesas_cartao']
    total_atualizado = 0

    for tabela in tabelas:
        query = f"SELECT id, descricao FROM {tabela} WHERE (categoria IS NULL OR categoria = 'TBD' OR tipo IS NULL OR tipo = 'TBD')"
        df = pd.read_sql_query(query, conn)

        if df.empty:
            print(f"Nenhuma transação pendente em {tabela}.")
            continue

        print(f"Analisando {len(df)} transações em {tabela}...")
        
        atualizados = 0
        for _, tx in df.iterrows():
            desc_orig = str(tx['descricao']).upper()
            desc_norm = normalize(desc_orig)
            desc_keywords = extract_keywords(desc_orig)
            
            tipo_encontrado = None
            cat_encontrada = None
            
            # PASS 1: Match exato ou substring direta (já normalizado)
            for regra in regras_list:
                if regra['normalized'] == desc_norm or \
                   regra['normalized'] in desc_norm or \
                   desc_norm in regra['normalized']:
                    tipo_encontrado = regra['tipo']
                    cat_encontrada = regra['categoria']
                    break
            
            # PASS 2: Match por palavras-chave (se não achou no PASS 1)
            if not tipo_encontrado and desc_keywords:
                for regra in regras_list:
                    if any(kw in desc_keywords for kw in regra['keywords']) and len(regra['keywords']) > 0:
                        # Para evitar falsos positivos, pedimos que a palavra-chave tenha > 3 letras
                        # ou que o match seja mais específico (por agora, simplificamos)
                        tipo_encontrado = regra['tipo']
                        cat_encontrada = regra['categoria']
                        break
            
            # PASS 3: Fuzzy matches hardcoded for common entities (if still not found)
            if not tipo_encontrado:
                common_matches = {
                    'ENEL': ('Energia elétrica', 'Serviços domésticos'),
                    'NETSERVICOS': ('Internet / telefone fixo', 'Serviços domésticos'),
                    'CLARO': ('Celular', 'Serviços domésticos'),
                    'BRCONSORCIOS': ('Consórcio', 'Moradia'),
                    'SABESP': ('Água e esgoto', 'Serviços domésticos'),
                    'UBER': ('Táxi / Uber', 'Transporte'),
                    'IFOOD': ('Delivery / iFood', 'Alimentação'),
                    'REMNER': ('Roupas adulto', 'Vestuário'),
                }
                for key, (tipo, cat) in common_matches.items():
                    if key in desc_orig:
                        tipo_encontrado = tipo
                        cat_encontrada = cat
                        break
            
            if tipo_encontrado:
                cat_final = mapeamento.get(tipo_encontrado, cat_encontrada)
                cursor.execute(
                    f"UPDATE {tabela} SET tipo = ?, categoria = ? WHERE id = ?",
                    (tipo_encontrado, cat_final, tx['id'])
                )
                atualizados += 1

        conn.commit()
        print(f"{atualizados} transações classificadas em {tabela}.")
        total_atualizado += atualizados

    conn.close()
    print(f"Processo concluído. Total de {total_atualizado} transações classificadas automaticamente.")

if __name__ == "__main__":
    classificar_automatico()
