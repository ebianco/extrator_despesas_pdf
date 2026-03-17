document.addEventListener('DOMContentLoaded', function() {
    
    // Configurações de Estado
    let currentPage = 1;
    let currentLimit = 50;
    
    let currentSearch = '';
    let currentMonth = '';
    let currentYear = '';
    let currentCategoria = '';
    let currentOrigem = '';

    // Elementos DOM
    const tableBody = document.querySelector('#transacoesTable tbody');
    const tableEl = document.getElementById('transacoesTable');
    const loaderEl = document.getElementById('tableLoader');
    const paginationSection = document.getElementById('paginationSection');
    const paginationInfo = document.getElementById('paginationInfo');
    const btnPrev = document.getElementById('btnPrev');
    const btnNext = document.getElementById('btnNext');

    // Inicialização
    initFilterEvents();
    populateMonthFilter();
    fetchTransactions();

    function showLoader() {
        loaderEl.style.display = 'block';
        tableEl.style.opacity = '0.3';
        btnPrev.disabled = true;
        btnNext.disabled = true;
    }

    function hideLoader() {
        loaderEl.style.display = 'none';
        tableEl.style.display = 'table';
        tableEl.style.opacity = '1';
        paginationSection.style.display = 'flex';
    }

    function initFilterEvents() {
        // Busca com Debounce (aguarda o usuário parar de digitar)
        let timeout = null;
        document.getElementById('searchInput').addEventListener('input', function(e) {
            clearTimeout(timeout);
            timeout = setTimeout(() => {
                currentSearch = e.target.value;
                currentPage = 1; // Reseta para pág 1 ao buscar
                fetchTransactions();
            }, 500);
        });

        document.getElementById('categoriaFilter').addEventListener('change', function(e) {
            currentCategoria = e.target.value;
            currentPage = 1;
            fetchTransactions();
        });

        document.getElementById('origemFilter').addEventListener('change', function(e) {
            currentOrigem = e.target.value;
            currentPage = 1;
            fetchTransactions();
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
            currentPage = 1;
            fetchTransactions();
        });

        btnPrev.addEventListener('click', () => {
            if (currentPage > 1) {
                currentPage--;
                fetchTransactions();
            }
        });

        btnNext.addEventListener('click', () => {
            currentPage++;
            fetchTransactions();
        });
    }

    function getQueryParams() {
        const params = new URLSearchParams();
        params.append('page', currentPage);
        params.append('limit', currentLimit);
        
        if (currentSearch) params.append('search', currentSearch);
        if (currentYear) params.append('ano', currentYear);
        if (currentMonth) params.append('mes', currentMonth);
        if (currentCategoria) params.append('categoria', currentCategoria);
        if (currentOrigem) params.append('origem', currentOrigem);
        
        return params.toString();
    }

    function fetchTransactions() {
        showLoader();
        const url = '/api/transacoes?' + getQueryParams();
        
        fetch(url)
            .then(res => res.json())
            .then(response => {
                hideLoader();
                renderTable(response.data);
                updatePagination(response);
            })
            .catch(err => {
                console.error('Erro ao buscar transações:', err);
                hideLoader();
            });
    }

    function renderTable(data) {
        tableBody.innerHTML = '';
        
        if (data.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:#94a3b8; padding:30px;">Nenhuma transação encontrada com os filtros atuais.</td></tr>';
            return;
        }

        data.forEach(item => {
            let row = tableBody.insertRow();
            
            row.insertCell(0).textContent = formatDate(item.data);
            
            let descCell = row.insertCell(1);
            descCell.innerHTML = `<span style="font-weight:500; color:#f8fafc;">${item.descricao}</span>`;
            
            row.insertCell(2).innerHTML = getCategoryBadge(item.categoria);
            
            let origemCell = row.insertCell(3);
            let origemIcon = item.origem.includes('Cartão') ? '<i class="fa-regular fa-credit-card text-purple"></i>' : '<i class="fa-solid fa-building-columns text-cyan"></i>';
            origemCell.innerHTML = `<span style="display:flex; align-items:center; gap:8px; font-size:13px;">${origemIcon} ${item.origem}</span>`;
            
            let valCell = row.insertCell(4);
            const valorNum = parseFloat(item.valor);
            valCell.innerHTML = `<span class="${valorNum > 0 ? 'val-negative' : 'val-positive'}">${formatCurrency(Math.abs(valorNum))}</span>`;
        });
    }

    function updatePagination(response) {
        const { page, total, limit, total_pages } = response;
        
        const start = ((page - 1) * limit) + 1;
        let end = page * limit;
        if (end > total) end = total;
        
        if (total === 0) {
            paginationInfo.textContent = '0 resultados';
        } else {
            paginationInfo.textContent = `Mostrando ${start} a ${end} de ${total} transações`;
        }

        btnPrev.disabled = page <= 1;
        btnNext.disabled = page >= total_pages;
    }

    // --- Helpers (Mesmos do Dashboard) ---

    function populateMonthFilter() {
        fetch('/api/gastos_evolucao_tempo')
            .then(res => res.json())
            .then(data => {
                const filter = document.getElementById('monthFilter');
                if(!data || data.length === 0) return;
                
                const mesesDisponiveis = [...new Set(data.map(item => item.mes))].sort().reverse();
                
                mesesDisponiveis.forEach(mes => {
                    const opt = document.createElement('option');
                    opt.value = mes;
                    const parts = mes.split('-');
                    const dateObj = new Date(parts[0], parts[1] - 1);
                    const monthName = dateObj.toLocaleString('pt-BR', { month: 'long' });
                    opt.textContent = monthName.charAt(0).toUpperCase() + monthName.slice(1) + '/' + parts[0];
                    filter.appendChild(opt);
                });
            })
            .catch(err => console.error("Erro carrega meses:", err));
    }

    function formatCurrency(value) {
        return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value);
    }
    
    function formatDate(dateStr) {
        const parts = dateStr.split('-');
        if(parts.length === 3) {
            return `${parts[2]}/${parts[1]}/${parts[0]}`;
        }
        return dateStr;
    }

    function getCategoryBadge(categoria) {
        let badgeClass = 'badge-default';
        const cat = (categoria || 'TBD').toLowerCase();
        
        if (cat === 'tbd') return `<span class="badge" style="background-color: rgba(239, 68, 68, 0.15); color: var(--semantic-danger); border: 1px solid rgba(239, 68, 68, 0.3);">Pendente</span>`;
        
        if (cat.includes('refeição')) badgeClass = 'badge-ref';
        else if (cat.includes('transporte')) badgeClass = 'badge-trans';
        else if (cat.includes('saúde') || cat.includes('pessoais')) badgeClass = 'badge-saude';
        else if (cat.includes('lazer')) badgeClass = 'badge-lazer';
        
        return `<span class="badge ${badgeClass}">${categoria}</span>`;
    }
});
