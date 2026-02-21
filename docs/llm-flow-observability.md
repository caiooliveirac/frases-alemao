# Fluxo LLM (Grok) e Observabilidade

Este documento descreve o fluxo **frontend → backend → LLM → resposta** do projeto e serve como referência estável para futuras análises (humanas e por IA).

> Objetivo: evitar redescoberta manual do fluxo a cada investigação.

## 1) Onde ocorre a chamada ao LLM

Integração principal (runtime ativo):

- `alemao_app/learning_engine_service.py`
  - Cliente LLM: `_get_llm_client()`
  - Endpoint xAI: `base_url="https://api.x.ai/v1"`
  - Modelo: `grok-4-1-fast-reasoning`
  - Chamadas:
    - `_call_llm(prompt_payload)` (geração de card)
    - `_call_llm_evaluation(...)` (avaliação de tradução)

Contrato atual do WordCard (`_call_llm`):

- JSON apenas
- chaves: `examples` (máx. 3), `useful_phrase` (1), `desafio` (1)
- sem sinônimos C1
- resposta total limitada a 1200 caracteres

Rotas Django ativas:

- `config/urls.py` inclui `alemao_app.urls`
- `alemao_app/urls.py`
  - `POST /api/study/generate/`
  - `POST /api/study/evaluate/`

## 2) Fluxo completo da requisição

### 2.0 Split de análise (lite vs deep)

Novos endpoints (sem quebrar os atuais):

- `POST /api/analyze_lite`
- `POST /api/analyze_deep`

Entradas:

```json
{
  "document_id": 123,
  "limit": 20
}
```

Regras de separação:

- `analyze_lite`: somente tokens básicos (`lemma`, `pos`, `gender` quando aplicável), sem enriquecimento profundo;
- `analyze_deep`: retorna caso sintático + função + confidence;
- ambos sem chamada ao LLM;
- endpoint legado de análise por documento permanece ativo para compatibilidade.

Fluxo de estados no frontend (análise de frase):

- `idle`
- `analyzing_lite`
- `lite_ready`
- `analyzing_deep`
- `deep_ready`
- `error`

Regras operacionais no frontend:

- ao clicar **Analisar**, chama `analyze_lite` primeiro;
- renderiza tokens imediatamente após `lite_ready`;
- inicia `analyze_deep` em background;
- aplica cores quando deep retorna (`case` → classes visuais);
- se a frase mudar, invalida respostas antigas por `phrase_hash`.

### 2.1 Geração de card (clique em token)

1. Frontend carrega/analisa texto:
   - `createDocument()` → `POST /api/documents/`
   - `getDocumentById()` → `GET /api/documents/{id}/`
2. Usuário clica em palavra no `InteractiveReader`.
3. Frontend chama `generateStudyFlashcard(documentId, wordId)`.
4. Backend recebe em `StudyGenerateAPIView.post`.
5. Backend executa `generate_study_plan(...)`:
   - busca candidatos (`_fetch_due_candidates`)
   - extrai contexto (`_extract_sentence_contexts`)
   - monta payload (`_build_prompt_payload`)
   - chama Grok (`_call_llm`)
6. Backend retorna `llm_result` + metadados dos itens.
7. Frontend renderiza card (`analise_rapida`, `nivel_c1`, `variacao_nativa`, `desafio_traducao`).

### 2.3 Análise de frase (contrato estrito)

Endpoint novo (backend):

- `GET /api/documents/{document_id}/analysis/`

Compatibilidade:

- este endpoint continua funcionando e reutiliza a mesma base de análise profunda.

Contrato de resposta (JSON estrito):

```json
{
  "document_id": 123,
  "tokens": [
    {
      "token_id": 1,
      "surface": "Patientin",
      "lemma": "patientin",
      "pos": "NOUN",
      "gender": "F",
      "case": "Nom",
      "syntactic_role": "subject",
      "confidence": 0.85
    }
  ]
}
```

Regras implementadas no backend:

- saída apenas JSON;
- máximo de 20 tokens;
- cada token contém **somente**: `token_id`, `surface`, `lemma`, `pos`, `gender`, `case`, `syntactic_role`, `confidence`;
- `case` restrito a `Nom | Akk | Dat | ?`;
- `syntactic_role` restrito a `subject | object | modifier | ?`;
- `confidence` entre `0` e `1`.

### 2.2 Avaliação de tradução

1. Frontend envia `desafio_pt`, `tentativa_de`, `contexto_original`.
2. Backend recebe em `StudyEvaluateAPIView.post`.
3. Backend chama `evaluate_translation(...)` → `_call_llm_evaluation(...)`.
4. Grok responde JSON de avaliação.
5. Backend persiste tentativa (`TranslationAttempt`) e responde ao frontend.

## 3) Arquivos envolvidos

Frontend:

- `frontend/src/App.jsx`
- `frontend/src/components/InteractiveReader.jsx`
- `frontend/src/api_client.js`
- `frontend/vite.config.js`

Backend:

- `config/urls.py`
- `alemao_app/urls.py`
- `alemao_app/views.py`
- `alemao_app/learning_engine_service.py`
- `alemao_app/text_processing_service.py`
- `config/settings.py`
- `docker-compose.yml`

## 4) Latência por etapa (estado atual)

### 4.0 Instrumentação implementada

Logs emitidos no backend:

- `analyze_lite_timing` (tempo de execução do endpoint)
- `analyze_deep_timing` (tempo de execução do endpoint)
- `wordcard_timing` (tempo total de geração de card)
- `evaluate_timing` (tempo total de avaliação)
- `wordcard_llm_timing` (tempo + payload/response bytes no LLM)
- `evaluate_llm_timing` (tempo + payload/response bytes no LLM)
- `request_timing` via middleware (método, path, status, duração)

Campos de tamanho registrados:

- `payload_bytes`: tamanho enviado ao LLM
- `response_bytes`: tamanho retornado pelo LLM

### 4.1 O que existe hoje

- Não há instrumentação explícita de tempo por etapa (sem métricas de elapsed por request/LLM no código).
- Há apenas log de exceção em falhas críticas (`logger.exception`).

### 4.2 Limites configurados (importantes para diagnóstico)

- Frontend timeout de request: `REQUEST_TIMEOUT_MS = 20000`
- LLM client timeout default: `LLM_TIMEOUT_SECONDS` (default 20s)
- LLM retries: `LLM_MAX_RETRIES` (default 1)
- Gunicorn: `--workers 3 --timeout 120`

### 4.3 Estimativa operacional (sem observação em produção)

- `POST /api/documents/` (spaCy + persistência): ~0.2s a 1.5s
- `POST /api/study/generate/`: dominado por chamada LLM (~0.8s a 8s)
- `POST /api/study/evaluate/`: dominado por chamada LLM (~0.7s a 6s)

> Faixas acima são heurísticas. Não representam média medida em log.

## 5) Bloqueios síncronos

Pontos de espera/bloqueio relevantes:

- Frontend espera `initCsrf()` antes de métodos mutáveis.
- Backend é síncrono por worker (WSGI/Gunicorn); chamada externa ao LLM bloqueia worker até retorno/timeout.
- NLP local com spaCy (`nlp(raw_text)`) é CPU-bound e síncrono.
- Persistência em transação (`transaction.atomic`, `bulk_create`) é síncrona.

## 6) Payload médio para LLM (estimado)

Sem logs de `token_usage`/bytes em produção, usamos estimativa a partir dos contratos JSON reais.

### 6.1 Geração (`_call_llm`)

- Cenário mais comum (1 item, clique em palavra): ~1.7 KB por request ao LLM
- 3 itens: ~2.4 KB
- 10 itens: ~4.9 KB

### 6.2 Avaliação (`_call_llm_evaluation`)

- Faixa típica: ~0.8 KB a ~1.1 KB por request

## 7) Tamanho médio da resposta LLM (estimado)

- Geração: ~0.35 KB a ~0.9 KB
- Avaliação: ~0.25 KB a ~0.45 KB

Observação:

- O backend também retorna `raw_content`, que replica o JSON original do LLM e pode ampliar a resposta final backend→frontend.

Atualização:

- o retorno de WordCard agora não inclui `raw_content`;
- o backend aplica truncamento defensivo para manter o JSON final de WordCard em até 1200 caracteres.

## 7.1 Cache WordCard

- Cache por chave `lemma + level` (`wordcard:v2:{LEVEL}:{lemma}`)
- TTL padrão: `WORDCARD_CACHE_TTL_SECONDS` (default 21600s)
- Cache usado quando há `focus_word_id` (clique em palavra)

## 8) Regra de manutenção da documentação

Sempre que alterar qualquer item abaixo, atualizar este arquivo **no mesmo PR/commit**:

1. Modelo/endpoint/provider LLM
2. Formato de prompt (`messages`, `response_format`, chaves esperadas)
3. Endpoints frontend/backend do fluxo de estudo
4. Timeouts/retries
5. Estratégia de persistência ligada ao fluxo
6. Campos de resposta consumidos pelo frontend
7. Contrato do endpoint estrito `/api/documents/{id}/analysis/`

Checklist rápido de atualização:

- [ ] Atualizar seção “Onde ocorre a chamada ao LLM”
- [ ] Atualizar seção “Fluxo completo da requisição”
- [ ] Atualizar seção “Arquivos envolvidos”
- [ ] Revisar “Latência por etapa” e limites configurados
- [ ] Revisar “Payload médio” e “Resposta média”

## 9) Limitações conhecidas de observabilidade

- Sem medição automática de latência por fase.
- Sem captura persistente de tamanho de payload/resposta por request.
- Sem `usage`/tokens registrados do provedor LLM.

Se a observabilidade for expandida no futuro, adicionar nesta documentação:

- fonte dos logs,
- periodicidade de cálculo,
- janela de média (ex.: p50/p95 por 24h/7d).
