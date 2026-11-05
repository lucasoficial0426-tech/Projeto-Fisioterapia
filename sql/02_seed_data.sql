-- Dados iniciais sanitizados (CPFs fictícios)
INSERT INTO sala (id, nome, capacidade_simultanea) VALUES
 (1,'Sala 1',1),(2,'Sala 2',1),(3,'Sala 3 Pilates',3);

INSERT INTO profissional (id, nome, tipo, cpf) VALUES
 (1,'Helena','Socio','000.000.000-01'),
 (2,'Diego','Contratado','000.000.000-02'),
 (3,'Sabrina','Contratado','000.000.000-03');

INSERT INTO paciente (id, nome, tipo, convenio_nome, cpf, data_inicio) VALUES
 (1,'Marta','Particular',NULL,'111.111.111-01','2026-06-01'),
 (2,'Ricardo','Particular',NULL,'111.111.111-02','2026-11-02'),
 (3,'José','Convenio','Unimed','111.111.111-03','2026-09-10'),
 (4,'Carla','Convenio','Bradesco Saúde','111.111.111-04','2026-10-01');

-- id 2 = "P-02" (expirado). id 3 = Marta com saldo 3. id 1 = pacote novo (15/120).
INSERT INTO pacote (id, paciente_id, data_compra, sessoes_totais, sessoes_usadas, validade_dias, status) VALUES
 (1,2,'2026-11-02',15,2,120,'Ativo'),
 (2,1,'2026-06-01',10,7,90,'Expirado'),
 (3,1,'2026-10-15',10,7,90,'Ativo');

INSERT INTO sessao (paciente_id, profissional_id, sala_id, pacote_id, data_hora, status, evolucao_clinica, atraso_minutos) VALUES
 (1,3,1,3,'2026-11-06 10:00','Agendada',NULL,0),
 (2,1,3,1,'2026-11-06 10:00','Agendada',NULL,0),
 (3,1,1,NULL,'2026-11-03 09:00','Realizada',NULL,0),
 (3,2,1,NULL,'2026-11-03 11:00','Evoluída','Boa amplitude de movimento; mantida conduta.',0),
 (4,3,2,NULL,'2026-11-04 14:00','Atendimento reduzido',NULL,20);

SELECT setval(pg_get_serial_sequence('sala','id'),(SELECT MAX(id) FROM sala));
SELECT setval(pg_get_serial_sequence('profissional','id'),(SELECT MAX(id) FROM profissional));
SELECT setval(pg_get_serial_sequence('paciente','id'),(SELECT MAX(id) FROM paciente));
SELECT setval(pg_get_serial_sequence('pacote','id'),(SELECT MAX(id) FROM pacote));
SELECT setval(pg_get_serial_sequence('sessao','id'),(SELECT MAX(id) FROM sessao));
