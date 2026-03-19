// validacao_cartao.js

const fmt = (v) => v == null ? '-' : new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v);
const fmtDate = (d) => { if (!d) return '-'; const [y,m,day] = d.split('-'); return `${day}/${m}/${y}`; };

function statusBadge(status) {
    const map = {
        'OK':         { cls: 'status-ok',       icon: 'fa-circle-check',  label: 'OK' },
        'DIVERGENTE': { cls: 'status-divergente',icon: 'fa-triangle-exclamation', label: 'Divergente' },
        'SEM_TOTAL':  { cls: 'status-sem_total', icon: 'fa-circle-question', label: 'Sem total' }
    };
    const s = map[status] || map['SEM_TOTAL'];
    return `<span class="status-badge ${s.cls}"><i class="fa-solid ${s.icon}"></i>${s.label}</span>`;
}

function diffCell(diferenca) {
    if (diferenca === null || diferenca === undefined) return `<span class="diff-neutral">-</span>`;
    const abs = Math.abs(diferenca);
    const cls = abs < 0.05 ? 'diff-ok' : 'diff-warn';
    const icon = abs < 0.05 ? '✓' : '⚠';
    return `<span class="${cls}">${icon} ${fmt(diferenca)}</span>`;
}

async function loadPage() {
    const res = await fetch('/api/validacao_cartao');
    const data = await res.json();

    document.getElementById('loader').style.display = 'none';
    document.getElementById('tableWrapper').style.display = 'block';
    document.getElementById('summaryCards').style.display = 'grid';

    let cntOk = 0, cntDiv = 0, cntSem = 0, cntPar = 0;
    const tbody = document.getElementById('valBody');
    tbody.innerHTML = '';

    data.forEach(row => {
        if (row.status === 'OK') cntOk++;
        else if (row.status === 'DIVERGENTE') cntDiv++;
        else cntSem++;
        if ((row.qtd_futuras || 0) > 0) cntPar++;

        const parcelaAlert = (row.qtd_futuras > 0)
            ? `<i class="fa-solid fa-calendar-xmark alert-icon" title="${row.qtd_futuras} lançamento(s) com data futura (parcelas)"></i>`
            : '';

        const tr = document.createElement('tr');
        tr.className = 'row-main';
        tr.onclick = () => toggleDetails(row.fonte_arquivo, tr);
        tr.innerHTML = `
            <td style="font-family:monospace; font-size:12px;">
                <i class="fa-solid fa-chevron-right chevron" id="chevron-${row.fonte_arquivo.replace(/[.\s]/g, '_')}"></i>
                ${row.fonte_arquivo}${parcelaAlert}
            </td>
            <td>${fmtDate(row.vencimento)}</td>
            <td style="text-align:right;">${fmt(row.total_declarado)}</td>
            <td style="text-align:right;">${fmt(row.total_extraido)}</td>
            <td style="text-align:right;">${diffCell(row.diferenca)}</td>
            <td style="text-align:center;">
                <span style="color:var(--text-secondary); font-size:12px;">${row.qtd_total ?? '-'} itens</span>
                ${row.qtd_futuras > 0 ? `<br><span style="color:#fbbf24; font-size:10px;">(+${row.qtd_futuras} futuras)</span>` : ''}
            </td>
            <td>${statusBadge(row.status)}</td>
        `;
        tbody.appendChild(tr);

        // expansion row (hidden by default)
        const trDetail = document.createElement('tr');
        trDetail.className = 'row-detail';
        trDetail.id = `detail-${row.fonte_arquivo.replace(/[.\s]/g, '_')}`;
        trDetail.innerHTML = `
            <td colspan="7">
                <div class="detail-container">
                    <div class="loader" id="loader-${row.fonte_arquivo.replace(/[.\s]/g, '_')}" style="margin:20px auto; position:relative; transform:none; left:auto; top:auto;"></div>
                    <div id="content-${row.fonte_arquivo.replace(/[.\s]/g, '_')}"></div>
                </div>
            </td>
        `;
        tbody.appendChild(trDetail);
    });

    document.getElementById('cntOk').textContent = cntOk;
    document.getElementById('cntDiv').textContent = cntDiv;
    document.getElementById('cntSem').textContent = cntSem;
    document.getElementById('cntPar').textContent = cntPar;
}

async function toggleDetails(filename, rowElement) {
    const id = filename.replace(/[.\s]/g, '_');
    const detailRow = document.getElementById(`detail-${id}`);
    const chevron = document.querySelector(`.chevron`); // This selector might be too broad if we have many chevrons
    const targetChevron = document.getElementById(`chevron-${id}`);
    
    if (detailRow.style.display === 'table-row') {
        detailRow.style.display = 'none';
        rowElement.classList.remove('expanded');
        targetChevron.style.transform = 'rotate(0deg)';
    } else {
        detailRow.style.display = 'table-row';
        rowElement.classList.add('expanded');
        targetChevron.style.transform = 'rotate(90deg)';
        
        const contentDiv = document.getElementById(`content-${id}`);
        const localLoader = document.getElementById(`loader-${id}`);
        
        if (contentDiv.innerHTML === '') {
            localLoader.style.display = 'block';
            try {
                const res = await fetch(`/api/validacao_cartao/detalhes/${encodeURIComponent(filename)}`);
                const items = await res.json();
                
                let html = `
                    <table class="detail-table">
                        <thead>
                            <tr>
                                <th>Data</th>
                                <th>Descrição</th>
                                <th style="text-align:right;">Valor</th>
                                <th>Tipo / Categoria</th>
                            </tr>
                        </thead>
                        <tbody>
                `;
                
                items.forEach(item => {
                    html += `
                        <tr>
                            <td>${fmtDate(item.data)}</td>
                            <td>${item.descricao}</td>
                            <td style="text-align:right; font-weight:500;">${fmt(item.valor)}</td>
                            <td style="color:var(--text-secondary); font-size:11px;">
                                ${item.tipo || 'TBD'} / ${item.categoria || 'TBD'}
                            </td>
                        </tr>
                    `;
                });
                
                html += `</tbody></table>`;
                contentDiv.innerHTML = html;
            } catch (err) {
                contentDiv.innerHTML = `<p style="color:#f87171;">Erro ao carregar detalhes.</p>`;
            } finally {
                localLoader.style.display = 'none';
            }
        }
    }
}

document.addEventListener('DOMContentLoaded', loadPage);
