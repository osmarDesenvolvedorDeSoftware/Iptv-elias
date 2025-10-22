# Roteiro de Validação Ponta a Ponta IPTV

## Objetivo
Garantir que o fluxo completo do sistema IPTV — englobando importação, processamento assíncrono, armazenamento persistente, interface web e métricas — funcione de forma integrada executando diretamente no host (Flask + Celery + Redis + MariaDB remota) gerenciados pelo PM2 e com frontend Vite React.

---

## 1. Preparação do Ambiente
1. **Clonar o repositório**
   ```bash
   git clone <URL_DO_REPOSITORIO>
   cd Iptv-elias
   ```
2. **Configurar variáveis de ambiente**
   ```bash
   cp backend/.env.example .env
   ```
   Ajuste `SQLALCHEMY_DATABASE_URI` para o host remoto e mantenha `REDIS_URL=redis://localhost:6379/0`.
3. **Instalar dependências e iniciar processos**
   ```bash
   python3.11 -m venv venv
   source venv/bin/activate
   pip install --upgrade pip
   pip install -r backend/requirements.txt
   sudo mkdir -p /var/log/iptv-elias && sudo chown $(whoami) /var/log/iptv-elias
   pm2 start ecosystem.config.js
   pm2 save && pm2 startup
   ```
4. **Monitorar inicialização**
   - Execute `pm2 status` e aguarde `backend-api` e `backend-worker` como `online`.
   - Use `pm2 logs backend-api`/`pm2 logs backend-worker` para validar carregamento.
5. **Health check inicial da API**
   ```bash
   curl http://localhost:5000/health
   ```
   - **Resultado esperado:** `{"status":"ok"}` com chaves `database`, `redis` e `celery` sinalizando sucesso.

---

## 2. Login no Frontend
1. Abrir `http://localhost:5173` no navegador.
2. Autenticar com credenciais seed:
   - Email: `admin@tenant.com`
   - Senha: `admin123`
3. **Validações:**
   - Redirecionamento automático para `/importacao`.
   - Sessão ativa (token no storage) e ausência de erros de rede.

---

## 3. Importação de Conteúdo
1. Na tela `/importacao`:
   - Clicar em **"Rodar agora"** na seção **Filmes**.
   - Repetir o processo para **Séries**.
2. **Monitoramento no frontend:**
   - Status deve evoluir de `idle` → `running` → `finished` para cada job.
   - O painel deve exibir timestamps e contadores atualizados.
3. **Validação de logs pelo frontend:**
   - Navegar para `/logs`.
   - Confirmar que os registros exibem as colunas/campos: `source_tag`, `source_tag_filmes`, `dominio`, `adult`, `dedupe`.
   - Verificar que os logs recém-criados aparecem com `status` coerente e mensagens legíveis.

---

## 4. Bouquets
1. Acessar `/bouquets`.
2. **Validações:**
   - Listagem principal deve apresentar filmes e séries importados.
   - Criar um novo bouquet (ex.: “Teste QA”) arrastando alguns itens importados.
   - Salvar alterações e confirmar toast de sucesso.
3. **Persistência:**
   - Atualizar a página ou reabrir `/bouquets` em nova aba.
   - Confirmar que o bouquet criado e a ordem/seleção permanecem intactos.

---

## 5. Configurações
1. Navegar até `/config`.
2. Ajustar parâmetros (ex.: idioma do TMDb, delays de importação) e salvar.
3. **Validações:**
   - Visualizar alerta “requer reinício” ou mensagem equivalente.
   - Recarregar a página ou navegar para outra rota e retornar.
   - Confirmar que os valores editados continuam aplicados.

---

## 6. Métricas e Dashboard
1. Acessar a rota de dashboard via frontend (cards em `/metrics/dashboard` ou seção equivalente no painel principal).
2. Confirmar que os cards exibem contagens atualizadas de:
   - Filmes
   - Séries
   - Jobs (por status)
   - Erros recentes
3. **Validação via API:**
   - Obter token JWT atual do storage do navegador.
   - Executar:
     ```bash
    curl http://localhost:5000/metrics/dashboard \
       -H "Authorization: Bearer <token>" \
       -H "X-Tenant-ID: tenant-demo"
     ```
   - Comparar os valores retornados com o que é mostrado no frontend.

---

## 7. Health Check Completo
1. Realizar nova chamada para o endpoint de health detalhado:
   ```bash
  curl http://localhost:5000/health
   ```
2. **Resultado esperado:**
   ```json
   {
     "status": "ok",
     "database": "ok",
     "redis": "ok",
     "celery": "ok"
   }
   ```

---

## 8. Logs e Banco de Dados
1. Conectar diretamente ao banco remoto (utilize as mesmas credenciais do `.env`):
   ```bash
   mysql -h <host-remoto> -u<usuario> -p<senha> <database>
   ```
2. **Consultas de verificação:**
   ```sql
   SHOW TABLES;
   SELECT COUNT(*) FROM streams;
   SELECT COUNT(*) FROM jobs WHERE status='finished';
   SELECT DISTINCT source_tag, source_tag_filmes FROM jobs LIMIT 20;
   ```
3. **Validações:**
   - Tabelas principais (`streams`, `jobs`, `bouquets`, etc.) presentes.
   - `COUNT(*)` consistente com importações executadas.
   - Colunas `source_tag` e `source_tag_filmes` preenchidas.

---

## 9. Verificações no Frontend
1. Alternar tema claro/escuro via UI.
   - Confirmar persistência no `localStorage` (verificar em DevTools → Application → Local Storage → chave do tema).
2. Abrir modal de detalhes de log e validar que os metadados legados (ex.: identificadores externos, status dedupe) são exibidos.
3. Interagir com toasts e navegação entre páginas (`/importacao`, `/bouquets`, `/logs`, `/config`).
   - Garantir ausência de erros de rede (monitorar via DevTools Network).

---

## 10. Finalização e Persistência
1. Reiniciar os processos gerenciados pelo PM2:
   ```bash
   pm2 restart backend-api
   pm2 restart backend-worker
   ```
2. Repetir verificações rápidas:
   - Acessar `/bouquets` e `/config` para garantir que configurações e bouquets permanecem.
   - Conferir `/metrics/dashboard` para validar métricas persistidas.
   - Checar `/logs` para confirmar histórico intacto.

---

## Resultado Esperado
- Importadores executam com sucesso e registram logs completos (incluindo deduplicação, marcação adulto e origem).
- Bouquets e configurações persistem entre sessões e reinicializações de containers.
- Dashboard apresenta métricas consistentes com a base de dados.
- Health check reporta todos os serviços como “ok”.
- SPA comunica-se com a API sem erros de CORS ou autenticação.
