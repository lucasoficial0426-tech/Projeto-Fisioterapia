"""API REST — Sessão (Clínica Reabilita).
Executar:  cd backend && DATABASE_URL=postgresql://user:pw@localhost/sessao uvicorn app:app --reload
Requer: pip install fastapi uvicorn psycopg2-binary
"""
import os
from contextlib import contextmanager
from datetime import date, datetime
from typing import Optional

import psycopg2
import psycopg2.errors
import psycopg2.extras
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import maquina_estados as me
import pacotes_controller as pc

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/sessao")
app = FastAPI(title="Sessão — Clínica Reabilita")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@contextmanager
def db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        yield conn.cursor()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@app.exception_handler(pc.ErroRegra)
async def _regra(_, exc):
    return JSONResponse(status_code=409, content={"codigo": exc.codigo, "detail": str(exc)})


@app.exception_handler(psycopg2.errors.UniqueViolation)
async def _unico(_, exc):
    return JSONResponse(status_code=409, content={"codigo": "UNICO", "detail": "Registro duplicado ou conflito de horário (RN-05)."})


@app.exception_handler(psycopg2.errors.ForeignKeyViolation)
async def _fk(_, exc):
    return JSONResponse(status_code=422, content={"codigo": "FK", "detail": "Referência inexistente."})


class PacienteIn(BaseModel):
    nome: str
    tipo: str = Field(pattern="^(Particular|Convenio)$")
    convenio_nome: Optional[str] = None
    cpf: str
    data_inicio: date


class ProfissionalIn(BaseModel):
    nome: str
    tipo: str = Field(pattern="^(Socio|Contratado)$")
    cpf: str


class SalaIn(BaseModel):
    nome: str
    capacidade_simultanea: int = Field(ge=1)


class PacoteIn(BaseModel):
    paciente_id: int
    data_compra: date


class SessaoIn(BaseModel):
    paciente_id: int
    profissional_id: int
    sala_id: int
    data_hora: datetime


class AtendimentoIn(BaseModel):
    atraso_minutos: int = Field(default=0, ge=0)


class EvolucaoIn(BaseModel):
    texto: str


def _listar(sql, params=()):
    with db() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


# ---------- Cadastros ----------
@app.get("/pacientes")
def listar_pacientes():
    return _listar("SELECT * FROM paciente ORDER BY nome")


@app.post("/pacientes", status_code=201)
def criar_paciente(d: PacienteIn):
    conv = (d.convenio_nome or "").strip() or None
    if d.tipo == "Convenio" and not conv:
        raise HTTPException(422, "Informe o nome do convênio.")
    if d.tipo == "Particular":
        conv = None
    with db() as cur:
        cur.execute("INSERT INTO paciente (nome,tipo,convenio_nome,cpf,data_inicio) VALUES (%s,%s,%s,%s,%s) RETURNING *",
                    (d.nome, d.tipo, conv, d.cpf, d.data_inicio))
        return cur.fetchone()


@app.get("/profissionais")
def listar_profissionais():
    return _listar("SELECT * FROM profissional ORDER BY nome")


@app.post("/profissionais", status_code=201)
def criar_profissional(d: ProfissionalIn):
    with db() as cur:
        cur.execute("INSERT INTO profissional (nome,tipo,cpf) VALUES (%s,%s,%s) RETURNING *", (d.nome, d.tipo, d.cpf))
        return cur.fetchone()


@app.get("/salas")
def listar_salas():
    return _listar("SELECT * FROM sala ORDER BY id")


@app.post("/salas", status_code=201)
def criar_sala(d: SalaIn):
    with db() as cur:
        cur.execute("INSERT INTO sala (nome,capacidade_simultanea) VALUES (%s,%s) RETURNING *", (d.nome, d.capacidade_simultanea))
        return cur.fetchone()


# ---------- Pacotes ----------
@app.get("/pacotes")
def listar_pacotes():
    return _listar("SELECT k.*, p.nome AS paciente_nome FROM pacote k JOIN paciente p ON p.id=k.paciente_id ORDER BY k.data_compra DESC")


@app.post("/pacotes", status_code=201)
def vender_pacote(d: PacoteIn):
    with db() as cur:
        cur.execute("SELECT tipo FROM paciente WHERE id=%s", (d.paciente_id,))
        p = cur.fetchone()
        if not p:
            raise HTTPException(404, "Paciente não encontrado.")
        if p["tipo"] != "Particular":
            raise HTTPException(422, "Pacotes são vendidos apenas para pacientes particulares.")
        n = pc.novo_pacote(d.paciente_id, d.data_compra)  # RN-01
        cur.execute("INSERT INTO pacote (paciente_id,data_compra,sessoes_totais,sessoes_usadas,validade_dias,status) "
                    "VALUES (%(paciente_id)s,%(data_compra)s,%(sessoes_totais)s,%(sessoes_usadas)s,%(validade_dias)s,%(status)s) RETURNING *", n)
        return cur.fetchone()


# ---------- Agenda ----------
@app.get("/agenda")
def agenda(data: date):
    return _listar("""SELECT s.*, p.nome AS paciente_nome, pr.nome AS profissional_nome, sa.nome AS sala_nome
        FROM sessao s JOIN paciente p ON p.id=s.paciente_id JOIN profissional pr ON pr.id=s.profissional_id
        JOIN sala sa ON sa.id=s.sala_id WHERE s.data_hora::date=%s ORDER BY s.data_hora""", (data,))


@app.post("/sessoes", status_code=201)
def agendar(d: SessaoIn):
    with db() as cur:
        cur.execute("SELECT * FROM paciente WHERE id=%s", (d.paciente_id,))
        pac = cur.fetchone()
        if not pac:
            raise HTTPException(404, "Paciente não encontrado.")
        cur.execute("SELECT id, capacidade_simultanea FROM sala")
        salas = {r["id"]: r["capacidade_simultanea"] for r in cur.fetchall()}
        if d.sala_id not in salas:
            raise HTTPException(404, "Sala não encontrada.")
        cur.execute("SELECT * FROM sessao WHERE data_hora=%s", (d.data_hora,))
        me.validar_agendamento_sessao(cur.fetchall(), salas, d.sala_id, d.profissional_id, d.data_hora)  # RN-04/05
        pacote_id = None
        if pac["tipo"] == "Particular":  # RN-07
            cur.execute("SELECT * FROM pacote WHERE paciente_id=%s", (pac["id"],))
            pacote_id = pc.escolher_pacote_valido(cur.fetchall(), d.data_hora.date())["id"]
        cur.execute("INSERT INTO sessao (paciente_id,profissional_id,sala_id,pacote_id,data_hora) VALUES (%s,%s,%s,%s,%s) RETURNING *",
                    (d.paciente_id, d.profissional_id, d.sala_id, pacote_id, d.data_hora))
        return cur.fetchone()


def _acao(sid, fn):
    with db() as cur:
        cur.execute("SELECT * FROM sessao WHERE id=%s FOR UPDATE", (sid,))
        s = cur.fetchone()
        if not s:
            raise HTTPException(404, "Sessão não encontrada.")
        pac = None
        if s["pacote_id"]:
            cur.execute("SELECT * FROM pacote WHERE id=%s FOR UPDATE", (s["pacote_id"],))
            pac = cur.fetchone()
        fn(me.SessaoFSM(s, pac))
        cur.execute("UPDATE sessao SET status=%s, evolucao_clinica=%s, atraso_minutos=%s WHERE id=%s",
                    (s["status"], s["evolucao_clinica"], s["atraso_minutos"], sid))
        if pac:
            novo = "Esgotado" if pc.saldo(pac) <= 0 else pac["status"]
            cur.execute("UPDATE pacote SET sessoes_usadas=%s, status=%s WHERE id=%s", (pac["sessoes_usadas"], novo, pac["id"]))
        return s


@app.post("/sessoes/{sid}/realizar")
def realizar(sid: int, d: AtendimentoIn):
    return _acao(sid, lambda f: f.realizar(d.atraso_minutos))


@app.post("/sessoes/{sid}/falta")
def falta(sid: int):
    return _acao(sid, lambda f: f.registrar_falta())


@app.post("/sessoes/{sid}/cancelar")
def cancelar(sid: int):
    return _acao(sid, lambda f: f.cancelar(datetime.now()))


@app.post("/sessoes/{sid}/evolucao")
def evolucao(sid: int, d: EvolucaoIn):
    return _acao(sid, lambda f: f.evoluir(d.texto))


# ---------- Lote de convênio ----------
def _lote(cur):
    cur.execute("""SELECT s.*, p.nome AS paciente_nome, p.convenio_nome FROM sessao s JOIN paciente p ON p.id=s.paciente_id
        WHERE p.tipo='Convenio' AND s.status IN ('Realizada','Evoluída','Atendimento reduzido') ORDER BY s.data_hora""")
    rows = cur.fetchall()
    return me.classificar_lote(rows, {r["paciente_id"]: {"tipo": "Convenio"} for r in rows})


@app.get("/convenio/lote")
def lote():
    with db() as cur:
        f, b = _lote(cur)
        return {"faturaveis": f, "bloqueadas": b}


@app.post("/convenio/lote/faturar")
def faturar_lote():
    with db() as cur:
        f, _ = _lote(cur)
        for s in f:
            me.SessaoFSM(s).faturar()
            cur.execute("UPDATE sessao SET status=%s WHERE id=%s", (s["status"], s["id"]))
        return {"faturadas": len(f)}


# ---------- Relatório ----------
@app.get("/relatorios/ocupacao")
def ocupacao(inicio: date, fim: date):
    with db() as cur:
        cur.execute("SELECT * FROM sala ORDER BY id"); salas = cur.fetchall()
        cur.execute("SELECT id, nome FROM profissional ORDER BY nome"); profs = cur.fetchall()
        cur.execute("SELECT * FROM sessao WHERE data_hora::date BETWEEN %s AND %s", (inicio, fim))
        return me.calcular_ocupacao(cur.fetchall(), salas, profs, inicio, fim)


_front = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(_front):
    app.mount("/", StaticFiles(directory=_front, html=True), name="frontend")
