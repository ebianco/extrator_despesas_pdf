document.addEventListener('DOMContentLoaded', () => {
    const startMonthFilter = document.getElementById('startMonthFilter');
    const endMonthFilter = document.getElementById('endMonthFilter');
    const tableLoader = document.getElementById('tableLoader');
    const fluxoTable = document.getElementById('fluxoTable');
    const fluxoTbody = document.getElementById('fluxoTbody');

    // Popular meses dinamicamente
    function populateMonths() {
        const months = [
            "01", "02", "03", "04", "05", "06", 
            "07", "08", "09", "10", "11", "12"
        ];
        const currentYear = new Date().getFullYear();
        let optionsHtml = '';
        
        // Simples loop para anos recentes
        for (let year = currentYear; year >= currentYear - 2; year--) {
            for (let i = 11; i >= 0; i--) {
                const mes = months[i];
                const label = `${mes}/${year}`;
                const value = `${year}-${mes}`;
                optionsHtml += `<option value="${value}">${label}</option>`;
            }
        }
        
        startMonthFilter.innerHTML = optionsHtml;
        endMonthFilter.innerHTML = optionsHtml;
        
        // Setup inicial: Mês atual em ambos
        const currentMonthVal = `${currentYear}-${months[new Date().getMonth()]}`;
        startMonthFilter.value = currentMonthVal;
        endMonthFilter.value = currentMonthVal;
    }

    populateMonths();

    function formatCurrency(value) {
        return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value);
    }

    function formatDate(dateString) {
        if (!dateString) return '';
        const parts = dateString.split('-');
        if (parts.length === 3) {
            return `${parts[2]}/${parts[1]}/${parts[0]}`; // DD/MM/YYYY
        }
        return dateString;
    }

    async function loadFluxo() {
        tableLoader.style.display = 'block';
        fluxoTable.style.display = 'none';
        
        let url = '/api/fluxo_financeiro';
        const startVal = startMonthFilter.value;
        const endVal = endMonthFilter.value;
        
        if (startVal && endVal) {
            const [anoIni, mesIni] = startVal.split('-');
            const [anoFim, mesFim] = endVal.split('-');
            url += `?ano_inicio=${anoIni}&mes_inicio=${mesIni}&ano_fim=${anoFim}&mes_fim=${mesFim}`;
        }

        try {
            const response = await fetch(url);
            const data = await response.json();
            renderSummary(data.data, data.saldos);
            renderTable(data.data, data.saldos);
        } catch (error) {
            console.error('Erro ao carregar fluxo financeiro', error);
        } finally {
            tableLoader.style.display = 'none';
            fluxoTable.style.display = 'table';
        }
    }

    const summaryCards = document.getElementById('summaryCards');
    const breakdownPanel = document.getElementById('breakdownPanel');
    const breakdownTitle = document.getElementById('breakdownTitle');
    const breakdownContent = document.getElementById('breakdownContent');

    let creditsByCategory = {};
    let debitsByCategory = {};

    function renderSummary(transactions, saldos) {
        if (!transactions || (transactions.length === 0 && (!saldos || saldos.saldo_inicial === null))) {
            summaryCards.style.display = 'none';
            breakdownPanel.style.display = 'none';
            return;
        }

        summaryCards.style.display = 'grid'; 
        breakdownPanel.style.display = 'none';
        
        let totalCredits = 0;
        let totalDebits = 0;
        creditsByCategory = {};
        debitsByCategory = {};

        transactions.forEach(tx => {
            if (tx.valor > 0) {
                totalCredits += tx.valor;
                const cat = tx.categoria || 'Sem Categoria';
                creditsByCategory[cat] = (creditsByCategory[cat] || 0) + tx.valor;
            } else if (tx.valor < 0) {
                if (tx.has_children && tx.children && tx.children.length > 0) {
                    let childrenSum = 0;
                    tx.children.forEach(child => {
                        const childVal = child.valor;
                        if (childVal < 0) {
                            childrenSum += childVal;
                            const cat = child.categoria || 'Sem Categoria';
                            debitsByCategory[cat] = (debitsByCategory[cat] || 0) + Math.abs(childVal);
                        } else if (childVal > 0) {
                            const cat = child.categoria || 'Sem Categoria';
                            creditsByCategory[cat] = (creditsByCategory[cat] || 0) + childVal;
                            totalCredits += childVal;
                        }
                    });
                    totalDebits += Math.abs(tx.valor);
                    const diff = Math.abs(tx.valor) - Math.abs(childrenSum);
                    if (Math.abs(diff) > 0.01) {
                         debitsByCategory['Outros/Ajuste Fatura'] = (debitsByCategory['Outros/Ajuste Fatura'] || 0) + diff;
                    }
                } else {
                    totalDebits += Math.abs(tx.valor);
                    const cat = tx.categoria || 'Sem Categoria';
                    debitsByCategory[cat] = (debitsByCategory[cat] || 0) + Math.abs(tx.valor);
                }
            }
        });

        const saldoInicial = (saldos && typeof saldos.saldo_inicial === 'number') ? saldos.saldo_inicial : 0;
        const saldoFinalDB = (saldos && typeof saldos.saldo_final === 'number') ? saldos.saldo_final : null;
        
        // Cálculo de conferência: Saldo Inicial + Créditos - Débitos
        const saldoCalculado = saldoInicial + totalCredits - totalDebits;
        
        // Diferença aceitável para erros de arredondamento (ex: 0.01)
        const temDiscrepancia = saldoFinalDB !== null && Math.abs(saldoCalculado - saldoFinalDB) > 0.01;
        const saldoFinalMissing = saldoFinalDB === null;

        document.getElementById('sumSaldoInicial').innerText = formatCurrency(saldoInicial);
        document.getElementById('sumSaldoInicial').className = saldoInicial < 0 ? 'val-negative' : 'val-positive';

        document.getElementById('sumCreditos').innerText = formatCurrency(totalCredits);
        document.getElementById('sumDebitos').innerText = formatCurrency(totalDebits);

        const sumSaldoFinalEl = document.getElementById('sumSaldoFinal');
        if (saldoFinalMissing) {
            sumSaldoFinalEl.innerText = "N/A (Faltando no DB)";
            sumSaldoFinalEl.style.color = "var(--text-secondary)";
            sumSaldoFinalEl.title = `Valor calculado seria: ${formatCurrency(saldoCalculado)}`;
        } else {
            sumSaldoFinalEl.innerText = formatCurrency(saldoFinalDB);
            if (temDiscrepancia) {
                sumSaldoFinalEl.innerHTML = `${formatCurrency(saldoFinalDB)} <i class="fa-solid fa-triangle-exclamation" title="Discrepância detectada! O saldo conciliado deveria ser ${formatCurrency(saldoCalculado)}"></i>`;
                sumSaldoFinalEl.style.color = "var(--danger-color)";
                sumSaldoFinalEl.classList.add('val-negative');
            } else {
                sumSaldoFinalEl.style.color = saldoFinalDB < 0 ? 'var(--danger-color)' : 'var(--success-color)';
                sumSaldoFinalEl.className = saldoFinalDB < 0 ? 'val-negative' : 'val-positive';
            }
        }
    }


    function showBreakdown(type) {
        breakdownPanel.style.display = 'block';
        breakdownContent.innerHTML = '';
        
        let dataMap = type === 'creditos' ? creditsByCategory : debitsByCategory;
        let title = type === 'creditos' ? 'Composição de Créditos' : 'Composição de Débitos';
        let colorClass = type === 'creditos' ? 'success' : 'danger';
        
        breakdownTitle.innerText = title;
        
        let sortedKeys = Object.keys(dataMap).sort((a, b) => dataMap[b] - dataMap[a]);
        
        if (sortedKeys.length === 0) {
            breakdownContent.innerHTML = '<div style="color: var(--text-secondary); font-size: 12px;">Nenhuma categoria para exibir.</div>';
            return;
        }

        sortedKeys.forEach(cat => {
            const val = dataMap[cat];
            const div = document.createElement('div');
            div.style.padding = '8px 12px';
            div.style.background = 'var(--bg-surface)';
            div.style.borderRadius = '4px';
            div.style.borderLeft = `3px solid var(--${colorClass}-color)`;
            
            div.innerHTML = `
                <div style="font-size: 11px; color: var(--text-secondary); text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">${cat}</div>
                <div style="font-size: 14px; font-weight: 500; color: var(--text-primary); margin-top: 2px;">${formatCurrency(val)}</div>
            `;
            breakdownContent.appendChild(div);
        });
    }

    document.getElementById('cardCreditos').addEventListener('click', () => showBreakdown('creditos'));
    document.getElementById('cardDebitos').addEventListener('click', () => showBreakdown('debitos'));

    function renderTable(transactions, saldos) {
        fluxoTbody.innerHTML = '';
        
        if (!transactions || (transactions.length === 0 && (!saldos || saldos.saldo_inicial === null))) {
            fluxoTbody.innerHTML = '<tr><td colspan="6" style="text-align:center;">Nenhuma transação encontrada para este período.</td></tr>';
            return;
        }

        // Renderiza Saldo Inicial
        if (saldos && typeof saldos.saldo_inicial === 'number') {
            const trSaldo = document.createElement('tr');
            trSaldo.style.backgroundColor = 'rgba(13, 138, 188, 0.1)';
            trSaldo.style.fontWeight = 'bold';
            
            const isNegative = saldos.saldo_inicial < 0;
            const valClass = isNegative ? 'val-negative' : 'val-positive';
            
            trSaldo.innerHTML = `
                <td></td>
                <td></td>
                <td><i class="fa-solid fa-piggy-bank"></i> Saldo Inicial do Período</td>
                <td></td>
                <td></td>
                <td style="text-align: right;" class="${valClass}">${formatCurrency(saldos.saldo_inicial)}</td>
            `;
            fluxoTbody.appendChild(trSaldo);
        }

        let parentIdCounter = 0;

        transactions.forEach(tx => {
            parentIdCounter++;
            const parentId = `parent-${parentIdCounter}`;
            
            const tr = document.createElement('tr');
            
            // Valor: Se positivo (renda/credito) verde, se negativo vermelho
            const isNegative = tx.valor < 0; 
            const valClass = isNegative ? 'val-negative' : 'val-positive';
            
            let expandIcon = '<span class="expand-icon" style="width:24px;"></span>'; // placeholder
            
            if (tx.has_children && tx.children && tx.children.length > 0) {
                expandIcon = `<span class="expand-icon"><i class="fa-solid fa-plus"></i><i class="fa-solid fa-minus" style="display:none;"></i></span> `;
                tr.className = 'row-parent collapsed clickable';
                tr.dataset.target = parentId;
                
                tr.addEventListener('click', function() {
                    const isCollapsed = this.classList.contains('collapsed');
                    
                    if (isCollapsed) {
                        this.classList.remove('collapsed');
                        this.classList.add('expanded');
                    } else {
                        this.classList.remove('expanded');
                        this.classList.add('collapsed');
                    }
                    
                    const children = document.querySelectorAll(`.${this.dataset.target}`);
                    children.forEach(child => {
                        child.style.display = isCollapsed ? 'table-row' : 'none';
                    });
                });
            } else {
                tr.className = 'row-parent';
            }

            let originTag = '<span class="badge" style="background:#0D8ABC; font-size:10px; margin-left:8px;">Banco</span>';
            if (tx.is_virtual) {
                originTag = '<span class="badge" style="background:#4b5563; font-size:10px; margin-left:8px;">Virtual</span>';
            }

            tr.innerHTML = `
                <td style="color: var(--text-secondary); font-size: 11px;">${tx.id || '-'}</td>
                <td>${formatDate(tx.data)}</td>
                <td>${expandIcon}${tx.descricao} ${tx.is_fatura ? originTag + '<span class="badge" style="background:var(--purple); font-size:10px; margin-left:4px;">Pai da Fatura</span>' : originTag}</td>
                <td><span class="category-badge">${tx.categoria || 'Sem Categoria'}</span></td>
                <td><span style="font-size: 13px; color: var(--text-secondary);">${tx.tipo || '-'}</span></td>
                <td style="text-align: right;" class="${valClass}">${formatCurrency(tx.valor)}</td>
            `;
            fluxoTbody.appendChild(tr);

            if (tx.has_children && tx.children) {
                tx.children.forEach(child => {
                    const childTr = document.createElement('tr');
                    childTr.className = `row-child ${parentId}`;
                    
                    const cIsNegative = child.valor < 0;
                    const cValClass = cIsNegative ? 'val-negative' : 'val-positive';

                    childTr.innerHTML = `
                        <td style="color: var(--text-secondary); font-size: 11px; padding-left: 20px;">${child.id || '-'}</td>
                        <td>${formatDate(child.data)}</td>
                        <td>↳ ${child.descricao}</td>
                        <td><span class="category-badge">${child.categoria || 'Sem Categoria'}</span></td>
                        <td><span style="font-size: 13px; color: var(--text-secondary);">${child.tipo || '-'}</span></td>
                        <td style="text-align: right;" class="${cValClass}">${formatCurrency(child.valor)}</td>
                    `;
                    fluxoTbody.appendChild(childTr);
                });
            }
        });

        // Renderiza Saldo Final
        if (saldos && typeof saldos.saldo_final === 'number') {
            const trSaldoF = document.createElement('tr');
            trSaldoF.style.backgroundColor = 'rgba(13, 138, 188, 0.1)';
            trSaldoF.style.fontWeight = 'bold';
            trSaldoF.style.borderTop = '2px solid var(--accent-primary)';
            
            const isNegative = saldos.saldo_final < 0;
            const valClass = isNegative ? 'val-negative' : 'val-positive';
            
            trSaldoF.innerHTML = `
                <td></td>
                <td></td>
                <td><i class="fa-solid fa-piggy-bank"></i> Saldo Final do Período</td>
                <td></td>
                <td></td>
                <td style="text-align: right;" class="${valClass}">${formatCurrency(saldos.saldo_final)}</td>
            `;
            fluxoTbody.appendChild(trSaldoF);
        }
    }

    startMonthFilter.addEventListener('change', loadFluxo);
    endMonthFilter.addEventListener('change', loadFluxo);

    // Initial load
    loadFluxo();
});
