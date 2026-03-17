import pandas as pd
from database import get_db_connection, create_tables

def classificar_despesa(descricao):
    descricao = descricao.upper()

    # Mapeamento de palavras-chave para Tipo
    mapa_tipo = {
        'MERCADO LIVRE': ['MERCADOLIVRE'],
        'RESTAURANTE': ['GULAGULA', 'GOLDENMORUMBI', 'OUTBACK', 'MCDONALDS', 'BURGER KING', 'DONPATTO', 'MADERO', 'BONGIORNO', 'BARBACOA', 'RODOSNACK', 'AMERICAMORUMBI', 'SONHOARABE', 'PAPAROTO', 'RESTAURANTEKHARINA', 'OPERETTA', 'ADMCOMDEALIMENTOSLT', 'GLOBALCHEFSADMINISTR', 'PRADOPONZINIRESTAURA', 'DAVVEROGELATOTRADIZI', 'PICANHARIAGAUCHALTDA', 'CASA RESTAURANTE', 'BACIODILATTE', 'BLACKRIVERCAFELTDA'],
        'PADARIA': ['PADARIA', 'BELLA PAULISTA', 'PUMILA', 'CONCRET*AFORNADAPADA', 'GRACAPAES', 'FLORDASAMERICASARTE', 'FLORDASAMERICASART'],
        'MERCADO': ['MINUTOPA', 'PAO DE ACUCAR', 'P@ODEACUCAR', 'CARREFOUR', 'SAMSCLUB', 'ORIGENSHORTIFRUTI', 'CHOCOLANDIA'],
        'AÇOUGUE': ['TBONEACOUGUES', 'NATUBRASIL', 'MINIEXTRA', 'SWIFT'],
        'IFOOD': ['IFD*', 'IFOOD'],
        'RAPPI': ['RAPPI'],
        'UBER': ['UBER'],
        'FARMÁCIA': ['DROGA', 'FARM', 'DROGASIL', 'DROGA RAIA', 'RAIA'],
        'POSTO DE GASOLINA': ['POSTO'],
        'CINEMA': ['CINEMARK', 'KINOPLEX'],
        'STREAMING': ['AMAZONPRIME', 'NETFLIX', 'YOUTUBEPREMIUM', 'SPOTIFY', 'HBOMAX'],
        'GAME': ['GOOGLEBRAWLSTARS', 'DL*GOOGLEBRAWL'],
        'CASA': ['LEROYMERLIN', 'TELHANORTE'],
        'VESTUÁRIO': ['LOJASRENNER', 'CENTAURO', 'CEAMRB140ECPC', 'IH46SPMORUMBI', 'VERDENCOMERCIODECAL', 'TIPTOPMORUMBI'],
        'BARBEARIA': ['TOMMYGUN'],
        'BELEZA': ['BRUNABEAUTY'],
        'SEM PARAR': ['SEMPARAR'],
        'ACADEMIA': ['WELLHUBGYM'],
        'PRESENTE': ['PBKIDSBRINQUEDOS', 'PBKIDBRINQUEDOS'],
        'NESPRESSO': ['NESTLEBRASIL', 'NESPRESSO'],
        'PET': ['PETLOVE', 'JCC04PETSTORELTDA'],
        'BAR': ['VIGGABAR'],
        'LAZER': ['POPHAUS'],
        'WINDSURF': ['WINDSURF']
    }

    # Mapeamento de Tipo para Categoria
    mapa_categoria = {
        'RESTAURANTE': 'Refeição',
        'PADARIA': 'Refeição',
        'MERCADO': 'Refeição',
        'AÇOUGUE': 'Refeição',
        'NESPRESSO': 'Refeição',
        'IFOOD': 'Refeição',
        'RAPPI': 'Refeição',
        'UBER': 'Transporte',
        'POSTO DE GASOLINA': 'Transporte',
        'SEM PARAR': 'Transporte',
        'FARMÁCIA': 'Saúde',
        'ACADEMIA': 'Saúde',
        'STREAMING': 'Lazer',
        'CINEMA': 'Lazer',
        'GAME': 'Lazer',
        'PRESENTE': 'Lazer',
        'BAR': 'Lazer',
        'LAZER': 'Lazer',
        'WINDSURF': 'Lazer',
        'CASA': 'Casa',
        'VESTUÁRIO': 'Vestuário',
        'BARBEARIA': 'Cuidados Pessoais',
        'BELEZA': 'Cuidados Pessoais',
        'PET': 'Pet',
        'MERCADO LIVRE': 'Bens de consumo'
    }

    tipo_encontrado = 'TBD'
    for tipo, keywords in mapa_tipo.items():
        if any(keyword in descricao for keyword in keywords):
            tipo_encontrado = tipo
            break

    categoria_encontrada = mapa_categoria.get(tipo_encontrado, 'TBD')

    return tipo_encontrado, categoria_encontrada

def analisar_e_atualizar_despesas():
    """Busca despesas não classificadas, aplica a classificação e atualiza o banco de dados."""
    create_tables()  # Garante que a tabela e as colunas existem
    conn = get_db_connection()
    # Busca apenas despesas que ainda não foram classificadas
    df = pd.read_sql_query("SELECT id, descricao FROM despesas_cartao WHERE tipo IS NULL OR tipo = 'TBD'", conn)

    if df.empty:
        print("Nenhuma despesa nova para analisar.")
        conn.close()
        return

    print(f"Analisando {len(df)} novas despesas...")
    # Aplica a função de classificação
    df[['tipo', 'categoria']] = df['descricao'].apply(lambda x: pd.Series(classificar_despesa(x)))

    cursor = conn.cursor()
    for index, row in df.iterrows():
        cursor.execute(
            "UPDATE despesas_cartao SET tipo = ?, categoria = ? WHERE id = ?",
            (row['tipo'], row['categoria'], row['id'])
        )
    
    conn.commit()
    conn.close()
    print(f"Análise concluída. {len(df)} registros foram atualizados no banco de dados.")

if __name__ == "__main__":
    analisar_e_atualizar_despesas()
