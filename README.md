# Sessão — Clínica Reabilita (Squad NSMT)

Agenda, pacotes de sessões e faturamento de convênios.

- `sql/` esquema PostgreSQL (3FN) e dados iniciais
- `backend/` API FastAPI + regras (máquina de estados e pacotes)
- `frontend/` 7 telas (HTML + Tailwind + JS). Para ver sem banco: `frontend/index.html?demo=1`
- `testes/` 22 testes: `python testes/testes.py`

Rodar completo: `psql sessao -f sql/01_ddl_schema.sql -f sql/02_seed_data.sql`, depois em `backend/`:
`pip install fastapi uvicorn psycopg2-binary` e `DATABASE_URL=postgresql://user:senha@localhost/sessao uvicorn app:app --reload`.


Abra as 7 telas

Acesse este endereço, com o ?demo=1 no final:

https://lucasoficial0426-tech.github.io/Projeto-Fisioterapia/frontend/index.html?demo=1
