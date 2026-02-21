from __future__ import annotations

import json
import logging
import os
import time
from functools import lru_cache
from dataclasses import dataclass
from typing import Any, Dict, List

import spacy
from django.core.cache import cache
from django.db.models import Prefetch
from django.utils import timezone
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, RateLimitError

from .models import TextDocument, TextTokenRelation, UserKnowledge

logger = logging.getLogger(__name__)


class LearningEngineError(Exception):
    pass


@dataclass(frozen=True)
class StudyCandidate:
    relation_id: int
    word_token_id: int
    lemma: str
    pos_tag: str
    gender: str
    grammatical_case: str
    position: int


class LearningEngineService:
    _nlp = None
    _model_name = None
    WORDCARD_MAX_RESPONSE_CHARS = 1200
    WORDCARD_MAX_TOKENS = 220
    EVALUATE_MAX_TOKENS = 180
    WORDCARD_SYSTEM_PROMPT = (
        "Você gera APENAS JSON válido. "
        "Schema exato: {\"examples\":[string<=120] max 3,\"useful_phrase\":string<=220,\"desafio\":string<=220}. "
        "Resposta total <=1200 chars. Sem markdown, sem texto extra, sem explicações longas, sem repetir a frase de entrada. "
        "Se houver dúvida, use '?'."
    )
    WORDCARD_FIX_JSON_PROMPT = (
        "Corrija para JSON válido e APENAS JSON. "
        "Schema exato: {\"examples\":array(max 3),\"useful_phrase\":string,\"desafio\":string}. "
        "<=1200 chars, sem texto extra, sem markdown, sem repetir entrada. Se dúvida use '?'."
    )
    EVALUATE_SYSTEM_PROMPT = (
        "Você avalia tradução PT->DE e retorna APENAS JSON válido. "
        "Schema exato: {\"correto\":boolean,\"feedback_curto\":string<=180,\"versao_ideal\":string<=180}. "
        "Sem markdown, sem texto extra, sem explicações longas, sem repetir integralmente os textos de entrada. "
        "Se houver dúvida, use '?'."
    )
    EVALUATE_FIX_JSON_PROMPT = (
        "Corrija para JSON válido e APENAS JSON. "
        "Schema exato: {\"correto\":boolean,\"feedback_curto\":string,\"versao_ideal\":string}. "
        "Sem texto extra, sem markdown, sem explicações longas. Se dúvida use '?'."
    )

    @staticmethod
    def _get_env_int(name: str, default: int) -> int:
        raw_value = os.getenv(name)
        if raw_value is None:
            return default
        try:
            return int(raw_value)
        except (TypeError, ValueError):
            return default

    @classmethod
    def _get_nlp(cls):
        if cls._nlp is None:
            try:
                cls._nlp = spacy.load("de_core_news_lg")
                cls._model_name = "de_core_news_lg"
            except OSError:
                cls._nlp = spacy.load("de_core_news_md")
                cls._model_name = "de_core_news_md"
        return cls._nlp

    @staticmethod
    @lru_cache(maxsize=64)
    def _extract_sentence_contexts(raw_text: str) -> Dict[int, Dict[str, str]]:
        nlp = LearningEngineService._get_nlp()
        doc = nlp(raw_text)

        context_by_position: Dict[int, Dict[str, str]] = {}
        for sent in doc.sents:
            sentence_text = sent.text.strip()
            for token in sent:
                context_by_position[token.i] = {
                    "surface": token.text,
                    "sentence": sentence_text,
                    "dependency": token.dep_,
                }

        return context_by_position

    @staticmethod
    def _fetch_due_candidates(user, document_id: int, focus_word_id: int | None = None) -> List[StudyCandidate]:
        now = timezone.now()

        user_knowledge_qs = UserKnowledge.objects.filter(user=user).only(
            "word_token_id",
            "retention_level",
            "next_review_at",
        )

        relations = (
            TextTokenRelation.objects.select_related("word_token")
            .prefetch_related(
                Prefetch(
                    "word_token__user_knowledge",
                    queryset=user_knowledge_qs,
                    to_attr="knowledge_for_user",
                )
            )
            .filter(text_document_id=document_id)
            .order_by("word_token_id", "position")
            .only(
                "id",
                "word_token_id",
                "grammatical_case",
                "position",
                "word_token__lemma",
                "word_token__pos_tag",
                "word_token__gender",
            )
        )

        if focus_word_id is not None:
            relations = relations.filter(word_token_id=focus_word_id)

        unique_by_word: Dict[int, StudyCandidate] = {}
        for relation in relations.iterator(chunk_size=2000):
            if relation.word_token_id in unique_by_word:
                continue

            knowledge_rows = getattr(relation.word_token, "knowledge_for_user", [])
            if focus_word_id is None and knowledge_rows:
                knowledge = knowledge_rows[0]
                is_due = knowledge.retention_level == 0 or knowledge.next_review_at <= now
                if not is_due:
                    continue

            unique_by_word[relation.word_token_id] = StudyCandidate(
                relation_id=relation.id,
                word_token_id=relation.word_token_id,
                lemma=relation.word_token.lemma,
                pos_tag=relation.word_token.pos_tag,
                gender=relation.word_token.gender,
                grammatical_case=relation.grammatical_case,
                position=relation.position,
            )

        return list(unique_by_word.values())

    @staticmethod
    def _build_prompt_payload(document_id: int, candidates: List[Dict[str, str]], level: str = "B1") -> Dict:
        return {
            "task": "german_c1_medical_training",
            "language": "pt-BR",
            "level": level,
            "document_id": document_id,
            "output_contract": {
                "type": "json_object",
                "required_keys": [
                    "examples",
                    "useful_phrase",
                    "desafio",
                ],
                "examples_max": 3,
                "total_chars_max": LearningEngineService.WORDCARD_MAX_RESPONSE_CHARS,
            },
            "study_items": candidates,
        }

    @staticmethod
    def _safe_str(value) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @staticmethod
    def _normalize_wordcard_payload(parsed: Dict) -> Dict:
        raw_examples = parsed.get("examples", [])
        if not isinstance(raw_examples, list):
            raw_examples = []

        examples: List[str] = []
        for item in raw_examples:
            text = LearningEngineService._safe_str(item)
            if text:
                examples.append(text)
            if len(examples) == 3:
                break

        useful_phrase = LearningEngineService._safe_str(parsed.get("useful_phrase", ""))
        desafio = LearningEngineService._safe_str(parsed.get("desafio", ""))

        payload = {
            "examples": examples,
            "useful_phrase": useful_phrase,
            "desafio": desafio,
        }
        return LearningEngineService._enforce_wordcard_max_chars(payload)

    @staticmethod
    def _enforce_wordcard_max_chars(payload: Dict) -> Dict:
        max_chars = LearningEngineService.WORDCARD_MAX_RESPONSE_CHARS
        normalized = {
            "examples": [LearningEngineService._safe_str(item) for item in payload.get("examples", [])][:3],
            "useful_phrase": LearningEngineService._safe_str(payload.get("useful_phrase", "")),
            "desafio": LearningEngineService._safe_str(payload.get("desafio", "")),
        }

        def _serialized_len(data: Dict) -> int:
            return len(json.dumps(data, ensure_ascii=False))

        if _serialized_len(normalized) <= max_chars:
            return normalized

        budget = max_chars
        base_overhead = _serialized_len({"examples": [], "useful_phrase": "", "desafio": ""})
        budget = max(budget - base_overhead, 0)

        trimmed_examples: List[str] = []
        for example in normalized["examples"]:
            if budget <= 0:
                break
            snippet = example[: min(len(example), 120)]
            if len(snippet) > budget:
                snippet = snippet[:budget]
            trimmed_examples.append(snippet)
            budget -= len(snippet)

        useful = normalized["useful_phrase"]
        useful_limit = min(max(budget // 2, 0), 220)
        useful = useful[:useful_limit] if useful_limit > 0 else ""
        budget -= len(useful)

        challenge = normalized["desafio"]
        challenge_limit = min(max(budget, 0), 220)
        challenge = challenge[:challenge_limit] if challenge_limit > 0 else ""

        constrained = {
            "examples": trimmed_examples[:3],
            "useful_phrase": useful,
            "desafio": challenge,
        }

        while _serialized_len(constrained) > max_chars:
            if constrained["desafio"]:
                constrained["desafio"] = constrained["desafio"][:-1]
                continue
            if constrained["useful_phrase"]:
                constrained["useful_phrase"] = constrained["useful_phrase"][:-1]
                continue
            if constrained["examples"] and constrained["examples"][-1]:
                constrained["examples"][-1] = constrained["examples"][-1][:-1]
                continue
            break

        return constrained

    @staticmethod
    def _wordcard_cache_key(lemma: str, level: str) -> str:
        safe_lemma = (lemma or "").strip().lower()
        safe_level = (level or "B1").strip().upper()
        return f"wordcard:v2:{safe_level}:{safe_lemma}"

    @staticmethod
    def _wordcard_cache_ttl_seconds() -> int:
        return max(LearningEngineService._get_env_int("WORDCARD_CACHE_TTL_SECONDS", 21600), 60)

    @staticmethod
    def _json_size_bytes(data) -> int:
        return len(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    @staticmethod
    def _response_content_to_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            chunks: List[str] = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text = part.get("text")
                    if isinstance(text, str):
                        chunks.append(text)
            return "".join(chunks)
        return ""

    @staticmethod
    def _create_completion(messages: List[Dict[str, str]], temperature: float, max_tokens: int):
        client = LearningEngineService._get_llm_client()
        return client.chat.completions.create(
            model="grok-4-1-fast-reasoning",
            response_format={"type": "json_object"},
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stop=["\n\n"],
        )

    @staticmethod
    def _validate_wordcard_schema(parsed: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(parsed, dict):
            raise LearningEngineError("LLM retornou formato inválido.")

        examples = parsed.get("examples")
        useful_phrase = parsed.get("useful_phrase")
        desafio = parsed.get("desafio")

        if not isinstance(examples, list):
            raise LearningEngineError("Schema inválido no WordCard: 'examples' deve ser array.")
        if len(examples) > 3:
            raise LearningEngineError("Schema inválido no WordCard: 'examples' excede 3 itens.")
        if not isinstance(useful_phrase, str):
            raise LearningEngineError("Schema inválido no WordCard: 'useful_phrase' deve ser string.")
        if not isinstance(desafio, str):
            raise LearningEngineError("Schema inválido no WordCard: 'desafio' deve ser string.")

        normalized = LearningEngineService._normalize_wordcard_payload(parsed)
        serialized_len = len(json.dumps(normalized, ensure_ascii=False))
        if serialized_len > LearningEngineService.WORDCARD_MAX_RESPONSE_CHARS:
            raise LearningEngineError("Schema inválido no WordCard: tamanho acima do limite.")

        return normalized

    @staticmethod
    def _validate_evaluation_schema(parsed: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(parsed, dict):
            raise LearningEngineError("Formato inválido na avaliação do LLM.")

        if "correto" not in parsed or "feedback_curto" not in parsed or "versao_ideal" not in parsed:
            raise LearningEngineError("Schema inválido na avaliação do LLM.")

        if not isinstance(parsed.get("feedback_curto"), str):
            raise LearningEngineError("Schema inválido na avaliação: 'feedback_curto' deve ser string.")
        if not isinstance(parsed.get("versao_ideal"), str):
            raise LearningEngineError("Schema inválido na avaliação: 'versao_ideal' deve ser string.")

        return parsed

    @staticmethod
    def _get_llm_client() -> OpenAI:
        api_key = os.getenv("LLM_API_KEY")
        if not api_key:
            raise LearningEngineError("LLM_API_KEY não configurada.")

        timeout_seconds = LearningEngineService._get_env_int("LLM_TIMEOUT_SECONDS", 20)
        max_retries = LearningEngineService._get_env_int("LLM_MAX_RETRIES", 1)

        return OpenAI(
            api_key=api_key,
            base_url="https://api.x.ai/v1",
            timeout=max(timeout_seconds, 5),
            max_retries=max(max_retries, 0),
        )

    @staticmethod
    def _call_llm(prompt_payload: Dict) -> Dict:
        start = time.perf_counter()
        user_json = json.dumps(prompt_payload, ensure_ascii=False)
        base_messages = [
            {"role": "system", "content": LearningEngineService.WORDCARD_SYSTEM_PROMPT},
            {"role": "user", "content": user_json},
        ]

        total_payload_bytes = 0
        response_size_bytes = 0
        normalized: Dict[str, Any] | None = None
        last_error: Exception | None = None
        content_text = ""

        for attempt in range(2):
            messages = base_messages
            temperature = 0.1
            if attempt == 1:
                messages = [
                    {"role": "system", "content": LearningEngineService.WORDCARD_FIX_JSON_PROMPT},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "original_request": prompt_payload,
                                "invalid_output": content_text,
                            },
                            ensure_ascii=False,
                        ),
                    },
                ]
                temperature = 0.0

            total_payload_bytes += LearningEngineService._json_size_bytes(messages)

            try:
                response = LearningEngineService._create_completion(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=LearningEngineService.WORDCARD_MAX_TOKENS,
                )
            except APITimeoutError as exc:
                raise LearningEngineError("O serviço de IA excedeu o tempo limite. Tente novamente.") from exc
            except RateLimitError as exc:
                raise LearningEngineError("Limite de requisições no serviço de IA. Aguarde e tente novamente.") from exc
            except APIConnectionError as exc:
                raise LearningEngineError("Falha de conexão com o serviço de IA. Tente novamente.") from exc
            except APIStatusError as exc:
                raise LearningEngineError(f"Serviço de IA indisponível (status {exc.status_code}).") from exc

            content = response.choices[0].message.content
            content_text = LearningEngineService._response_content_to_text(content)
            if not content_text:
                last_error = LearningEngineError("Resposta vazia do LLM.")
                continue

            response_size_bytes = len(content_text.encode("utf-8"))

            try:
                parsed = json.loads(content_text)
                normalized = LearningEngineService._validate_wordcard_schema(parsed)
                break
            except (json.JSONDecodeError, LearningEngineError) as exc:
                last_error = exc

        if normalized is None:
            if isinstance(last_error, LearningEngineError):
                raise last_error
            raise LearningEngineError("LLM não retornou JSON válido.")

        useful_phrase = normalized.get("useful_phrase", "")
        examples = normalized.get("examples", [])
        desafio = normalized.get("desafio", "")

        legacy_analise = examples[0] if examples else useful_phrase

        result = {
            "examples": examples[:3],
            "useful_phrase": useful_phrase,
            "desafio": desafio,
            "analise_rapida": legacy_analise,
            "nivel_c1": [],
            "variacao_nativa": useful_phrase,
            "desafio_traducao": desafio,
        }
        LearningEngineService._log_wordcard_llm_metrics(total_payload_bytes, response_size_bytes, start)
        return result

    @staticmethod
    def _log_wordcard_llm_metrics(payload_size_bytes: int, response_size_bytes: int, start: float) -> None:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "wordcard_llm_timing duration_ms=%.2f payload_bytes=%s response_bytes=%s",
            elapsed_ms,
            payload_size_bytes,
            response_size_bytes,
        )

    @staticmethod
    def _call_llm_evaluation(desafio_pt: str, tentativa_de: str, contexto_original: str) -> Dict:
        start = time.perf_counter()
        user_payload = {
            "desafio_pt": desafio_pt,
            "tentativa_de": tentativa_de,
            "contexto_original": contexto_original,
            "output_contract": {
                "type": "json_object",
                "required_keys": ["correto", "feedback_curto", "versao_ideal"],
            },
        }
        base_messages = [
            {"role": "system", "content": LearningEngineService.EVALUATE_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ]

        total_payload_bytes = 0
        response_size_bytes = 0
        parsed: Dict[str, Any] | None = None
        last_error: Exception | None = None
        content_text = ""

        for attempt in range(2):
            messages = base_messages
            temperature = 0.1
            if attempt == 1:
                messages = [
                    {"role": "system", "content": LearningEngineService.EVALUATE_FIX_JSON_PROMPT},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "original_request": user_payload,
                                "invalid_output": content_text,
                            },
                            ensure_ascii=False,
                        ),
                    },
                ]
                temperature = 0.0

            total_payload_bytes += LearningEngineService._json_size_bytes(messages)

            try:
                response = LearningEngineService._create_completion(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=LearningEngineService.EVALUATE_MAX_TOKENS,
                )
            except APITimeoutError as exc:
                raise LearningEngineError("A avaliação demorou além do esperado. Tente novamente.") from exc
            except RateLimitError as exc:
                raise LearningEngineError("Limite de avaliações atingido no serviço de IA. Aguarde e tente novamente.") from exc
            except APIConnectionError as exc:
                raise LearningEngineError("Falha de conexão com o serviço de IA na avaliação.") from exc
            except APIStatusError as exc:
                raise LearningEngineError(f"Serviço de IA indisponível na avaliação (status {exc.status_code}).") from exc

            content = response.choices[0].message.content
            content_text = LearningEngineService._response_content_to_text(content)
            if not content_text:
                last_error = LearningEngineError("Resposta vazia do LLM na avaliação.")
                continue

            response_size_bytes = len(content_text.encode("utf-8"))

            try:
                candidate = json.loads(content_text)
                parsed = LearningEngineService._validate_evaluation_schema(candidate)
                break
            except (json.JSONDecodeError, LearningEngineError) as exc:
                last_error = exc

        if parsed is None:
            if isinstance(last_error, LearningEngineError):
                raise last_error
            raise LearningEngineError("LLM não retornou JSON válido na avaliação.")

        result = {
            "correto": bool(parsed.get("correto", False)),
            "feedback_curto": str(parsed.get("feedback_curto", "")),
            "versao_ideal": str(parsed.get("versao_ideal", "")),
            "raw_content": content_text,
        }
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "evaluate_llm_timing duration_ms=%.2f payload_bytes=%s response_bytes=%s",
            elapsed_ms,
            total_payload_bytes,
            response_size_bytes,
        )
        return result



def generate_study_plan(user, document_id: int, focus_word_id: int | None = None, proficiency_level: str = "B1") -> Dict:
    try:
        document = TextDocument.objects.only("id", "raw_text").get(id=document_id)
    except TextDocument.DoesNotExist as exc:
        raise LearningEngineError("Documento não encontrado.") from exc

    try:
        candidates = LearningEngineService._fetch_due_candidates(
            user=user,
            document_id=document_id,
            focus_word_id=focus_word_id,
        )
        if not candidates:
            return {
                "document_id": document_id,
                "study_items_count": 0,
                "items": [],
                "llm_result": {"items": []},
            }

        context_by_position = LearningEngineService._extract_sentence_contexts(document.raw_text)

        llm_items: List[Dict[str, str]] = []
        for candidate in candidates:
            context = context_by_position.get(candidate.position, {})
            llm_items.append(
                {
                    "relation_id": candidate.relation_id,
                    "word_token_id": candidate.word_token_id,
                    "lemma": candidate.lemma,
                    "pos_tag": candidate.pos_tag,
                    "gender": candidate.gender,
                    "grammatical_case": candidate.grammatical_case,
                    "surface_form": context.get("surface", candidate.lemma),
                    "dependency": context.get("dependency", ""),
                    "context_sentence": context.get("sentence", ""),
                }
            )

        llm_result = None

        if focus_word_id is not None and llm_items:
            cache_key = LearningEngineService._wordcard_cache_key(llm_items[0].get("lemma", ""), proficiency_level)
            cached_value = cache.get(cache_key)
            if isinstance(cached_value, dict):
                llm_result = cached_value

            if llm_result is None:
                prompt_payload = LearningEngineService._build_prompt_payload(
                    document_id=document_id,
                    candidates=[llm_items[0]],
                    level=proficiency_level,
                )
                llm_result = LearningEngineService._call_llm(prompt_payload)
                cache.set(cache_key, llm_result, timeout=LearningEngineService._wordcard_cache_ttl_seconds())
        else:
            prompt_payload = LearningEngineService._build_prompt_payload(
                document_id=document_id,
                candidates=llm_items[:1],
                level=proficiency_level,
            )
            llm_result = LearningEngineService._call_llm(prompt_payload)

        return {
            "document_id": document_id,
            "study_items_count": len(llm_items),
            "items": llm_items,
            "llm_result": llm_result,
        }

    except Exception as exc:
        logger.exception("Erro ao gerar plano de estudo para o usuário %s e documento %s", user.id, document_id)
        if isinstance(exc, LearningEngineError):
            raise
        raise LearningEngineError("Falha ao gerar plano de estudo.") from exc


def evaluate_translation(desafio_pt: str, tentativa_de: str, contexto_original: str) -> Dict:
    if not desafio_pt.strip():
        raise LearningEngineError("desafio_pt é obrigatório.")
    if not tentativa_de.strip():
        raise LearningEngineError("tentativa_de é obrigatório.")

    try:
        return LearningEngineService._call_llm_evaluation(
            desafio_pt=desafio_pt.strip(),
            tentativa_de=tentativa_de.strip(),
            contexto_original=(contexto_original or "").strip(),
        )
    except Exception as exc:
        if isinstance(exc, LearningEngineError):
            raise
        raise LearningEngineError("Falha ao avaliar tradução.") from exc
