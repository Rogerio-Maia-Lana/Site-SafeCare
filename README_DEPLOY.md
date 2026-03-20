# Deploy grátis do SafeCare (Render + Neon)

## 1) No Neon
- Crie um projeto PostgreSQL.
- Copie a connection string.
- Use o nome completo em `DATABASE_URL`.

## 2) No GitHub
- Suba esta pasta inteira para um repositório.

## 3) No Render
- New + Web Service
- Conecte o repositório
- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn app:app`

## 4) Variáveis de ambiente no Render
- `DATABASE_URL` = string do Neon
- `SECRET_KEY` = qualquer chave secreta forte

## 5) Logins padrão criados automaticamente
- Cuidador: `cuidador@gmail.com` / `123456`
- Familiar: `familiar@gmail.com` / `123456`
