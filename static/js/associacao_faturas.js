// associacao_faturas.js — Gerencia a associação entre pagamentos de fatura e meses do cartão

let mesesDisponiveis = [];

const formatCurrency = (v) =>
    v == null ? '-' : new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v);

const formatDate = (d) => {
    if (!d) return '-';
    const [y, m, day] = d.split('-');
    return `${day}/${m}/${y}`;
};

function mesLabelFromYearMonth(ano, mes) {
    if (!ano || !mes) return null;
    const meses = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'];
    return `${meses[parseInt(mes) - 1]}/${ano}`;
}

async function fetchMesesDisponiveis(exceptMovId = null) {
    let url = '/api/fatura_meses_disponiveis';
    if (exceptMovId) url += `?except_mov_id=${exceptMovId}`;
    const res = await fetch(url);
    return await res.json();
}

function buildMesOptions(selectedAno, selectedMes) {
    let html = '<option value="">-- Selecione o mês da fatura --</option>';
    mesesDisponiveis.forEach(m => {
        const val = `${m.ano}-${m.mes}`;
        const label = `${mesLabelFromYearMonth(m.ano, m.mes)} — ${formatCurrency(Math.abs(m.total))} (${m.qtd} itens)`;
        const sel = (m.ano === selectedAno && m.mes === selectedMes) ? 'selected' : '';
        html += `<option value="${val}" ${sel}>${label}</option>`;
    });
    return html;
}

function renderStatusBadge(row) {
    if (!row.fatura_ano) {
        return `<span class="status-badge status-sem-assoc"><i class="fa-solid fa-circle-xmark"></i> Sem associação</span>`;
    }
    if (row.confirmado) {
        return `<span class="status-badge status-confirmado"><i class="fa-solid fa-circle-check"></i> Confirmado</span>`;
    }
    return `<span class="status-badge status-automatico"><i class="fa-solid fa-rotate"></i> Automático</span>`;
}

function renderDiff(row) {
    if (row.diferenca === null || row.diferenca === undefined) {
        return `<span class="diff-neutral">-</span>`;
    }
    const abs = Math.abs(row.diferenca);
    const cls = abs < 0.02 ? 'diff-ok' : 'diff-warn';
    const icon = abs < 0.02 ? '✓' : '⚠';
    return `<span class="${cls}">${icon} ${formatCurrency(row.diferenca)}</span>`;
}

async function openEditRow(rowId, pagId, currentAno, currentMes) {
    // Remove qualquer edição anterior aberta
    document.querySelectorAll('.edit-expansion-row').forEach(r => r.remove());
    document.querySelectorAll('tr.editing-row').forEach(r => r.classList.remove('editing-row'));

    const refRow = document.getElementById(`row-${rowId}`);
    if (!refRow) return;
    refRow.classList.add('editing-row');

    // Busca meses disponíveis para esta linha específica
    mesesDisponiveis = await fetchMesesDisponiveis(pagId);

    const editTr = document.createElement('tr');
    editTr.className = 'edit-expansion-row';
    editTr.innerHTML = `
        <td colspan="9" class="edit-row">
            <div class="edit-panel">
                <i class="fa-solid fa-link" style="color:var(--accent-primary);"></i>
                <span style="color:var(--text-secondary); font-size:13px;">Associar à fatura do mês:</span>
                <select id="selMes_${rowId}" class="fatura-select">
                    ${buildMesOptions(currentAno, currentMes)}
                </select>
                <button class="btn btn-primary" style="white-space:nowrap;" onclick="saveAssociation(${pagId}, '${rowId}')">
                    <i class="fa-solid fa-floppy-disk"></i> Salvar
                </button>
                ${currentAno ? `
                <button class="btn btn-secondary" style="white-space:nowrap;" onclick="removeAssociation(${pagId}, '${rowId}')">
                    <i class="fa-solid fa-trash"></i> Remover
                </button>` : ''}
                <button class="btn" style="white-space:nowrap;" onclick="cancelEdit('${rowId}')">
                    Cancelar
                </button>
            </div>
        </td>
    `;
    refRow.insertAdjacentElement('afterend', editTr);
}

async function saveAssociation(pagId, rowId) {
    const sel = document.getElementById(`selMes_${rowId}`);
    if (!sel || !sel.value) { alert('Selecione um mês da fatura.'); return; }

    const [ano, mes] = sel.value.split('-');
    const res = await fetch('/api/fatura_associacoes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ movimentacao_id: pagId, fatura_ano: ano, fatura_mes: mes, confirmado: 1 })
    });
    if (res.ok) {
        await loadPage();
    } else {
        const err = await res.json();
        alert(err.error || 'Erro ao salvar.');
    }
}

async function removeAssociation(pagId, rowId) {
    if (!confirm('Remover a associação? O sistema voltará a usar o mês anterior automaticamente.')) return;

    // Find assoc_id from table — fetch fresh
    const listRes = await fetch('/api/fatura_associacoes');
    const list = await listRes.json();
    const item = list.find(r => r.id === pagId);
    if (item && item.assoc_id) {
        await fetch(`/api/fatura_associacoes/${item.assoc_id}`, { method: 'DELETE' });
    }
    await loadPage();
}

function cancelEdit(rowId) {
    document.querySelectorAll('.edit-expansion-row').forEach(r => r.remove());
    document.querySelectorAll('tr.editing-row').forEach(r => r.classList.remove('editing-row'));
}

async function loadPage() {
    document.getElementById('loader').style.display = 'block';
    document.getElementById('tableWrapper').style.display = 'none';
    document.getElementById('emptyMsg').style.display = 'none';

    // await loadMesesDisponiveis(); // Não precisa carregar na carga inicial mais

    const res = await fetch('/api/fatura_associacoes');
    const data = await res.json();

    document.getElementById('loader').style.display = 'none';

    if (!data || data.length === 0) {
        document.getElementById('emptyMsg').style.display = 'block';
        return;
    }

    document.getElementById('tableWrapper').style.display = 'block';
    const tbody = document.getElementById('assocBody');
    tbody.innerHTML = '';

    data.forEach(row => {
        const faturaLabel = row.fatura_ano
            ? `${mesLabelFromYearMonth(row.fatura_ano, row.fatura_mes)} (${row.fatura_qtd || '?'} itens)`
            : '<span style="color:var(--text-secondary);">—</span>';

        const tr = document.createElement('tr');
        tr.id = `row-${row.id}`;
        tr.innerHTML = `
            <td style="color:var(--text-secondary); font-size:11px;">${row.id}</td>
            <td>${formatDate(row.data)}</td>
            <td>${row.descricao}</td>
            <td style="text-align:right;" class="${row.valor < 0 ? 'val-negative' : 'val-positive'}">${formatCurrency(row.valor)}</td>
            <td>${faturaLabel}</td>
            <td style="text-align:right;">${formatCurrency(row.fatura_total ? -Math.abs(row.fatura_total) : null)}</td>
            <td style="text-align:right;">${renderDiff(row)}</td>
            <td>${renderStatusBadge(row)}</td>
            <td>
                <button class="btn btn-icon" title="Editar associação"
                    onclick="openEditRow(${row.id}, ${row.id}, '${row.fatura_ano || ''}', '${row.fatura_mes || ''}')">
                    <i class="fa-solid fa-pen-to-square" style="color:var(--accent-primary);"></i>
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

document.addEventListener('DOMContentLoaded', loadPage);
