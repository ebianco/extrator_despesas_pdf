import sqlite3
import os

DATABASE_FILE = 'despesas.db'

def run_migration():
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Carrega o mapeamento
    cursor.execute("SELECT categoria, tipo FROM categoria_tipo")
    mapeamento = {row['tipo']: row['categoria'] for row in cursor.fetchall()}

    tipos_validos = list(mapeamento.keys())

    print(f"Encontrados {len(tipos_validos)} tipos válidos no mapeamento.")

    # 2. Atualiza despesas_cartao
    cursor.execute("SELECT id, categoria, tipo FROM despesas_cartao WHERE tipo IS NOT NULL OR categoria IS NOT NULL")
    cartao_txs = cursor.fetchall()
    
    atualizados_cartao = 0
    zerados_cartao = 0

    for tx in cartao_txs:
        tipo = tx['tipo']
        
        if tipo in mapeamento:
            categoria_correta = mapeamento[tipo]
            if tx['categoria'] != categoria_correta:
                cursor.execute("UPDATE despesas_cartao SET categoria = ? WHERE id = ?", (categoria_correta, tx['id']))
                atualizados_cartao += 1
        else:
            # Tipo não está no mapeamento (ou está vazio), reseta para TBD
            cursor.execute("UPDATE despesas_cartao SET categoria = 'TBD', tipo = NULL WHERE id = ?", (tx['id'],))
            zerados_cartao += 1

    # 3. Atualiza movimentacoes_bancarias
    cursor.execute("SELECT id, categoria, tipo FROM movimentacoes_bancarias WHERE tipo IS NOT NULL OR categoria IS NOT NULL")
    banco_txs = cursor.fetchall()

    atualizados_banco = 0
    zerados_banco = 0

    for tx in banco_txs:
        tipo = tx['tipo']
        
        if tipo in mapeamento:
            categoria_correta = mapeamento[tipo]
            if tx['categoria'] != categoria_correta:
                cursor.execute("UPDATE movimentacoes_bancarias SET categoria = ? WHERE id = ?", (categoria_correta, tx['id']))
                atualizados_banco += 1
        else:
            # Tipo não está no mapeamento (ou está vazio), reseta para TBD
            cursor.execute("UPDATE movimentacoes_bancarias SET categoria = 'TBD', tipo = NULL WHERE id = ?", (tx['id'],))
            zerados_banco += 1

    # 4. Atualiza regras_usuario
    cursor.execute("SELECT descricao, categoria, tipo FROM regras_usuario")
    regras = cursor.fetchall()
    
    regras_atualizadas = 0
    regras_removidas = 0

    for regra in regras:
        tipo = regra['tipo']
        
        if tipo in mapeamento:
            categoria_correta = mapeamento[tipo]
            if regra['categoria'] != categoria_correta:
                cursor.execute("UPDATE regras_usuario SET categoria = ? WHERE descricao = ?", (categoria_correta, regra['descricao']))
                regras_atualizadas += 1
        else:
            # Regras antigas sem tipo válido: apagar a regra
            cursor.execute("DELETE FROM regras_usuario WHERE descricao = ?", (regra['descricao'],))
            regras_removidas += 1

    conn.commit()
    conn.close()

    print("--- Resultado da Migração ---")
    print(f"Cartão de Crédito: {atualizados_cartao} atualizados para nova categoria, {zerados_cartao} resetados para TBD.")
    print(f"Extrato Bancário: {atualizados_banco} atualizados para nova categoria, {zerados_banco} resetados para TBD.")
    print(f"Regras do Usuário: {regras_atualizadas} atualizadas, {regras_removidas} removidas por tipo inválido.")

if __name__ == '__main__':
    run_migration()
