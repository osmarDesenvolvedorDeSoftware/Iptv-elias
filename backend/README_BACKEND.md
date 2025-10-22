# Backend IPTV - Fase B1C

Backend mínimo viável em Flask para atender ao front IPTV.

## Requisitos

- Ubuntu 24.04 LTS (ou compatível)
- Python 3.11 + `python3-venv`
- Redis Server 7+
- Banco MariaDB/MySQL remoto acessível a partir do IP público da VPS
- Node.js + PM2 (`npm install -g pm2`)

## Preparar o ambiente

1. Instale dependências de sistema e o Redis nativo:
   ```bash
   sudo apt update
   sudo apt install -y python3.11 python3.11-venv redis-server build-essential libffi-dev
   sudo systemctl enable --now redis-server
   ```
2. Clone o repositório e copie as variáveis padrão:
   ```bash
   git clone <URL_DO_REPOSITORIO>
   cd Iptv-elias
   cp backend/.env.example .env
   ```
3. Crie o virtualenv e instale as dependências Python:
   ```bash
   python3.11 -m venv venv
   source venv/bin/activate
   pip install --upgrade pip
   pip install -r backend/requirements.txt
   ```
4. Edite `.env` com as credenciais do banco remoto e demais segredos. Os campos principais são:
   - `SQLALCHEMY_DATABASE_URI=mysql+pymysql://<usuario>:<senha>@<host-remoto>:3306/<database>`
   - `REDIS_URL=redis://localhost:6379/0`
   - `CELERY_BROKER_URL=redis://localhost:6379/0`
   - `CELERY_RESULT_BACKEND=redis://localhost:6379/0`

   O backend já carrega esse arquivo automaticamente (`app/config.py`).

## Migrações do banco principal

1. Garanta que o virtualenv esteja ativo (`source venv/bin/activate`).
2. Aplique as migrações SQLAlchemy/Alembic:
   ```bash
   cd backend
   ../venv/bin/alembic upgrade head
   cd ..
   ```

## Testar a conexão com o banco remoto

Execute o helper interno diretamente no host (fora do Docker):
```bash
source venv/bin/activate
cd backend
../venv/bin/python -c "from app.services.settings import _test_db_connection; _test_db_connection('<host-remoto>', 3306, '<usuario>', '<senha>', '<database>')"
cd ..
```

A mensagem `Access denied` ou erros de SSL indicam que o banco não está aceitando o IP atual. Conexões bem-sucedidas retornam `None` silenciosamente.

## Execução com PM2

1. Certifique-se de que o diretório de logs exista:
   ```bash
   sudo mkdir -p /var/log/iptv-elias
   sudo chown $(whoami):$(whoami) /var/log/iptv-elias
   ```
2. Inicie os processos definidos em `ecosystem.config.js`:
   ```bash
   pm2 start ecosystem.config.js
   pm2 status
   ```
3. Persista a configuração e habilite o autostart:
   ```bash
   pm2 save
   pm2 startup systemd
   ```
4. Comandos úteis:
   ```bash
   pm2 restart backend-api
   pm2 restart backend-worker
   pm2 logs backend-api
   pm2 logs backend-worker
   ```

- A API Flask fica disponível em `http://localhost:5000` (exposta ao Nginx reverso).
- Logs JSON da API e do worker são gravados em `/var/log/iptv-elias/*.log` com rotação (`max_size`/`retain`).

## Health check e debug rápido

- Health check:
  ```bash
  curl http://localhost:5000/health
  ```
- Script auxiliar `tabela.py` (ex.: inspecionar tabelas XUI):
  ```bash
  source venv/bin/activate
  python tabela.py
  ```

## Estrutura de pastas

```
backend/
  app/
    api/
    config.py
    extensions.py
    __main__.py
    models/
    services/
    tasks/
  migrations/
  requirements.txt
  alembic.ini
```

## Notas

- A autenticação utiliza JWT (Flask-JWT-Extended) com tokens de acesso e refresh.
- Redis local (`localhost:6379`) é compartilhado entre a API e o worker Celery.
- Ajuste `LOG_LEVEL` no `.env` para controlar a verbosidade dos logs (stdout + arquivos gerenciados pelo PM2).
