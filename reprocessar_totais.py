"""
reprocessar_totais.py
Script para extrair retroativamente o total declarado e vencimento dos PDFs de fatura
já processados (dentro de faturas_processadas/), preenchendo a tabela totais_fatura_cartao.
"""
import os
import pdfplumber
from despesas_cartao import extrair_total_e_vencimento, salvar_total_fatura

PROCESSADAS_DIR = 'faturas_processadas/'

def main():
    if not os.path.exists(PROCESSADAS_DIR):
        print(f"Diretório '{PROCESSADAS_DIR}' não encontrado.")
        return

    arquivos = [f for f in os.listdir(PROCESSADAS_DIR) if f.lower().endswith('.pdf')]
    if not arquivos:
        print("Nenhum PDF encontrado em faturas_processadas/.")
        return

    print(f"Reprocessando totais de {len(arquivos)} arquivos...\n")
    ok = 0
    sem_total = 0

    for nome in sorted(arquivos):
        caminho = os.path.join(PROCESSADAS_DIR, nome)
        try:
            with pdfplumber.open(caminho, password="08700599719") as pdf:
                texto = "".join(p.extract_text() for p in pdf.pages if p.extract_text())
            total_decl, vencimento = extrair_total_e_vencimento(texto, nome)
            salvar_total_fatura(nome, total_decl, vencimento)
            if total_decl:
                print(f"  ✓ {nome}: R$ {total_decl:,.2f} | venc: {vencimento}")
                ok += 1
            else:
                print(f"  ⚠ {nome}: total não encontrado (venc: {vencimento})")
                sem_total += 1
        except Exception as e:
            print(f"  ✗ {nome}: ERRO — {e}")

    print(f"\nConcluído: {ok} com total, {sem_total} sem total.")

if __name__ == '__main__':
    main()
