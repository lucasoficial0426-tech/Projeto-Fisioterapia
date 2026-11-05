"""Regras temporais e de saldo dos pacotes (RN-01, RN-07)."""
from datetime import date, datetime, timedelta

DATA_CORTE = date(2026, 11, 1)  # Aditivo 01/11


class ErroRegra(Exception):
    codigo = "ERRO"


class PacoteInvalido(ErroRegra):
    codigo = "RN-07"


def _d(x):
    return x.date() if isinstance(x, datetime) else x


def regras_pacote(data_compra):
    """RN-01: (sessões, validade_dias) conforme a data de compra."""
    return (10, 90) if _d(data_compra) < DATA_CORTE else (15, 120)


def novo_pacote(paciente_id, data_compra):
    sessoes, validade = regras_pacote(data_compra)
    return {"paciente_id": paciente_id, "data_compra": _d(data_compra),
            "sessoes_totais": sessoes, "sessoes_usadas": 0,
            "validade_dias": validade, "status": "Ativo"}


def data_expiracao(p):
    return _d(p["data_compra"]) + timedelta(days=p["validade_dias"])


def saldo(p):
    return p["sessoes_totais"] - p["sessoes_usadas"]


def esta_expirado(p, referencia):
    return _d(referencia) > data_expiracao(p)


def validar_agendamento(p, data_sessao):
    """RN-07: pacote expirado ou saldo zerado não pode ser agendado."""
    if p is None:
        raise PacoteInvalido("Paciente particular sem pacote cadastrado.")
    if esta_expirado(p, data_sessao):
        raise PacoteInvalido(f"Pacote expirado em {data_expiracao(p):%d/%m/%Y}.")
    if saldo(p) <= 0:
        raise PacoteInvalido("Pacote sem saldo de sessões.")
    return True


def escolher_pacote_valido(pacotes, data_sessao):
    erro = PacoteInvalido("Paciente particular sem pacote cadastrado.")
    for p in sorted(pacotes, key=lambda x: x["data_compra"]):
        try:
            validar_agendamento(p, data_sessao)
            return p
        except PacoteInvalido as e:
            erro = e
    raise erro


def consumir_sessao(p):
    if saldo(p) <= 0:
        raise PacoteInvalido("Pacote sem saldo de sessões.")
    p["sessoes_usadas"] += 1
    return saldo(p)
