# KlinikDeutsch

Plataforma de treino de alemão médico com foco em contexto real de plantão (A1/B1/C1), análise linguística com spaCy e geração/avaliação assistida por LLM (Grok 4.1).

## Visão geral

O KlinikDeutsch permite:
- autenticação por sessão (usuário obrigatório para usar a API);
- roleta de casos clínicos por nível CEFR (A1, B1, C1);
- análise de texto alemão com tokenização e contexto gramatical;
- geração de cards e treino SRS por usuário;
- histórico de eventos de estudo (cliques, tentativas de tradução e revisões).

### Perfis e níveis

A aplicação já suporta perfis com nível padrão:
- `marcos` → C1
- `caio` → B1
- `thais` → A1

No frontend, o usuário pode alternar o nível da roleta para explorar frases de outros níveis sem perder o histórico de flashcards vinculado à própria conta.

---

## Stack

- **Backend:** Django + Django REST Framework
- **Frontend:** React (Vite)
- **NLP:** spaCy (`de_core_news_lg`)
- **LLM:** xAI Grok 4.1 (endpoint compatível OpenAI SDK)
- **Banco:** PostgreSQL
- **Deploy:** Docker + Docker Compose + Gunicorn + WhiteNoise

---

## Como funciona no uso diário

1. Usuário faz login na aplicação.
2. Frontend carrega frases do nível selecionado via `/api/scenarios/`.
3. Ao analisar uma frase, o backend:
   - cria o documento;
   - disseca tokens com spaCy;
   - persiste relações gramaticais.
4. Ao clicar em palavras, o sistema gera conteúdo de estudo e cria/atualiza cards SRS do usuário.
5. No treino diário, respostas atualizam retenção e próxima revisão por card.

Tudo é persistido no PostgreSQL por usuário autenticado.

---

## Configuração de ambiente

### 1) Crie o arquivo `.env`

Use o `.env.example` como base:

```bash
cp .env.example .env
```

Campos principais:
- `SECRET_KEY`
- `DATABASE_URL`
- `LLM_API_KEY`
- `DJANGO_DEBUG`
- `DJANGO_SECURE_SSL`
- `CSRF_TRUSTED_ORIGINS`

### 2) Backend local (sem Docker)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download de_core_news_lg
python manage.py migrate
python manage.py runserver 127.0.0.1:8001
```

### 3) Frontend local

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

---

## Docker (produção)

Arquivos de deploy incluídos:
- `Dockerfile`
- `docker-compose.yml`
- `deploy.sh`

Subida padrão:

```bash
docker compose build
docker compose up -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py collectstatic --noinput
```

A aplicação web fica exposta na porta `8050` (proxy reverso recomendado no Nginx para `mnrs.com.br`).

---

## Segurança

- Sessão obrigatória para endpoints da API.
- Cookies de sessão/CSRF seguros em produção.
- `ALLOWED_HOSTS` restrito.
- Segredos via variáveis de ambiente.
- Arquivos sensíveis ignorados por `.gitignore`.

---

## Comandos úteis

Popular cenários CEFR no banco:

```bash
python manage.py seed_clinical_scenarios --reset
```

Criar usuários base (A1/B1/C1):

```bash
python manage.py bootstrap_users
```

Verificar projeto:

```bash
python manage.py check
```
