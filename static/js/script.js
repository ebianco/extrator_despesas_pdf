document.addEventListener('DOMContentLoaded', function() {

    // Carrega a biblioteca do Google Charts
    google.charts.load('current', {'packages':['sankey', 'corechart', 'line']});
    google.charts.setOnLoadCallback(desenharGraficos);

    // Configurações Globais de Tema dos Gráficos Google
    const chartTheme = {
        backgroundColor: 'transparent',
        textStyle: { color: '#f8fafc', fontName: 'Outfit' },
        hAxis: {
            textStyle: { color: '#94a3b8' },
            gridlines: { color: 'rgba(255,255,255,0.05)' },
            baselineColor: 'rgba(255,255,255,0.1)'
        },
        vAxis: {
            textStyle: { color: '#94a3b8' },
            gridlines: { color: 'rgba(255,255,255,0.05)' },
            baselineColor: 'rgba(255,255,255,0.1)'
        },
        legend: { textStyle: { color: '#94a3b8' } },
        chartArea: { width: '85%', height: '75%' }
    };

    let currentMonth = '';
    let currentYear = '';
    let currentOrigem = '';

    function showLoader(id) { document.getElementById(id).style.display = 'block'; }
    function hideLoader(id) { document.getElementById(id).style.display = 'none'; }

    function desenharGraficos() {
        populateMonthFilter();
        updateDashboard();
        
        // Redraw on resize
        window.addEventListener('resize', () => {
             drawSankeyChart();
             drawEvolucaoChart();
        });

        document.getElementById('monthFilter').addEventListener('change', function(e) {
            const val = e.target.value;
            if (val) {
                const parts = val.split('-');
                currentYear = parts[0];
                currentMonth = parts[1];
            } else {
                currentYear = '';
                currentMonth = '';
            }
            updateDashboard();
        });

        document.getElementById('origemFilter').addEventListener('change', function(e) {
            currentOrigem = e.target.value;
            updateDashboard();
        });
    }

    function updateDashboard() {
        showLoader('loaderSankey');
        showLoader('loaderEvolucao');
        drawSankeyChart();
        drawEvolucaoChart();
        fetchDespesasRecentes();
    }

    function getQueryParams() {
        const params = new URLSearchParams();
        if (currentYear) params.append('ano', currentYear);
        if (currentMonth) params.append('mes', currentMonth);
        if (currentOrigem) params.append('origem', currentOrigem);
        return params.toString();
    }

    function populateMonthFilter() {
        // Aproveita o endpoint de evolução temporal (sem filtros) para descobrir quais meses existem
        fetch('/api/gastos_evolucao_tempo')
            .then(res => res.json())
            .then(data => {
                const filter = document.getElementById('monthFilter');
                if(!data || data.length === 0) return;
                
                const mesesDisponiveis = [...new Set(data.map(item => item.mes))].sort().reverse();
                
                // Mantém a opção "Todo o Período"
                filter.innerHTML = '<option value="">Todo o Período</option>';
                
                mesesDisponiveis.forEach(mes => {
                    const opt = document.createElement('option');
                    opt.value = mes;
                    
                    // Formata "2024-05" para "Maio/2024"
                    const parts = mes.split('-');
                    const dateObj = new Date(parts[0], parts[1] - 1);
                    const monthName = dateObj.toLocaleString('pt-BR', { month: 'long' });
                    
                    opt.textContent = monthName.charAt(0).toUpperCase() + monthName.slice(1) + '/' + parts[0];
                    filter.appendChild(opt);
                });
            })
            .catch(err => console.error("Erro ao carregar meses do filtro:", err));
    }

    function drawSankeyChart() {
        const query = getQueryParams();
        const url = query ? `/api/sankey_data?${query}` : '/api/sankey_data';
        fetch(url)
            .then(response => response.json())
            .then(data => {
                hideLoader('loaderSankey');
                if (!data || data.length === 0) {
                    document.getElementById('sankey_chart').innerHTML = '<p style="color:#94a3b8; text-align:center; padding-top:40px;">Sem dados suficientes para o gráfico de fluxo.</p>';
                    return;
                }

                var dataTable = new google.visualization.DataTable();
                dataTable.addColumn('string', 'De');
                dataTable.addColumn('string', 'Para');
                dataTable.addColumn('number', 'Valor');

                // Garante valores positivos no Sankey para não quebrar o gráfico Google
                // item[0]=fonte, item[1]=destino, item[2]=tipo, item[3]=valor
                const processedData = data.map(item => [item[0], item[1], Math.abs(item[3])]);
                dataTable.addRows(processedData);

                var colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4'];

                var options = {
                    backgroundColor: 'transparent',
                    height: 400,
                    sankey: {
                        node: {
                            label: { fontName: 'Outfit', fontSize: 13, color: '#f8fafc', bold: true },
                            nodePadding: 40,
                            colors: colors,
                            width: 8
                        },
                        link: { colorMode: 'gradient', color: { fill: '#334155', fillOpacity: 0.6 } }
                    }
                };

                var chart = new google.visualization.Sankey(document.getElementById('sankey_chart'));
                chart.draw(dataTable, options);
            })
            .catch(err => {
                 hideLoader('loaderSankey');
                 console.error("Erro no Sankey: ", err);
            });
    }

    function drawEvolucaoChart() {
        // Para a evolução, geralmente queremos ver a linha do tempo, mas se houver filtro de ano, enviamos o ano
        let url = '/api/gastos_evolucao_tempo';
        if (currentYear) {
             url += `?ano=${currentYear}`;
        }
        fetch(url)
        .then(response => response.json())
        .then(data => {
            hideLoader('loaderEvolucao');
            if (!data || data.length === 0) {
                document.getElementById('evolucaoChart').innerHTML = '<p style="color:#94a3b8; text-align:center; padding-top:40px;">Sem dados para exibir evolução.</p>';
                return;
            }

            // Pivot data for Google Charts
            const meses = [...new Set(data.map(item => item.mes))].sort();
            const categorias = [...new Set(data.map(item => item.categoria))];
            const dataArray = [['Mês', ...categorias]];

            meses.forEach(mes => {
                const row = [mes];
                categorias.forEach(categoria => {
                    const item = data.find(d => d.mes === mes && d.categoria === categoria);
                    row.push(item ? Math.abs(item.total) : 0);
                });
                dataArray.push(row);
            });

            var dataTable = google.visualization.arrayToDataTable(dataArray);

            var options = Object.assign({}, chartTheme, {
                curveType: 'function',
                legend: { position: 'top', alignment: 'end', textStyle: { color: '#94a3b8' } },
                height: 350,
                lineWidth: 3,
                colors: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#ec4899', '#14b8a6'],
                pointSize: 5
            });

            // Remove o gridline horizontal para dar visual mais limpo
            options.vAxis.gridlines.color = 'rgba(255,255,255,0.03)';
            options.hAxis.gridlines.color = 'transparent';

            var chart = new google.visualization.LineChart(document.getElementById('evolucaoChart'));
            chart.draw(dataTable, options);
        })
        .catch(err => {
             hideLoader('loaderEvolucao');
             console.error("Erro na Evolução: ", err);
        });
    }

    function formatCurrency(value) {
        return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value);
    }
    
    function formatDate(dateStr) {
        // Assume YYYY-MM-DD
        const parts = dateStr.split('-');
        if(parts.length === 3) {
            return `${parts[2]}/${parts[1]}/${parts[0]}`;
        }
        return dateStr;
    }

    function getCategoryBadge(categoria) {
        let badgeClass = 'badge-default';
        const cat = (categoria || 'TBD').toLowerCase();
        
        if (cat === 'tbd') {
             return `<span class="badge" style="background-color: rgba(239, 68, 68, 0.15); color: var(--semantic-danger); border: 1px solid rgba(239, 68, 68, 0.3);">Pendente</span>`;
        }
        
        if (cat.includes('refeição')) badgeClass = 'badge-ref';
        else if (cat.includes('transporte')) badgeClass = 'badge-trans';
        else if (cat.includes('saúde') || cat.includes('pessoais')) badgeClass = 'badge-saude';
        else if (cat.includes('lazer')) badgeClass = 'badge-lazer';
        
        return `<span class="badge ${badgeClass}">${categoria}</span>`;
    }

    function fetchDespesasRecentes() {
        const query = getQueryParams();
        const url = query ? `/api/despesas_recentes?${query}` : '/api/despesas_recentes';
        fetch(url)
        .then(response => response.json())
        .then(data => {
            const tableBody = document.querySelector('#despesasTable tbody');
            tableBody.innerHTML = ''; 
            
            if (data.length === 0) {
                tableBody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:#94a3b8;">Nenhuma despesa recente encontrada.</td></tr>';
                return;
            }

            data.forEach(item => {
                let row = tableBody.insertRow();
                
                // Data
                row.insertCell(0).textContent = formatDate(item.data);
                
                // Descrição com um bold sutil
                let descCell = row.insertCell(1);
                descCell.innerHTML = `<span style="font-weight:500; color:#f8fafc;">${item.descricao}</span>`;
                
                // Categoria (Badge)
                row.insertCell(2).innerHTML = getCategoryBadge(item.categoria);
                
                // Tipo
                let tipoCell = row.insertCell(3);
                tipoCell.innerHTML = `<span style="font-size:13px; color:#94a3b8;">${item.tipo || '-'}</span>`;
                
                // Origem (Cartão de Crédito ou Extrato Bancário)
                let origemCell = row.insertCell(4);
                let origemIcon = item.origem.includes('Cartão') ? '<i class="fa-regular fa-credit-card text-purple"></i>' : '<i class="fa-solid fa-building-columns text-cyan"></i>';
                origemCell.innerHTML = `<span style="display:flex; align-items:center; gap:8px; font-size:13px;">${origemIcon} ${item.origem}</span>`;
                
                // Valor
                let valCell = row.insertCell(5);
                const valorNum = parseFloat(item.valor);
                valCell.innerHTML = `<span class="${valorNum > 0 ? 'val-negative' : 'val-positive'}">${formatCurrency(Math.abs(valorNum))}</span>`;
            });
        });
    }
});