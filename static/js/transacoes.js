document.addEventListener('DOMContentLoaded', function() {
    
    // Configurações de Estado
    let currentPage = 1;
    let currentLimit = 50;
    
    let currentSearch = '';
    let currentMonth = '';
    let currentYear = '';
    let currentCategoria = '';
    let currentOrigem = '';
    let currentTipo = '';

    let currentSort = 'data';
    let currentOrder = 'desc';

    // Elementos DOM
    const tableBody = document.querySelector('#transacoesTable tbody');
    const tableEl = document.getElementById('transacoesTable');
    const loaderEl = document.getElementById('tableLoader');
    const paginationSection = document.getElementById('paginationSection');
    const paginationInfo = document.getElementById('paginationInfo');
    const btnPrev = document.getElementById('btnPrev');
    const btnNext = document.getElementById('btnNext');

    let categoriasTiposHtml = '<option value="">Tipo...</option>';

    // Inicialização
    initFilterEvents();
    populateMonthFilter();
    fetchCategoriasTipos().then(() => fetchTransactions());

    async function fetchCategoriasTipos() {
        try {
            const res = await fetch('/api/categorias_tipos');
            const data = await res.json();
            
            // Agrupar por categoria para o select com optgroup e coletar únicos
            const grouped = {};
            const categoriasSet = new Set();
            const tiposSet = new Set();
            
            data.forEach(item => {
                categoriasSet.add(item.categoria);
                tiposSet.add(item.tipo);
                
                if(!grouped[item.categoria]) {
                    grouped[item.categoria] = [];
                }
                grouped[item.categoria].push(item.tipo);
            });
            
            let html = '<option value="">Selecione o Tipo...</option>';
            for(const [cat, tipos] of Object.entries(grouped)) {
                html += `<optgroup label="${cat}">`;
                tipos.forEach(t => {
                    html += `<option value="${t}" data-categoria="${cat}">${t}</option>`;
                });
                html += `</optgroup>`;
            }
            categoriasTiposHtml = html;

            // Popular filtro de Categoria
            const catFilter = document.getElementById('categoriaFilter');
            let catOptions = '<option value="">Todas Categorias</option>';
            Array.from(categoriasSet).sort().forEach(cat => {
                catOptions += `<option value="${cat}">${cat}</option>`;
            });
            catOptions += '<option value="TBD">Pendentes (TBD)</option>';
            catFilter.innerHTML = catOptions;

            // Popular filtro de Tipo
            const tipoFilter = document.getElementById('tipoFilter');
            let tipoOptions = '<option value="">Todos Tipos</option>';
            Array.from(tiposSet).sort().forEach(t => {
                tipoOptions += `<option value="${t}">${t}</option>`;
            });
            tipoFilter.innerHTML = tipoOptions;

            // Restaurar valores se estiverem setados
            if (currentCategoria) catFilter.value = currentCategoria;
            if (currentTipo) tipoFilter.value = currentTipo;
        } catch (err) {
            console.error('Erro ao carregar categorias e tipos:', err);
        }
    }

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
        
        document.getElementById('tipoFilter').addEventListener('change', function(e) {
            currentTipo = e.target.value;
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

        // Eventos de Ordenação
        document.querySelectorAll('th.sortable').forEach(th => {
            th.addEventListener('click', function() {
                const sortField = this.getAttribute('data-sort');
                
                if (currentSort === sortField) {
                    // Alterna direção se for o mesmo campo
                    currentOrder = currentOrder === 'asc' ? 'desc' : 'asc';
                } else {
                    // Muda para novo campo, padrão desc para data, asc para outros
                    currentSort = sortField;
                    currentOrder = (sortField === 'data' || sortField === 'valor') ? 'desc' : 'asc';
                }
                
                currentPage = 1; // Reseta página ao ordenar
                updateSortUI();
                fetchTransactions();
            });
        });
    }

    function updateSortUI() {
        document.querySelectorAll('th.sortable').forEach(th => {
            const field = th.getAttribute('data-sort');
            const icon = th.querySelector('i.sort-icon');
            
            th.classList.remove('active');
            icon.className = 'fa-solid fa-sort sort-icon';
            
            if (field === currentSort) {
                th.classList.add('active');
                icon.className = `fa-solid fa-sort-${currentOrder === 'asc' ? 'up' : 'down'} sort-icon`;
            }
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
        if (currentTipo) params.append('tipo', currentTipo);
        
        params.append('sort', currentSort);
        params.append('order', currentOrder);
        
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
            
            row.insertCell(2).innerHTML = getCategoryBadge(item.categoria, item.descricao, item.sugestao, item.tipo, item.sugestao_tipo);
            
            let tipoCell = row.insertCell(3);
            tipoCell.innerHTML = `<span style="font-size:13px; color:#94a3b8;">${item.tipo || '-'}</span>`;
            
            let origemCell = row.insertCell(4);
            let origemIcon = item.origem.includes('Cartão') ? '<i class="fa-regular fa-credit-card text-purple"></i>' : '<i class="fa-solid fa-building-columns text-cyan"></i>';
            origemCell.innerHTML = `<span style="display:flex; align-items:center; gap:8px; font-size:13px;">${origemIcon} ${item.origem}</span>`;
            
            let valCell = row.insertCell(5);
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

    function getCategoryBadge(categoria, descricao, sugestao, tipo, sugestao_tipo) {
        const cat = (categoria || 'TBD').toLowerCase();
        
        if (cat === 'tbd') {
            const descSanitized = (descricao || '').replace(/"/g, '&quot;');
            let suggestHtml = '';
            if (sugestao) {
                suggestHtml = `
                    <div class="suggestion-chip" onclick="window.aceitarSugestao(this)" data-descricao="${descSanitized}" data-sugestao="${sugestao}" data-sugestao-tipo="${sugestao_tipo || ''}" title="Clique para aceitar a sugestão" style="background-color:rgba(255,255,255,0.1); cursor:pointer; font-size:11px; padding: 2px 6px; border-radius: 4px; display: inline-flex; align-items: center; gap: 4px; margin-top: 4px;">
                        <span>✨ ${sugestao}${sugestao_tipo ? ' ('+sugestao_tipo+')' : ''}</span>
                        <i class="fa-solid fa-check" style="font-size: 10px; color: var(--semantic-success);"></i>
                    </div>`;
            }

            return `
            <div class="classification-group" style="display:flex; flex-direction:column; gap:4px; min-width: 150px;">
                <div style="display:flex; gap:4px;">
                    <select class="tipo-select filter-select" data-descricao="${descSanitized}" style="padding: 4px 6px; font-size: 12px; flex: 1; border-color: rgba(239, 68, 68, 0.3);">
                        ${categoriasTiposHtml}
                    </select>
                    <button class="btn-save-mini" onclick="window.salvarClassificacao(this)" title="Salvar" style="background: var(--accent-primary); border: none; color: white; border-radius: 4px; padding: 0 8px; cursor: pointer;"><i class="fa-solid fa-floppy-disk"></i></button>
                </div>
                ${suggestHtml}
            </div>
            `;
        }
        
        if (cat.includes('refeição')) badgeClass = 'badge-ref';
        else if (cat.includes('transporte')) badgeClass = 'badge-trans';
        else if (cat.includes('saúde') || cat.includes('pessoais')) badgeClass = 'badge-saude';
        else if (cat.includes('lazer')) badgeClass = 'badge-lazer';
        
        return `<span class="badge ${badgeClass}">${categoria}</span>`;
    }

    // Funções globais para a tabela iterativa
    window.salvarClassificacao = function(btnElement) {
        const container = btnElement.closest('.classification-group');
        const tipoSelect = container.querySelector('.tipo-select');
        
        const novoTipo = tipoSelect.value;
        const descricao = tipoSelect.getAttribute('data-descricao');
        
        if (!novoTipo) {
            alert('Por favor, selecione o tipo da despesa.');
            return;
        }
        
        // Categoria será deduzida no back-end, ou podemos pegar do front-end
        const novaCategoria = tipoSelect.options[tipoSelect.selectedIndex].getAttribute('data-categoria');
        
        btnElement.disabled = true;
        enviarAtualizacao(descricao, novaCategoria, novoTipo, container);
    };

    window.aceitarSugestao = function(element) {
        const descricao = element.getAttribute('data-descricao');
        const sugestao = element.getAttribute('data-sugestao');
        const sugestaoTipo = element.getAttribute('data-sugestao-tipo');
        element.style.opacity = '0.5';
        element.style.pointerEvents = 'none';
        enviarAtualizacao(descricao, sugestao, sugestaoTipo, element.parentElement);
    };

    function enviarAtualizacao(descricao, novaCategoria, novoTipo, containerUI) {
        if(containerUI) containerUI.style.opacity = '0.5';
        
        fetch('/api/atualizar_categoria', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                descricao: descricao, 
                nova_categoria: novaCategoria,
                nova_tipo: novoTipo
            })
        })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'success') {
                // Ao dar sucesso, a refetchTransactions já limpará a tela em lote
                fetchTransactions();
            } else {
                alert('Erro ao atualizar categoria.');
                if(containerUI) containerUI.style.opacity = '1';
            }
        })
        .catch(err => {
            console.error(err);
            alert('Erro de rede ao atualizar.');
            if(containerUI) containerUI.style.opacity = '1';
        });
    }
});
