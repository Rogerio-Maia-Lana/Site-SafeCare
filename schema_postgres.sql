CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    senha VARCHAR(255) NOT NULL,
    tipo VARCHAR(20) NOT NULL CHECK (tipo IN ('cuidador', 'familiar')),
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pacientes (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    idade INT NULL,
    observacoes TEXT NULL,
    cuidador_id INT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS autorizacoes (
    id SERIAL PRIMARY KEY,
    paciente_id INT NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    familiar_id INT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_autorizacao UNIQUE (paciente_id, familiar_id)
);

CREATE TABLE IF NOT EXISTS solicitacoes_autorizacao (
    id SERIAL PRIMARY KEY,
    paciente_id INT NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    remetente_id INT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    destinatario_id INT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    mensagem TEXT NULL,
    status VARCHAR(20) DEFAULT 'pendente' CHECK (status IN ('pendente', 'aceita', 'recusada')),
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    respondido_em TIMESTAMP NULL DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS tarefas (
    id SERIAL PRIMARY KEY,
    paciente_id INT NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    descricao VARCHAR(255) NOT NULL,
    tipo VARCHAR(50) DEFAULT 'rotina',
    data DATE NOT NULL,
    concluida BOOLEAN DEFAULT FALSE,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ocorrencias (
    id SERIAL PRIMARY KEY,
    paciente_id INT NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    descricao TEXT NOT NULL,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notificacoes (
    id SERIAL PRIMARY KEY,
    usuario_id INT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    titulo VARCHAR(150) NOT NULL,
    mensagem TEXT NOT NULL,
    tipo VARCHAR(50) NOT NULL,
    lida BOOLEAN DEFAULT FALSE,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_usuario_tipo ON usuarios(tipo);
CREATE INDEX IF NOT EXISTS idx_paciente_cuidador ON pacientes(cuidador_id);
CREATE INDEX IF NOT EXISTS idx_aut_familiar ON autorizacoes(familiar_id);
CREATE INDEX IF NOT EXISTS idx_sol_destinatario ON solicitacoes_autorizacao(destinatario_id);
CREATE INDEX IF NOT EXISTS idx_sol_remetente ON solicitacoes_autorizacao(remetente_id);
CREATE INDEX IF NOT EXISTS idx_tarefa_paciente ON tarefas(paciente_id);
CREATE INDEX IF NOT EXISTS idx_tarefa_data ON tarefas(data);
CREATE INDEX IF NOT EXISTS idx_tarefa_tipo ON tarefas(tipo);
CREATE INDEX IF NOT EXISTS idx_ocorrencia_paciente ON ocorrencias(paciente_id);
CREATE INDEX IF NOT EXISTS idx_ocorrencia_data ON ocorrencias(criado_em);
CREATE INDEX IF NOT EXISTS idx_not_usuario ON notificacoes(usuario_id);
