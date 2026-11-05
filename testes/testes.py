"""Suíte com 22 testes (unittest) — 10 Casos Oficiais + Aditivo 01/11."""
import os
import sys
import unittest
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
import maquina_estados as me
import pacotes_controller as pc

SALAS = {1: 1, 2: 1, 3: 3}
H10 = datetime(2026, 11, 2, 10, 0)  # segunda-feira
HELENA, DIEGO, SABRINA = 1, 2, 3


def S(sid, sala, prof, dh=H10, status=me.AGENDADA, paciente=1, **k):
    return {"id": sid, "paciente_id": paciente, "profissional_id": prof, "sala_id": sala, "pacote_id": None,
            "data_hora": dh, "status": status, "evolucao_clinica": None, "atraso_minutos": 0, **k}


def pacote(usadas=7, compra=date(2026, 10, 15), total=10, validade=90):
    return {"data_compra": compra, "sessoes_totais": total, "sessoes_usadas": usadas, "validade_dias": validade, "status": "Ativo"}


CONV = {3: {"tipo": "Convenio"}, 4: {"tipo": "Convenio"}}


class TestAgenda(unittest.TestCase):
    def test_caso1_sala3_lotada_recusa_4a(self):  # RN-04
        ss = [S(1, 3, HELENA), S(2, 3, DIEGO), S(3, 3, SABRINA)]
        with self.assertRaises(me.ConflitoSala):
            me.validar_agendamento_sessao(ss, SALAS, 3, HELENA, H10)

    def test_caso2_sabrina_outra_sala_mesmo_horario(self):  # RN-05
        with self.assertRaises(me.ConflitoProfissional):
            me.validar_agendamento_sessao([S(1, 1, SABRINA)], SALAS, 2, SABRINA, H10)

    def test_caso3_sala3_com_2_aceita_3a(self):
        self.assertTrue(me.validar_agendamento_sessao([S(1, 3, HELENA), S(2, 3, DIEGO)], SALAS, 3, SABRINA, H10))

    def test_sala_capacidade_1_ocupada(self):
        with self.assertRaises(me.ConflitoSala):
            me.validar_agendamento_sessao([S(1, 1, HELENA)], SALAS, 1, DIEGO, H10)

    def test_cancelada_libera_horario(self):
        ss = [S(1, 1, HELENA, status=me.CANCELADA)]
        self.assertTrue(me.validar_agendamento_sessao(ss, SALAS, 1, HELENA, H10))


class TestSaldo(unittest.TestCase):
    def setUp(self):
        self.p = pacote(usadas=7)  # saldo 3
        self.dh = datetime(2026, 11, 10, 9, 0)

    def test_caso4_falta_sem_aviso_consome(self):  # RN-02
        s = S(1, 1, HELENA, dh=self.dh)
        me.SessaoFSM(s, self.p).registrar_falta()
        self.assertEqual((s["status"], pc.saldo(self.p)), (me.FALTA, 2))

    def test_caso5_cancelar_48h_nao_consome(self):  # RN-03
        s = S(1, 1, HELENA, dh=self.dh)
        me.SessaoFSM(s, self.p).cancelar(self.dh - timedelta(hours=48))
        self.assertEqual((s["status"], pc.saldo(self.p)), (me.CANCELADA, 3))

    def test_cancelar_menos_24h_vira_falta(self):  # RN-02
        s = S(1, 1, HELENA, dh=self.dh)
        me.SessaoFSM(s, self.p).cancelar(self.dh - timedelta(hours=2))
        self.assertEqual((s["status"], pc.saldo(self.p)), (me.FALTA, 2))


class TestPacotes(unittest.TestCase):
    def test_caso6_p02_expirado_recusa(self):  # RN-01 / RN-07
        p02 = pacote(compra=date(2026, 6, 1))
        with self.assertRaises(pc.PacoteInvalido):
            pc.validar_agendamento(p02, date(2026, 11, 10))
        with self.assertRaises(pc.PacoteInvalido):
            pc.escolher_pacote_valido([p02], date(2026, 11, 10))

    def test_saldo_zerado_recusa(self):
        with self.assertRaises(pc.PacoteInvalido):
            pc.validar_agendamento(pacote(usadas=10), date(2026, 11, 10))

    def test_aditivo_pacote_15_10_2026(self):
        self.assertEqual(pc.regras_pacote(date(2026, 10, 15)), (10, 90))
        self.assertEqual(pc.regras_pacote(date(2026, 10, 31)), (10, 90))
        p = pc.novo_pacote(1, date(2026, 10, 15))
        self.assertEqual((p["sessoes_totais"], p["validade_dias"], pc.data_expiracao(p)), (10, 90, date(2027, 1, 13)))

    def test_aditivo_pacote_01_11_2026(self):
        p = pc.novo_pacote(1, date(2026, 11, 1))
        self.assertEqual((p["sessoes_totais"], p["validade_dias"], pc.data_expiracao(p)), (15, 120, date(2027, 3, 1)))

    def test_pacote_valido_aceito_ate_data_limite(self):
        p = pacote()
        self.assertTrue(pc.validar_agendamento(p, date(2026, 11, 10)))
        self.assertTrue(pc.validar_agendamento(p, pc.data_expiracao(p)))


class TestFaturamento(unittest.TestCase):
    def test_caso7_jose_sem_evolucao_bloqueia(self):  # RN-06
        s = S(1, 1, HELENA, status=me.REALIZADA, paciente=3)
        f, b = me.classificar_lote([s], CONV)
        self.assertEqual((len(f), len(b)), (0, 1))
        self.assertTrue(b[0]["motivo"].startswith("RN-06"))
        with self.assertRaises(me.EvolucaoObrigatoria):
            me.SessaoFSM(s).faturar()

    def test_caso8_jose_com_evolucao_aceita(self):
        s = S(1, 1, HELENA, status=me.REALIZADA, paciente=3)
        me.SessaoFSM(s).evoluir("Paciente evoluiu bem.")
        f, b = me.classificar_lote([s], CONV)
        self.assertEqual((len(f), len(b)), (1, 0))

    def test_caso9_carla_20min_atendimento_reduzido(self):  # RN-08
        p = pacote(usadas=0)
        s = S(1, 2, SABRINA, paciente=4)
        fsm = me.SessaoFSM(s, p)
        self.assertEqual(fsm.realizar(20), me.REDUZIDO)
        self.assertEqual(pc.saldo(p), 9)  # consome sessão
        f, b = me.classificar_lote([s], CONV)
        self.assertEqual((len(f), len(b)), (0, 1))
        self.assertTrue(b[0]["motivo"].startswith("RN-08"))
        with self.assertRaises(me.BloqueioFaturamento):
            fsm.faturar()

    def test_ciclo_completo_ate_faturada(self):
        s = S(1, 1, HELENA, paciente=3)
        f = me.SessaoFSM(s)
        f.realizar(0); f.evoluir("Ok"); f.faturar()
        self.assertEqual(s["status"], me.FATURADA)

    def test_transicao_invalida_agendada_para_evoluida(self):
        with self.assertRaises(me.TransicaoInvalida):
            me.SessaoFSM(S(1, 1, HELENA)).evoluir("texto")

    def test_atraso_de_15_min_nao_reduz(self):
        s = S(1, 1, HELENA)
        self.assertEqual(me.SessaoFSM(s).realizar(15), me.REALIZADA)

    def test_evolucao_vazia_recusada(self):
        s = S(1, 1, HELENA, status=me.REALIZADA)
        with self.assertRaises(me.EvolucaoObrigatoria):
            me.SessaoFSM(s).evoluir("   ")


class TestOcupacao(unittest.TestCase):
    def setUp(self):
        salas = [{"id": 1, "nome": "Sala 1", "capacidade_simultanea": 1}, {"id": 2, "nome": "Sala 2", "capacidade_simultanea": 1},
                 {"id": 3, "nome": "Sala 3 Pilates", "capacidade_simultanea": 3}]
        profs = [{"id": 1, "nome": "Helena"}, {"id": 2, "nome": "Diego"}, {"id": 3, "nome": "Sabrina"}]
        ss = [S(1, 1, HELENA, datetime(2026, 11, 2, 9)), S(2, 1, SABRINA, datetime(2026, 11, 2, 11)),
              S(3, 3, HELENA), S(4, 3, DIEGO), S(5, 3, SABRINA)]
        d = date(2026, 11, 2)
        self.r = me.calcular_ocupacao(ss, salas, profs, d, d)

    def test_caso10_taxa_por_sala(self):
        self.assertEqual([x["ocupacao_pct"] for x in self.r["por_sala"]], [20.0, 0.0, 10.0])

    def test_caso10_taxa_por_profissional(self):
        self.assertEqual([x["ocupacao_pct"] for x in self.r["por_profissional"]], [20.0, 10.0, 20.0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
