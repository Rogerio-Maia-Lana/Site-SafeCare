# SafeCare

Projeto Flask + MySQL com:

- separação de CSS em `base.css`, `home.css`, `auth.css` e `dashboard.css`
- CRUD de pacientes
- CRUD de tarefas com filtro por data, tipo e status
- ocorrências
- solicitações de autorização entre cuidador e familiar
- notificações internas
- relatórios simples diário, semanal e mensal

## Como rodar

1. Crie o banco com o arquivo `safecare.sql` no MySQL Workbench.
2. Ajuste as credenciais em `database.py` ou use variáveis de ambiente.
3. Instale as dependências:

```bash
pip install -r rq.txt
```

4. Execute:

```bash
python app.py
```

## Observação

Se você já tiver um banco antigo do SafeCare, o mais seguro é recriar o schema com o `safecare.sql` atualizado porque agora existem novas tabelas e a coluna `tipo` em `tarefas`.
