// Sessão — SPA com 7 telas. API no mesmo domínio (ou defina window.API_BASE).
const API = window.API_BASE || '';
const $ = s => document.querySelector(s);
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const hoje = () => new Date().toISOString().slice(0, 10);
const fdata = s => String(s).slice(0, 10).split('-').reverse().join('/');

async function api(path, opts = {}) {
  const r = await fetch(API + path, { headers: {'Content-Type': 'application/json'}, ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) {
    const e = new Error(typeof d.detail === 'string' ? d.detail : JSON.stringify(d.detail || 'Erro'));
    e.codigo = d.codigo; throw e;
  }
  return d;
}
function aviso(t, m) { $('#m-titulo').textContent = t; $('#m-msg').textContent = m;
  $('#modal').classList.remove('hidden'); $('#modal').classList.add('flex'); }
function fechar() { $('#modal').classList.add('hidden'); $('#modal').classList.remove('flex'); }
const falha = e => aviso(e.codigo ? `Regra violada (${e.codigo})` : 'Erro', e.message);
function ligar(sel, fn) {
  $(sel).onsubmit = async ev => { ev.preventDefault();
    try { await fn(Object.fromEntries(new FormData(ev.target))); } catch (e) { falha(e); } };
}
// cols: [rótulo, fn(linha), raw?]
function tabela(cols, rows) {
  return `<div class="overflow-x-auto"><table class="tbl"><thead><tr>${cols.map(c => `<th>${c[0]}</th>`).join('')}</tr></thead><tbody>${
    rows.map(r => `<tr>${cols.map(c => `<td>${c[2] ? c[1](r) : esc(c[1](r))}</td>`).join('')}</tr>`).join('') ||
    `<tr><td colspan="${cols.length}">Sem registros.</td></tr>`}</tbody></table></div>`;
}
const T = (titulo, corpo) => $('#tela').innerHTML = `<h2 class="h2">${titulo}</h2>${corpo}`;
const opts = (arr, rot) => arr.map(x => `<option value="${x.id}">${esc(rot(x))}</option>`).join('');

// ---- Tela 1
async function t1() {
  const ps = await api('/pacientes');
  T('Cadastro de Pacientes', `<form id="f" class="card grid md:grid-cols-5 gap-2">
    <input name="nome" placeholder="Nome" required class="inp">
    <select name="tipo" class="inp"><option>Particular</option><option>Convenio</option></select>
    <input name="convenio_nome" placeholder="Convênio (se aplicável)" class="inp">
    <input name="cpf" placeholder="CPF" required class="inp">
    <input name="data_inicio" type="date" value="${hoje()}" class="inp">
    <button class="btn md:col-span-5">Cadastrar</button></form>` +
    tabela([['Nome', p => p.nome], ['Tipo', p => p.tipo], ['Convênio', p => p.convenio_nome], ['CPF', p => p.cpf], ['Início', p => fdata(p.data_inicio)]], ps));
  ligar('#f', async d => { await api('/pacientes', {method: 'POST', body: d}); t1(); });
}

// ---- Tela 2
async function t2() {
  const [pr, sa] = await Promise.all([api('/profissionais'), api('/salas')]);
  T('Profissionais e Salas', `<div class="grid md:grid-cols-2 gap-4"><div>
    <form id="fp" class="card grid gap-2"><input name="nome" placeholder="Nome" required class="inp">
      <select name="tipo" class="inp"><option>Socio</option><option>Contratado</option></select>
      <input name="cpf" placeholder="CPF" required class="inp"><button class="btn">Adicionar profissional</button></form>
    ${tabela([['Nome', p => p.nome], ['Tipo', p => p.tipo], ['CPF', p => p.cpf]], pr)}</div><div>
    <form id="fs" class="card grid gap-2"><input name="nome" placeholder="Nome da sala" required class="inp">
      <input name="capacidade_simultanea" type="number" min="1" value="1" class="inp"><button class="btn">Adicionar sala</button></form>
    ${tabela([['Sala', s => s.nome], ['Capacidade simultânea', s => s.capacidade_simultanea]], sa)}</div></div>`);
  ligar('#fp', async d => { await api('/profissionais', {method: 'POST', body: d}); t2(); });
  ligar('#fs', async d => { d.capacidade_simultanea = +d.capacidade_simultanea; await api('/salas', {method: 'POST', body: d}); t2(); });
}

// ---- Tela 3
const regraPacote = d => d < '2026-11-01' ? '10 sessões / 90 dias (modalidade anterior)' : '15 sessões / 120 dias (modalidade nova)';
const expira = (c, v) => { const d = new Date(String(c).slice(0, 10) + 'T00:00:00'); d.setDate(d.getDate() + v); return d.toLocaleDateString('pt-BR'); };
async function t3() {
  const [ps, pk] = await Promise.all([api('/pacientes'), api('/pacotes')]);
  T('Venda de Pacotes', `<form id="f" class="card grid md:grid-cols-4 gap-2 items-center">
    <select name="paciente_id" class="inp">${opts(ps.filter(p => p.tipo === 'Particular'), p => p.nome)}</select>
    <input name="data_compra" id="dc" type="date" value="${hoje()}" class="inp">
    <span id="prev" class="text-sm text-teal-700 font-semibold">${regraPacote(hoje())}</span>
    <button class="btn">Vender pacote</button></form>` +
    tabela([['Paciente', k => k.paciente_nome], ['Compra', k => fdata(k.data_compra)], ['Sessões', k => k.sessoes_totais],
      ['Usadas', k => k.sessoes_usadas], ['Saldo', k => k.sessoes_totais - k.sessoes_usadas], ['Expira em', k => expira(k.data_compra, k.validade_dias)], ['Status', k => k.status]], pk));
  $('#dc').oninput = e => $('#prev').textContent = regraPacote(e.target.value);
  ligar('#f', async d => { d.paciente_id = +d.paciente_id; await api('/pacotes', {method: 'POST', body: d}); t3(); });
}

// ---- Tela 4
let diaAgenda = hoje();
async function t4() {
  const [sa, pr, ps, ag] = await Promise.all([api('/salas'), api('/profissionais'), api('/pacientes'), api('/agenda?data=' + diaAgenda)]);
  const horas = Array.from({length: 10}, (_, i) => String(8 + i).padStart(2, '0') + ':00');
  T('Agenda Interativa', `<input type="date" id="dia" value="${diaAgenda}" class="inp w-auto mb-3">
    <div class="overflow-x-auto"><table class="tbl"><thead><tr><th>Hora</th>${sa.map(s => `<th>${esc(s.nome)} (cap ${s.capacidade_simultanea})</th>`).join('')}</tr></thead><tbody>${
    horas.map(h => `<tr><td>${h}</td>${sa.map(s => `<td>${ag.filter(x => x.sala_id === s.id && x.data_hora.slice(11, 16) === h).map(x =>
      `<div class="chip"><b>${esc(x.paciente_nome)}</b> · ${esc(x.profissional_nome)}<br><small>${esc(x.status)}</small></div>`).join('')}
      <button class="add" data-s="${s.id}" data-h="${h}">+ agendar</button></td>`).join('')}</tr>`).join('')}</tbody></table></div>
    <div id="novo"></div>`);
  $('#dia').onchange = e => { diaAgenda = e.target.value; t4(); };
  document.querySelectorAll('.add').forEach(b => b.onclick = () => {
    $('#novo').innerHTML = `<form id="f" class="card grid md:grid-cols-4 gap-2 mt-3">
      <select name="paciente_id" class="inp">${opts(ps, p => p.nome)}</select>
      <select name="profissional_id" class="inp">${opts(pr, p => p.nome)}</select>
      <input class="inp" disabled value="${esc(sa.find(s => s.id == b.dataset.s).nome)} às ${b.dataset.h}">
      <button class="btn">Confirmar</button></form>`;
    ligar('#f', async d => {
      await api('/sessoes', {method: 'POST', body: {paciente_id: +d.paciente_id, profissional_id: +d.profissional_id,
        sala_id: +b.dataset.s, data_hora: `${diaAgenda}T${b.dataset.h}:00`}});
      t4();
    });
  });
}

// ---- Tela 5
let diaAt = hoje();
async function t5() {
  const ag = await api('/agenda?data=' + diaAt);
  T('Atendimento e Prontuário', `<input type="date" id="dia" value="${diaAt}" class="inp w-auto mb-3">` +
    tabela([['Hora', s => s.data_hora.slice(11, 16)], ['Paciente', s => s.paciente_nome], ['Profissional', s => s.profissional_nome],
      ['Status', s => s.status], ['Atraso', s => s.atraso_minutos + ' min'],
      ['', s => `<button class="btn" data-id="${s.id}">Abrir</button>`, true]], ag) + '<div id="painel"></div>');
  $('#dia').onchange = e => { diaAt = e.target.value; t5(); };
  document.querySelectorAll('[data-id]').forEach(b => b.onclick = () => {
    const s = ag.find(x => x.id == b.dataset.id);
    $('#painel').innerHTML = `<div class="card mt-3"><b>${esc(s.paciente_nome)}</b> — ${esc(s.status)}
      <div class="flex flex-wrap gap-2 my-2 items-center">
        <label>Atraso (min) <input id="atr" type="number" min="0" value="0" class="inp w-24 inline"></label>
        <button class="btn" id="b1">Registrar presença</button><button class="btn red" id="b2">Falta sem aviso</button>
        <button class="btn gray" id="b3">Cancelar</button></div>
      <textarea id="evo" rows="4" class="inp" placeholder="Evolução clínica (obrigatória)">${esc(s.evolucao_clinica || '')}</textarea>
      <button class="btn mt-2" id="b4">Salvar evolução</button></div>`;
    const post = (p, body) => async () => { try { await api(`/sessoes/${s.id}/${p}`, {method: 'POST', body}); t5(); } catch (e) { falha(e); } };
    $('#b1').onclick = () => post('realizar', {atraso_minutos: +$('#atr').value})();
    $('#b2').onclick = post('falta'); $('#b3').onclick = post('cancelar');
    $('#b4').onclick = () => post('evolucao', {texto: $('#evo').value})();
  });
}

// ---- Tela 6
async function t6() {
  const l = await api('/convenio/lote');
  const cols = [['Paciente', s => s.paciente_nome], ['Convênio', s => s.convenio_nome], ['Data', s => fdata(s.data_hora) + ' ' + s.data_hora.slice(11, 16)]];
  T('Lote de Convênio', `<div class="grid md:grid-cols-2 gap-4">
    <div><h3 class="ok mb-1">Faturáveis (${l.faturaveis.length})</h3>${tabela(cols, l.faturaveis)}
      <button id="fat" class="btn mt-2" ${l.faturaveis.length ? '' : 'disabled'}>Faturar lote</button></div>
    <div><h3 class="bad mb-1">Bloqueadas (${l.bloqueadas.length})</h3>${tabela([...cols, ['Justificativa', s => s.motivo]], l.bloqueadas)}</div></div>`);
  $('#fat').onclick = async () => { try { const r = await api('/convenio/lote/faturar', {method: 'POST'}); aviso('Lote faturado', `${r.faturadas} sessão(ões) faturada(s).`); t6(); } catch (e) { falha(e); } };
}

// ---- Tela 7
async function t7(ini = hoje().slice(0, 8) + '01', fim = hoje()) {
  const r = await api(`/relatorios/ocupacao?inicio=${ini}&fim=${fim}`);
  const bloco = (tit, rows) => `<div class="card"><h3 class="font-bold mb-2">${tit}</h3>${rows.map(x =>
    `<div class="mb-2"><div class="flex justify-between text-sm"><span>${esc(x.nome)}</span><span>${x.ocupacao_pct}% (${x.sessoes}/${x.capacidade})</span></div>
     <div class="bg-slate-200 rounded"><div class="bar" style="width:${Math.min(x.ocupacao_pct, 100)}%"></div></div></div>`).join('')}</div>`;
  T('Relatório de Ocupação', `<form id="f" class="card flex gap-2 items-center"><input name="ini" type="date" value="${ini}" class="inp w-auto">
    <input name="fim" type="date" value="${fim}" class="inp w-auto"><button class="btn">Atualizar</button></form>
    <div class="grid md:grid-cols-2 gap-4">${bloco('Por sala', r.por_sala)}${bloco('Por profissional', r.por_profissional)}</div>`);
  ligar('#f', async d => t7(d.ini, d.fim));
}

// ---- Navegação
const TELAS = [['1 · Pacientes', t1], ['2 · Profissionais e Salas', t2], ['3 · Pacotes', t3], ['4 · Agenda', t4], ['5 · Atendimento', t5], ['6 · Convênio', t6], ['7 · Ocupação', t7]];
function abrir(i) {
  document.querySelectorAll('.navbtn').forEach((b, j) => b.classList.toggle('ativo', i === j));
  TELAS[i][1]().catch(falha);
}
$('#nav').innerHTML = TELAS.map((t, i) => `<button class="navbtn" data-i="${i}">${t[0]}</button>`).join('');
document.querySelectorAll('.navbtn').forEach(b => b.onclick = () => abrir(+b.dataset.i));
abrir(0);
