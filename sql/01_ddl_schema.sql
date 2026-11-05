-- Sessão — Clínica Reabilita | Esquema PostgreSQL (3FN)
CREATE TABLE paciente (
  id            SERIAL PRIMARY KEY,
  nome          VARCHAR(120) NOT NULL,
  tipo          VARCHAR(10)  NOT NULL CHECK (tipo IN ('Particular','Convenio')),
  convenio_nome VARCHAR(80),
  cpf           VARCHAR(14)  NOT NULL UNIQUE,
  data_inicio   DATE NOT NULL DEFAULT CURRENT_DATE,
  CONSTRAINT ck_convenio CHECK ((tipo = 'Convenio' AND convenio_nome IS NOT NULL)
                             OR (tipo = 'Particular' AND convenio_nome IS NULL))
);

CREATE TABLE profissional (
  id   SERIAL PRIMARY KEY,
  nome VARCHAR(120) NOT NULL,
  tipo VARCHAR(10)  NOT NULL CHECK (tipo IN ('Socio','Contratado')),
  cpf  VARCHAR(14)  NOT NULL UNIQUE
);

CREATE TABLE sala (
  id                    SERIAL PRIMARY KEY,
  nome                  VARCHAR(60) NOT NULL UNIQUE,
  capacidade_simultanea INT NOT NULL CHECK (capacidade_simultanea >= 1)
);

CREATE TABLE pacote (
  id             SERIAL PRIMARY KEY,
  paciente_id    INT  NOT NULL REFERENCES paciente(id),
  data_compra    DATE NOT NULL,
  sessoes_totais INT  NOT NULL CHECK (sessoes_totais IN (10,15)),
  sessoes_usadas INT  NOT NULL DEFAULT 0,
  validade_dias  INT  NOT NULL CHECK (validade_dias IN (90,120)),
  status         VARCHAR(10) NOT NULL DEFAULT 'Ativo' CHECK (status IN ('Ativo','Expirado','Esgotado')),
  CONSTRAINT ck_usadas CHECK (sessoes_usadas >= 0 AND sessoes_usadas <= sessoes_totais)
);

CREATE TABLE sessao (
  id               SERIAL PRIMARY KEY,
  paciente_id      INT NOT NULL REFERENCES paciente(id),
  profissional_id  INT NOT NULL REFERENCES profissional(id),
  sala_id          INT NOT NULL REFERENCES sala(id),
  pacote_id        INT REFERENCES pacote(id),
  data_hora        TIMESTAMP NOT NULL,
  status           VARCHAR(25) NOT NULL DEFAULT 'Agendada'
    CHECK (status IN ('Agendada','Realizada','Evoluída','Faturada',
                      'Falta sem aviso','Cancelada com aviso','Atendimento reduzido')),
  evolucao_clinica TEXT,
  atraso_minutos   INT NOT NULL DEFAULT 0 CHECK (atraso_minutos >= 0)
);

-- RN-05 também garantida no banco: profissional não pode ter 2 sessões ativas no mesmo horário
CREATE UNIQUE INDEX ux_sessao_prof_horario ON sessao (profissional_id, data_hora)
  WHERE status <> 'Cancelada com aviso';
CREATE INDEX ix_sessao_data ON sessao (data_hora);
CREATE INDEX ix_pacote_paciente ON pacote (paciente_id);
