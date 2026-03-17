# Extrator de Despesas de Fatura de Cartão de Crédito

Este projeto contém um script Python para extrair automaticamente os dados de gastos de uma fatura de cartão de crédito em formato PDF e organizá-los em uma planilha (CSV ou Excel) para fácil análise.

## Como Usar

1. Coloque seus arquivos de fatura em PDF na pasta `faturas`.
2. Execute o script principal:
   ```bash
   python main.py
   ```
3. O script irá processar todos os PDFs da pasta `faturas`.
4. Ao final, os arquivos processados serão movidos automaticamente para a pasta `faturas_processadas`.
5. A planilha consolidada com todas as despesas será salva em `planilhas/despesas_consolidadas.csv`.
