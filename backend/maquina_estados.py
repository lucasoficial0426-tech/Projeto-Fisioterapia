"""Máquina de estados da Sessão + regras de agenda, lote de convênio e ocupação."""
from datetime import timedelta

from pacotes_controller import ErroRegra, consumir_sessao

AGENDADA, REALIZADA, EVOLUIDA, FATURADA = "Agendada", "Realizada", "Evoluída", "Faturada"
FALTA, CANCELADA, REDUZIDO = "Falta sem aviso", "Cancelada com aviso", "Atendimento reduzido"
STATUS_OCUPAM = {AGENDADA, REALIZADA, EVOLUIDA, FATURADA, REDUZIDO, FALTA}
ANTECEDENCIA_MIN_H = 24
ATRASO_LIMITE_MIN = 15
HORAS_DIA = 10  # grade 08:00–17:00 (1 sessão/hora/vaga)


class TransicaoInvalida(ErroRegra):
    codigo = "TRANSICAO_INVALIDA"


class EvolucaoObrigatoria(TransicaoInvalida):
    codigo = "RN-06"


class BloqueioFaturamento(TransicaoInvalida):
    codigo = "RN-08"


class ConflitoSala(ErroRegra):
    codigo = "RN-04"


class ConflitoProfissional(ErroRegra):
    codigo = "RN-05"


class SessaoFSM:
    TRANSICOES = {
        AGENDADA: {REALIZADA, REDUZIDO, FALTA, CANCELADA},
        REALIZADA: {EVOLUIDA},
        EVOLUIDA: {FATURADA},
    }

    def __init__(self, sessao, pacote=None):
        self.s, self.pacote = sessao, pacote

    def _ir(self, novo, consome=False):
        if novo not in self.TRANSICOES.get(self.s["status"], set()):
            raise TransicaoInvalida(f"Transição '{self.s['status']}' -> '{novo}' não permitida.")
        if consome and self.pacote is not None:
            consumir_sessao(self.pacote)
        self.s["status"] = novo
        return novo

    def realizar(self, atraso_minutos=0):
        """RN-08: atraso > 15 min => Atendimento reduzido (consome sessão)."""
        novo = REDUZIDO if atraso_minutos > ATRASO_LIMITE_MIN else REALIZADA
        self._ir(novo, consome=True)
        self.s["atraso_minutos"] = atraso_minutos
        return novo

    def registrar_falta(self):
        """RN-02: falta sem aviso consome 1 sessão."""
        return self._ir(FALTA, consome=True)

    def cancelar(self, agora):
        """RN-03: >=24h de antecedência não consome; senão vira falta sem aviso (RN-02)."""
        horas = (self.s["data_hora"] - agora).total_seconds() / 3600
        if horas >= ANTECEDENCIA_MIN_H:
            return self._ir(CANCELADA)
        return self._ir(FALTA, consome=True)

    def evoluir(self, texto):
        texto = (texto or "").strip()
        if self.s["status"] == REDUZIDO:  # prontuário registrado, status permanece
            if not texto:
                raise EvolucaoObrigatoria("Evolução clínica obrigatória.")
            self.s["evolucao_clinica"] = texto
            return REDUZIDO
        if self.s["status"] != REALIZADA:
            raise TransicaoInvalida(f"Transição '{self.s['status']}' -> '{EVOLUIDA}' não permitida.")
        if not texto:
            raise EvolucaoObrigatoria("Evolução clínica obrigatória.")
        self.s["evolucao_clinica"] = texto
        return self._ir(EVOLUIDA)

    def faturar(self):
        st = self.s["status"]
        if st == REALIZADA:
            raise EvolucaoObrigatoria("RN-06: Realizada -> Faturada é proibido; registre a evolução clínica.")
        if st == REDUZIDO:
            raise BloqueioFaturamento("RN-08: Atendimento reduzido não pode ser faturado no convênio.")
        return self._ir(FATURADA)


# ---------- Agenda (RN-04 e RN-05) ----------
def validar_agendamento_sessao(sessoes, salas, sala_id, profissional_id, data_hora):
    """salas: {sala_id: capacidade}. Levanta ConflitoSala / ConflitoProfissional."""
    mesmas = [s for s in sessoes if s["data_hora"] == data_hora and s["status"] in STATUS_OCUPAM]
    if sum(1 for s in mesmas if s["sala_id"] == sala_id) >= salas[sala_id]:
        raise ConflitoSala(f"Sala lotada neste horário (capacidade {salas[sala_id]}).")
    if any(s["profissional_id"] == profissional_id for s in mesmas):
        raise ConflitoProfissional("Profissional já possui sessão neste horário.")
    return True


# ---------- Lote de convênio (RN-06, RN-08) ----------
def classificar_lote(sessoes, pacientes):
    faturaveis, bloqueadas = [], []
    for s in sessoes:
        if pacientes[s["paciente_id"]]["tipo"] != "Convenio":
            continue
        if s["status"] not in (REALIZADA, EVOLUIDA, REDUZIDO):
            continue
        motivo = None
        if s["status"] == REDUZIDO:
            motivo = "RN-08: atendimento reduzido (atraso > 15 min) não é faturável."
        elif s["status"] == REALIZADA or not (s.get("evolucao_clinica") or "").strip():
            motivo = "RN-06: sem evolução clínica registrada."
        (bloqueadas if motivo else faturaveis).append({**s, "motivo": motivo})
    return faturaveis, bloqueadas


# ---------- Relatório de ocupação ----------
def _dias_uteis(ini, fim):
    n, d = 0, ini
    while d <= fim:
        n += d.weekday() < 5
        d += timedelta(days=1)
    return n


def calcular_ocupacao(sessoes, salas, profissionais, inicio, fim):
    """salas: [{id,nome,capacidade_simultanea}] | profissionais: [{id,nome}]."""
    dias = _dias_uteis(inicio, fim)
    ativas = [s for s in sessoes if s["status"] in STATUS_OCUPAM and inicio <= s["data_hora"].date() <= fim]

    def linha(ident, nome, qtd, cap):
        cap = max(cap, 1)
        return {"id": ident, "nome": nome, "sessoes": qtd, "capacidade": cap,
                "ocupacao_pct": round(100 * qtd / cap, 1)}

    por_sala = [linha(x["id"], x["nome"], sum(s["sala_id"] == x["id"] for s in ativas),
                      x["capacidade_simultanea"] * HORAS_DIA * dias) for x in salas]
    por_prof = [linha(x["id"], x["nome"], sum(s["profissional_id"] == x["id"] for s in ativas),
                      HORAS_DIA * dias) for x in profissionais]
    return {"por_sala": por_sala, "por_profissional": por_prof}
