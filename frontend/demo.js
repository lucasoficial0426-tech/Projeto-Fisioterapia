// MODO DEMO: abra index.html?demo=1 — simula a API em memória (sem banco), para ver as 7 telas.
(() => {
  if (!location.search.includes('demo')) return;
  const H = new Date().toISOString().slice(0, 10);
  let seq = 100; const nid = () => ++seq;
  const salas = [[1, 'Sala 1', 1], [2, 'Sala 2', 1], [3, 'Sala 3 Pilates', 3]].map(([id, nome, c]) => ({id, nome, capacidade_simultanea: c}));
  const profs = [[1, 'Helena', 'Socio'], [2, 'Diego', 'Contratado'], [3, 'Sabrina', 'Contratado']].map(([id, nome, tipo]) => ({id, nome, tipo, cpf: `000.000.000-0${id}`}));
  const pacs = [[1, 'Marta', 'Particular', null], [2, 'Ricardo', 'Particular', null], [3, 'José', 'Convenio', 'Unimed'], [4, 'Carla', 'Convenio', 'Bradesco Saúde']]
    .map(([id, nome, tipo, c]) => ({id, nome, tipo, convenio_nome: c, cpf: `111.111.111-0${id}`, data_inicio: '2026-06-01'}));
  const pacotes = [[1, 1, '2026-10-15', 10, 7, 90, 'Ativo'], [2, 1, '2026-06-01', 10, 7, 90, 'Expirado'], [3, 2, '2026-11-02', 15, 2, 120, 'Ativo']]
    .map(([id, p, c, t, u, v, st]) => ({id, paciente_id: p, paciente_nome: pacs[p - 1].nome, data_compra: c, sessoes_totais: t, sessoes_usadas: u, validade_dias: v, status: st}));
  const mk = (p, pr, sa, h, status, x = {}) => ({id: nid(), paciente_id: p, profissional_id: pr, sala_id: sa, pacote_id: null, data_hora: `${H}T${h}:00`, status, evolucao_clinica: null, atraso_minutos: 0, ...x});
  const ses = [mk(1, 3, 1, '10:00', 'Agendada', {pacote_id: 1}), mk(2, 1, 3, '10:00', 'Agendada', {pacote_id: 3}), mk(3, 1, 1, '09:00', 'Realizada'),
    mk(3, 2, 1, '11:00', 'Evoluída', {evolucao_clinica: 'Boa evolução.'}), mk(4, 3, 2, '14:00', 'Atendimento reduzido', {atraso_minutos: 20})];
  const by = (l, i) => l.find(x => x.id == i);
  const enr = s => ({...s, paciente_nome: by(pacs, s.paciente_id).nome, profissional_nome: by(profs, s.profissional_id).nome, sala_nome: by(salas, s.sala_id).nome});
  const E = (c, m) => [409, {codigo: c, detail: m}];
  const saldo = p => p.sessoes_totais - p.sessoes_usadas;
  const exp = p => { const d = new Date(p.data_compra + 'T00:00:00'); d.setDate(d.getDate() + p.validade_dias); return d.toISOString().slice(0, 10); };
  const consome = s => { const p = by(pacotes, s.pacote_id); if (p) p.sessoes_usadas++; };
  const lote = () => { const f = [], b = [];
    ses.filter(s => by(pacs, s.paciente_id).tipo === 'Convenio' && ['Realizada', 'Evoluída', 'Atendimento reduzido'].includes(s.status)).forEach(s => {
      const m = s.status === 'Atendimento reduzido' ? 'RN-08: atendimento reduzido (atraso > 15 min) não é faturável.'
        : (s.status === 'Realizada' || !s.evolucao_clinica) ? 'RN-06: sem evolução clínica registrada.' : null;
      (m ? b : f).push({...enr(s), convenio_nome: by(pacs, s.paciente_id).convenio_nome, motivo: m}); });
    return {faturaveis: f, bloqueadas: b}; };
  function ocup(ini, fim) {
    let dias = 0; for (let d = new Date(ini + 'T00:00:00'); d <= new Date(fim + 'T00:00:00'); d.setDate(d.getDate() + 1)) if (d.getDay() % 6) dias++;
    const at = ses.filter(s => s.status !== 'Cancelada com aviso' && s.data_hora.slice(0, 10) >= ini && s.data_hora.slice(0, 10) <= fim);
    const l = (x, q, cap) => { cap = Math.max(cap, 1); return {id: x.id, nome: x.nome, sessoes: q, capacidade: cap, ocupacao_pct: Math.round(1000 * q / cap) / 10}; };
    return {por_sala: salas.map(x => l(x, at.filter(s => s.sala_id === x.id).length, x.capacidade_simultanea * 10 * dias)),
            por_profissional: profs.map(x => l(x, at.filter(s => s.profissional_id === x.id).length, 10 * dias))};
  }
  function rota(m, url, b) {
    const [p, q] = url.split('?'); const qs = new URLSearchParams(q || ''); let r;
    if (m === 'GET') {
      if (p === '/pacientes') return [200, pacs]; if (p === '/profissionais') return [200, profs]; if (p === '/salas') return [200, salas];
      if (p === '/pacotes') return [200, pacotes]; if (p === '/convenio/lote') return [200, lote()];
      if (p === '/agenda') return [200, ses.filter(s => s.data_hora.startsWith(qs.get('data'))).map(enr)];
      if (p === '/relatorios/ocupacao') return [200, ocup(qs.get('inicio'), qs.get('fim'))];
    }
    if (p === '/pacientes') { pacs.push({id: nid(), ...b, convenio_nome: b.tipo === 'Convenio' ? b.convenio_nome : null}); return [201, {}]; }
    if (p === '/profissionais') { profs.push({id: nid(), ...b}); return [201, {}]; }
    if (p === '/salas') { salas.push({id: nid(), ...b}); return [201, {}]; }
    if (p === '/pacotes') { const n = b.data_compra < '2026-11-01';
      pacotes.push({id: nid(), paciente_id: b.paciente_id, paciente_nome: by(pacs, b.paciente_id).nome, data_compra: b.data_compra, sessoes_totais: n ? 10 : 15, sessoes_usadas: 0, validade_dias: n ? 90 : 120, status: 'Ativo'}); return [201, {}]; }
    if (p === '/sessoes') {
      const mesmas = ses.filter(s => s.data_hora === b.data_hora && s.status !== 'Cancelada com aviso');
      if (mesmas.filter(s => s.sala_id === b.sala_id).length >= by(salas, b.sala_id).capacidade_simultanea) return E('RN-04', 'Sala lotada neste horário.');
      if (mesmas.some(s => s.profissional_id === b.profissional_id)) return E('RN-05', 'Profissional já possui sessão neste horário.');
      let pk = null;
      if (by(pacs, b.paciente_id).tipo === 'Particular') {
        const dia = b.data_hora.slice(0, 10);
        pk = pacotes.find(x => x.paciente_id === b.paciente_id && dia <= exp(x) && saldo(x) > 0);
        if (!pk) return E('RN-07', 'Paciente particular sem pacote válido (expirado ou sem saldo).');
      }
      ses.push({id: nid(), paciente_id: b.paciente_id, profissional_id: b.profissional_id, sala_id: b.sala_id, pacote_id: pk && pk.id, data_hora: b.data_hora, status: 'Agendada', evolucao_clinica: null, atraso_minutos: 0});
      return [201, {}];
    }
    if (p === '/convenio/lote/faturar') { const f = lote().faturaveis; f.forEach(x => by(ses, x.id).status = 'Faturada'); return [200, {faturadas: f.length}]; }
    if ((r = p.match(/^\/sessoes\/(\d+)\/(\w+)$/))) {
      const s = by(ses, r[1]), a = r[2];
      if (a === 'realizar' || a === 'falta' || a === 'cancelar') {
        if (s.status !== 'Agendada') return E('TRANSICAO_INVALIDA', `Transição '${s.status}' não permitida.`);
        if (a === 'realizar') { s.status = b.atraso_minutos > 15 ? 'Atendimento reduzido' : 'Realizada'; s.atraso_minutos = b.atraso_minutos; consome(s); }
        else if (a === 'falta' || new Date(s.data_hora) - new Date() < 864e5) { s.status = 'Falta sem aviso'; consome(s); }
        else s.status = 'Cancelada com aviso';
      } else if (a === 'evolucao') {
        if (!b.texto.trim()) return E('RN-06', 'Evolução clínica obrigatória.');
        if (s.status === 'Realizada') s.status = 'Evoluída'; else if (s.status !== 'Atendimento reduzido') return E('TRANSICAO_INVALIDA', `Transição '${s.status}' não permitida.`);
        s.evolucao_clinica = b.texto;
      }
      return [200, s];
    }
    return [404, {detail: 'Rota demo inexistente'}];
  }
  window.fetch = async (url, o = {}) => { const [st, body] = rota(o.method || 'GET', url, o.body ? JSON.parse(o.body) : {});
    return {ok: st < 400, status: st, json: async () => body}; };
  addEventListener('DOMContentLoaded', () => { const d = document.createElement('div'); d.className = 'bg-amber-300 text-center text-sm py-1';
    d.textContent = 'MODO DEMO — dados simulados em memória (nada é gravado).'; document.body.prepend(d); });
})();
