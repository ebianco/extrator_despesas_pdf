document.addEventListener('DOMContentLoaded', function() {
    let currentMonth = '';
    let currentYear = '';
    let currentOrigem = 'Extrato Bancário';

    const monthFilter = document.getElementById('monthFilter');
    const origemFilter = document.getElementById('origemFilter');
    const btnConsultar = document.getElementById('btnConsultar');
    const loader = document.getElementById('loader');
    const saldosCard = document.getElementById('saldosCard');
    const recordsCount = document.getElementById('recordCount');

    function showLoader() { loader.style.display = 'block'; }
    function hideLoader() { loader.style.display = 'none'; }

    function populateMonthFilter() {
        fetch('/api/gastos_evolucao_tempo')
            .then(res => res.json())
            .then(data => {
                if(!data || data.length === 0) return;
                
                const mesesDisponiveis = [...new Set(data.map(item => item.mes))].sort().reverse();
                monthFilter.innerHTML = '';
                
                mesesDisponiveis.forEach((mes, index) => {
                    const opt = document.createElement('option');
                    opt.value = mes;
                    
                    const parts = mes.split('-');
                    const dateObj = new Date(parts[0], parts[1] - 1);
                    const monthName = dateObj.toLocaleString('pt-BR', { month: 'long' });
                    
                    opt.textContent = monthName.charAt(0).toUpperCase() + monthName.slice(1) + '/' + parts[0];
                    monthFilter.appendChild(opt);

                    // Seleciona o primeiro mês por padrão
                    if (index === 0) {
                        currentYear = parts[0];
                        currentMonth = parts[1];
                        consultarDB();
                    }
                });
            })
            .catch(err => console.error("Erro ao carregar meses do filtro:", err));
    }

    function formatCurrency(value) {
        if (value === null || value === undefined) return '-';
        return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value);
    }

    function consultarDB() {
        const val = monthFilter.value;
        if (val) {
            const parts = val.split('-');
            currentYear = parts[0];
            currentMonth = parts[1];
        }
        currentOrigem = origemFilter.value;

        showLoader();
        const url = `/api/consulta_direta?mes=${currentMonth}&ano=${currentYear}&origem=${encodeURIComponent(currentOrigem)}`;
        
        fetch(url)
            .then(res => res.json())
            .then(response => {
                hideLoader();
                renderTable(response.data);
                renderSaldos(response.saldos);
                recordsCount.textContent = `${response.data.length} registros`;
            })
            .catch(err => {
                hideLoader();
                console.error("Erro ao consultar DB:", err);
            });
    }

    function renderTable(data) {
        const tableHead = document.getElementById('tableHead');
        const tableBody = document.getElementById('tableBody');
        
        tableHead.innerHTML = '';
        tableBody.innerHTML = '';

        if (!data || data.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="10" style="text-align:center; padding: 20px;">Nenhum registro encontrado para este período.</td></tr>';
            return;
        }

        // Criar Header baseado nas chaves do primeiro objeto
        const columns = Object.keys(data[0]);
        const headerRow = document.createElement('tr');
        columns.forEach(col => {
            const th = document.createElement('th');
            th.textContent = col.charAt(0).toUpperCase() + col.slice(1).replace(/_/g, ' ');
            headerRow.appendChild(th);
        });
        tableHead.appendChild(headerRow);

        // Criar Body
        data.forEach(item => {
            const row = document.createElement('tr');
            columns.forEach(col => {
                const td = document.createElement('td');
                let value = item[col];
                
                // Formatações especiais
                if (col === 'valor') {
                     td.textContent = formatCurrency(value);
                     td.className = value < 0 ? 'val-negative' : 'val-positive';
                } else if (col === 'data') {
                    const d = value.split('-');
                    td.textContent = d.length === 3 ? `${d[2]}/${d[1]}/${d[0]}` : value;
                } else {
                    td.textContent = value !== null ? value : '-';
                }
                row.appendChild(td);
            });
            tableBody.appendChild(row);
        });
    }

    function renderSaldos(saldos) {
        if (currentOrigem === 'Extrato Bancário' && saldos) {
            saldosCard.style.display = 'block';
            document.getElementById('saldoInicial').textContent = formatCurrency(saldos.saldo_inicial);
            document.getElementById('saldoFinal').textContent = formatCurrency(saldos.saldo_final);
        } else {
            saldosCard.style.display = 'none';
        }
    }

    monthFilter.addEventListener('change', consultarDB);
    origemFilter.addEventListener('change', consultarDB);
    btnConsultar.addEventListener('click', consultarDB);

    populateMonthFilter();
});
