DROP DATABASE IF EXISTS safecare;
CREATE DATABASE safecare
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE safecare;

CREATE TABLE usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    senha VARCHAR(255) NOT NULL,
    tipo ENUM('cuidador', 'familiar') NOT NULL,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE pacientes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    idade INT NULL,
    observacoes TEXT NULL,
    cuidador_id INT NOT NULL,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_paciente_cuidador FOREIGN KEY (cuidador_id) REFERENCES usuarios(id) ON DELETE CASCADE
);

CREATE TABLE autorizacoes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    paciente_id INT NOT NULL,
    familiar_id INT NOT NULL,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_aut_paciente FOREIGN KEY (paciente_id) REFERENCES pacientes(id) ON DELETE CASCADE,
    CONSTRAINT fk_aut_familiar FOREIGN KEY (familiar_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    CONSTRAINT unique_autorizacao UNIQUE (paciente_id, familiar_id)
);

CREATE TABLE solicitacoes_autorizacao (
    id INT AUTO_INCREMENT PRIMARY KEY,
    paciente_id INT NOT NULL,
    remetente_id INT NOT NULL,
    destinatario_id INT NOT NULL,
    mensagem TEXT NULL,
    status ENUM('pendente', 'aceita', 'recusada') DEFAULT 'pendente',
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    respondido_em TIMESTAMP NULL DEFAULT NULL,
    CONSTRAINT fk_sol_paciente FOREIGN KEY (paciente_id) REFERENCES pacientes(id) ON DELETE CASCADE,
    CONSTRAINT fk_sol_remetente FOREIGN KEY (remetente_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    CONSTRAINT fk_sol_destinatario FOREIGN KEY (destinatario_id) REFERENCES usuarios(id) ON DELETE CASCADE
);

CREATE TABLE tarefas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    paciente_id INT NOT NULL,
    descricao VARCHAR(255) NOT NULL,
    tipo VARCHAR(50) DEFAULT 'rotina',
    data DATE NOT NULL,
    concluida BOOLEAN DEFAULT FALSE,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_tarefa_paciente FOREIGN KEY (paciente_id) REFERENCES pacientes(id) ON DELETE CASCADE
);

CREATE TABLE ocorrencias (
    id INT AUTO_INCREMENT PRIMARY KEY,
    paciente_id INT NOT NULL,
    descricao TEXT NOT NULL,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ocorrencia_paciente FOREIGN KEY (paciente_id) REFERENCES pacientes(id) ON DELETE CASCADE
);

CREATE TABLE notificacoes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    titulo VARCHAR(150) NOT NULL,
    mensagem TEXT NOT NULL,
    tipo VARCHAR(50) NOT NULL,
    lida BOOLEAN DEFAULT FALSE,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_not_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
);

CREATE INDEX idx_usuario_tipo ON usuarios(tipo);
CREATE INDEX idx_paciente_cuidador ON pacientes(cuidador_id);
CREATE INDEX idx_aut_familiar ON autorizacoes(familiar_id);
CREATE INDEX idx_sol_destinatario ON solicitacoes_autorizacao(destinatario_id);
CREATE INDEX idx_sol_remetente ON solicitacoes_autorizacao(remetente_id);
CREATE INDEX idx_tarefa_paciente ON tarefas(paciente_id);
CREATE INDEX idx_tarefa_data ON tarefas(data);
CREATE INDEX idx_tarefa_tipo ON tarefas(tipo);
CREATE INDEX idx_ocorrencia_paciente ON ocorrencias(paciente_id);
CREATE INDEX idx_ocorrencia_data ON ocorrencias(criado_em);
CREATE INDEX idx_not_usuario ON notificacoes(usuario_id);


-- Usuários de demonstração são criados automaticamente ao iniciar o app.
-- cuidador@gmail.com / 123456 / tipo cuidador
-- familiar@gmail.com / 123456 / tipo familiar
