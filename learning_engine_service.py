from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import spacy
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from openai import OpenAI

from .models import TextDocument, TextTokenRelation

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

    @classmethod
    def _get_nlp(cls):
        if cls._nlp is None:
            cls._nlp = spacy.load("de_core_news_lg")
        return cls._nlp

    @staticmethod
    def _get_llm_client() -> OpenAI:
        api_key = getattr(settings, "OPENAI_API_KEY", None)
        if not api_key:
            raise LearningEngineError("OPENAI_API_KEY não configurada.")

        base_url = getattr(settings, "OPENAI_BASE_URL", None)
        if base_url:
            return OpenAI(api_key=api_key, base_url=base_url)
        return OpenAI(api_key=api_key)

    @staticmethod
    def _get_llm_model() -> str:
        return getattr(settings, "LEARNING_ENGINE_LLM_MODEL", "gpt-4.1-mini")

    @staticmethod
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
    def _fetch_due_candidates(user, document_id: int) -> List[StudyCandidate]:
        now = timezone.now()

        relations = (
            TextTokenRelation.objects.select_related("word_token", "text_document")
            .filter(text_document_id=document_id)
            .filter(word_token__user_knowledge__user=user)
            .filter(
                Q(word_token__user_knowledge__retention_level=0)
                | Q(word_token__user_knowledge__next_review_at__lte=now)
            )
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

        unique_by_word: Dict[int, StudyCandidate] = {}
        for relation in relations.iterator(chunk_size=2000):
            if relation.word_token_id in unique_by_word:
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
    def _build_prompt_payload(document_id: int, candidates: List[Dict[str, str]]) -> Dict:
        return {
            "task": "german_learning_plan",
            "language": "pt-BR",
            "document_id": document_id,
            "instructions": {
                "goal": "Para cada item, explique a regra gramatical aplicada à palavra no contexto da frase e gere duas frases novas com a mesma palavra.",
                "required_output_schema": {
                    "items": [
                        {
                            "word_token_id": "int",
                            "lemma": "string",
                            "context_sentence": "string",
                            "grammar_explanation_ptbr": "string",
                            "example_sentences_de": ["string", "string"],
                        }
                    ]
                },
                "constraints": [
                    "Explique de forma objetiva e pedagógica.",
                    "As duas frases novas devem estar em alemão e usar explicitamente a mesma palavra (lemma) do item.",
                    "Não invente dados fora dos itens fornecidos.",
                ],
            },
            "study_items": candidates,
        }

    @staticmethod
    def _call_llm(prompt_payload: Dict) -> Dict:
        client = LearningEngineService._get_llm_client()
        model = LearningEngineService._get_llm_model()

        response = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "Você é um tutor especialista em gramática alemã. Responda apenas JSON válido.",
                },
                {
                    "role": "user",
                    "content": json.dumps(prompt_payload, ensure_ascii=False),
                },
            ],
            temperature=0.2,
        )

        content = response.choices[0].message.content
        if not content:
            raise LearningEngineError("Resposta vazia do LLM.")

        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise LearningEngineError("LLM retornou JSON inválido.") from exc



def generate_study_plan(user, document_id: int) -> Dict:
    try:
        document = TextDocument.objects.only("id", "raw_text").get(id=document_id)
    except TextDocument.DoesNotExist as exc:
        raise LearningEngineError("Documento não encontrado.") from exc

    try:
        candidates = LearningEngineService._fetch_due_candidates(user=user, document_id=document_id)
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

        prompt_payload = LearningEngineService._build_prompt_payload(
            document_id=document_id,
            candidates=llm_items,
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
