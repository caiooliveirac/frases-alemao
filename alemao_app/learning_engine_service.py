from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Dict, List

import spacy
from django.db.models import Prefetch
from django.utils import timezone
from openai import OpenAI

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
    def _build_prompt_payload(document_id: int, candidates: List[Dict[str, str]]) -> Dict:
        return {
            "task": "german_c1_medical_training",
            "language": "pt-BR",
            "document_id": document_id,
            "output_contract": {
                "type": "json_object",
                "required_keys": [
                    "analise_rapida",
                    "nivel_c1",
                    "variacao_nativa",
                    "desafio_traducao",
                ],
                "nivel_c1_format": "array_with_2_strings",
            },
            "study_items": candidates,
        }

    @staticmethod
    def _call_llm(prompt_payload: Dict) -> Dict:
        client = OpenAI(api_key=os.getenv("LLM_API_KEY"), base_url="https://api.x.ai/v1")
        if not os.getenv("LLM_API_KEY"):
            raise LearningEngineError("LLM_API_KEY não configurada.")

        response = client.chat.completions.create(
            model="grok-4-1-fast-reasoning",
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "Você é um Chefarzt (Médico Chefe) em um hospital de Zurique. Sua função é treinar um médico brilhante que está aprendendo alemão nível C1. Esqueça explicações gramaticais longas e chatas. Foco em alta performance, nuances e jargão clínico. Para a palavra e a frase fornecidas, devolva UM JSON válido com as seguintes chaves: - 'analise_rapida': 1 frase direta sobre a função da palavra. - 'nivel_c1': 2 sinônimos avançados ou jargões médicos exatos para essa palavra. - 'variacao_nativa': Como um médico suíço diria essa frase inteira de forma mais natural, rápida ou idiomática durante uma emergência. - 'desafio_traducao': Uma frase curta em português (contexto de plantão/emergência) usando essa mesma estrutura gramatical para o aluno traduzir mentalmente. Retorne APENAS o JSON puro, sem markdown e sem texto extra.",
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
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LearningEngineError("LLM não retornou JSON válido.") from exc

        if not isinstance(parsed, dict):
            raise LearningEngineError("LLM retornou formato inválido.")

        analise_rapida = parsed.get("analise_rapida", "")
        nivel_c1 = parsed.get("nivel_c1", [])
        variacao_nativa = parsed.get("variacao_nativa", "")
        desafio_traducao = parsed.get("desafio_traducao", "")

        if not isinstance(nivel_c1, list):
            nivel_c1 = []

        return {
            "analise_rapida": analise_rapida,
            "nivel_c1": [str(item) for item in nivel_c1][:2],
            "variacao_nativa": variacao_nativa,
            "desafio_traducao": desafio_traducao,
            "raw_content": content,
        }

    @staticmethod
    def _call_llm_evaluation(desafio_pt: str, tentativa_de: str, contexto_original: str) -> Dict:
        client = OpenAI(api_key=os.getenv("LLM_API_KEY"), base_url="https://api.x.ai/v1")
        if not os.getenv("LLM_API_KEY"):
            raise LearningEngineError("LLM_API_KEY não configurada.")

        system_prompt = (
            "Você é um preceptor médico suíço avaliando a tradução de um residente do português para o alemão (foco C1). "
            f"O residente precisava traduzir: '{desafio_pt}'. "
            f"A tentativa dele foi: '{tentativa_de}'. "
            "Avalie a precisão gramatical (especialmente declinações e ordem dos verbos) e o vocabulário clínico. "
            "Retorne APENAS um JSON com: 'correto' (boolean), 'feedback_curto' (1 frase de correção direta) e 'versao_ideal' "
            "(a melhor forma nativa C1 de dizer isso)."
        )

        user_payload = {
            "desafio_pt": desafio_pt,
            "tentativa_de": tentativa_de,
            "contexto_original": contexto_original,
            "output_contract": {
                "type": "json_object",
                "required_keys": ["correto", "feedback_curto", "versao_ideal"],
            },
        }

        response = client.chat.completions.create(
            model="grok-4-1-fast-reasoning",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            temperature=0.1,
        )

        content = response.choices[0].message.content
        if not content:
            raise LearningEngineError("Resposta vazia do LLM na avaliação.")

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LearningEngineError("LLM não retornou JSON válido na avaliação.") from exc

        if not isinstance(parsed, dict):
            raise LearningEngineError("Formato inválido na avaliação do LLM.")

        return {
            "correto": bool(parsed.get("correto", False)),
            "feedback_curto": str(parsed.get("feedback_curto", "")),
            "versao_ideal": str(parsed.get("versao_ideal", "")),
            "raw_content": content,
        }



def generate_study_plan(user, document_id: int, focus_word_id: int | None = None) -> Dict:
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
