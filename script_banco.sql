-- ============================================================
-- SIFSM - Aurora Siger | script_banco.sql
-- Dialeto: SQLite (banco equivalente ao Oracle).
-- Para Oracle: trocar INTEGER PRIMARY KEY AUTOINCREMENT por
--   NUMBER GENERATED ALWAYS AS IDENTITY, TEXT por VARCHAR2(n), REAL por NUMBER.
-- ============================================================
DROP TABLE IF EXISTS alertas;
DROP TABLE IF EXISTS chamados;
DROP TABLE IF EXISTS leituras;
DROP TABLE IF EXISTS sensores;
DROP TABLE IF EXISTS modulos;

CREATE TABLE modulos (
    id_modulo           TEXT PRIMARY KEY,
    nome                TEXT NOT NULL,
    tipo                TEXT NOT NULL,
    critico             INTEGER NOT NULL CHECK (critico IN (0,1)),
    ativo               INTEGER NOT NULL CHECK (ativo IN (0,1)),
    potencia_nominal_kw REAL NOT NULL CHECK (potencia_nominal_kw > 0)
);

CREATE TABLE sensores (
    codigo_sensor TEXT PRIMARY KEY,
    id_modulo     TEXT NOT NULL REFERENCES modulos(id_modulo),
    tipo_sensor   TEXT NOT NULL
);

CREATE TABLE leituras (
    id_leitura       INTEGER PRIMARY KEY AUTOINCREMENT,
    ciclo            INTEGER NOT NULL CHECK (ciclo >= 0),
    id_modulo        TEXT NOT NULL REFERENCES modulos(id_modulo),
    codigo_sensor    TEXT NOT NULL REFERENCES sensores(codigo_sensor),
    ocupantes        INTEGER NOT NULL CHECK (ocupantes >= 0),
    temperatura_c    REAL NOT NULL,
    umidade_pct      REAL NOT NULL CHECK (umidade_pct BETWEEN 0 AND 100),
    luminosidade_lux REAL NOT NULL CHECK (luminosidade_lux >= 0),
    consumo_kwh      REAL NOT NULL CHECK (consumo_kwh >= 0),
    status_sensor    TEXT NOT NULL CHECK (status_sensor IN ('OK','INVALIDO'))
);

CREATE TABLE alertas (
    id_alerta INTEGER PRIMARY KEY AUTOINCREMENT,
    id_modulo TEXT NOT NULL REFERENCES modulos(id_modulo),
    ciclo     INTEGER NOT NULL,
    nivel     INTEGER NOT NULL,          -- 1 = mais grave
    mensagem  TEXT NOT NULL
);

CREATE TABLE chamados (
    id_chamado INTEGER PRIMARY KEY AUTOINCREMENT,
    id_modulo  TEXT NOT NULL REFERENCES modulos(id_modulo),
    descricao  TEXT NOT NULL,
    prioridade INTEGER NOT NULL DEFAULT 3,
    status     TEXT NOT NULL DEFAULT 'ABERTO' CHECK (status IN ('ABERTO','ATENDIDO'))
);

INSERT INTO modulos VALUES ('M01','Energia','energia',1,1,6);
INSERT INTO modulos VALUES ('M02','Habitação','habitacao',1,1,10);
INSERT INTO modulos VALUES ('M03','Agricultura','agricultura',1,1,12);
INSERT INTO modulos VALUES ('M04','Laboratório','laboratorio',0,1,8);
INSERT INTO modulos VALUES ('M05','Comunicação','comunicacao',0,1,5);
INSERT INTO modulos VALUES ('M06','Suporte Médico','medico',1,1,9);

INSERT INTO sensores VALUES ('SNS-M01','M01','multissensor');
INSERT INTO sensores VALUES ('SNS-M02','M02','multissensor');
INSERT INTO sensores VALUES ('SNS-M03','M03','multissensor');
INSERT INTO sensores VALUES ('SNS-M04','M04','multissensor');
INSERT INTO sensores VALUES ('SNS-M05','M05','multissensor');
INSERT INTO sensores VALUES ('SNS-M06','M06','multissensor');
