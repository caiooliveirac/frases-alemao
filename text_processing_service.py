from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional, Set, Tuple

import spacy
from django.db import IntegrityError, transaction

from .models import TextDocument, TextTokenRelation, WordToken

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TokenPayload:
    lemma: str
    pos_tag: str
    gender: str
    position: int
    grammatical_case: str


class TextDissectorError(Exception):
    pass


class TextDissector:
    _nlp = None

    def __init__(self, raw_text: str, title: Optional[str] = None) -> None:
        self.raw_text = (raw_text or "").strip()
        self.title = (title or "Texto em alemão").strip()

    @classmethod
    def _get_nlp(cls):
        if cls._nlp is None:
            cls._nlp = spacy.load("de_core_news_lg")
        return cls._nlp

    @staticmethod
    def _map_pos_tag(spacy_pos: str) -> str:
        valid_pos = {choice[0] for choice in WordToken.POSTag.choices}
        return spacy_pos if spacy_pos in valid_pos else WordToken.POSTag.X

    @staticmethod
    def _map_gender(token) -> str:
        gender = token.morph.get("Gender")
        if not gender:
            return WordToken.Gender.NONE

        value = gender[0]
        if value == "Masc":
            return WordToken.Gender.MASCULINE
        if value == "Fem":
            return WordToken.Gender.FEMININE
        if value == "Neut":
            return WordToken.Gender.NEUTER
        return WordToken.Gender.NONE

    @staticmethod
    def _map_case(token) -> str:
        case = token.morph.get("Case")
        if not case:
            return TextTokenRelation.GrammaticalCase.NONE

        value = case[0]
        if value == "Nom":
            return TextTokenRelation.GrammaticalCase.NOMINATIV
        if value == "Acc":
            return TextTokenRelation.GrammaticalCase.AKKUSATIV
        if value == "Dat":
            return TextTokenRelation.GrammaticalCase.DATIV
        if value == "Gen":
            return TextTokenRelation.GrammaticalCase.GENITIV
        return TextTokenRelation.GrammaticalCase.NONE

    @staticmethod
    def _is_valid_word(token) -> bool:
        return token.is_alpha and not token.is_space and not token.is_punct

    @staticmethod
    def _calculate_complexity(doc) -> Decimal:
        sentence_lengths = [sum(1 for t in sent if t.is_alpha) for sent in doc.sents]
        avg_sentence_length = (sum(sentence_lengths) / len(sentence_lengths)) if sentence_lengths else 0

        lemmas = [t.lemma_.lower().strip() for t in doc if t.is_alpha]
        unique_lemmas = len(set(lemmas))
        lexical_diversity = (unique_lemmas / len(lemmas)) if lemmas else 0

        score = (avg_sentence_length * 0.7) + (lexical_diversity * 30)
        score = max(0, min(score, 99.99))
        return Decimal(f"{score:.2f}")

    def _extract_token_payloads(self, doc) -> List[TokenPayload]:
        payloads: List[TokenPayload] = []

        for index, token in enumerate(doc):
            if not self._is_valid_word(token):
                continue

            lemma = token.lemma_.lower().strip()
            if not lemma:
                continue

            payloads.append(
                TokenPayload(
                    lemma=lemma,
                    pos_tag=self._map_pos_tag(token.pos_),
                    gender=self._map_gender(token),
                    position=index,
                    grammatical_case=self._map_case(token),
                )
            )

        return payloads

    @staticmethod
    def _index_word_tokens(tokens: List[WordToken]) -> Dict[Tuple[str, str, str], WordToken]:
        return {(t.lemma, t.pos_tag, t.gender): t for t in tokens}

    def process_and_persist(self) -> int:
        if not self.raw_text:
            raise TextDissectorError("Texto bruto não pode ser vazio.")

        try:
            nlp = self._get_nlp()
            doc = nlp(self.raw_text)

            _ = [sent.text for sent in doc.sents]
            _ = [(t.text, t.lemma_, t.dep_) for t in doc]

            complexity_score = self._calculate_complexity(doc)
            token_payloads = self._extract_token_payloads(doc)

            with transaction.atomic():
                text_document = TextDocument.objects.create(
                    title=self.title,
                    raw_text=self.raw_text,
                    complexity_score=complexity_score,
                )

                if not token_payloads:
                    return text_document.id

                signatures: Set[Tuple[str, str, str]] = {
                    (p.lemma, p.pos_tag, p.gender) for p in token_payloads
                }
                unique_lemmas = {sig[0] for sig in signatures}

                existing_tokens = list(WordToken.objects.filter(lemma__in=unique_lemmas).only("id", "lemma", "pos_tag", "gender"))
                token_map = self._index_word_tokens(existing_tokens)

                missing_tokens = [
                    WordToken(lemma=lemma, pos_tag=pos_tag, gender=gender)
                    for (lemma, pos_tag, gender) in signatures
                    if (lemma, pos_tag, gender) not in token_map
                ]

                if missing_tokens:
                    WordToken.objects.bulk_create(missing_tokens, ignore_conflicts=True, batch_size=1000)
                    refreshed_tokens = list(
                        WordToken.objects.filter(lemma__in=unique_lemmas).only("id", "lemma", "pos_tag", "gender")
                    )
                    token_map = self._index_word_tokens(refreshed_tokens)

                relations = []
                for payload in token_payloads:
                    word_token = token_map.get((payload.lemma, payload.pos_tag, payload.gender))
                    if not word_token:
                        continue

                    relations.append(
                        TextTokenRelation(
                            text_document=text_document,
                            word_token=word_token,
                            position=payload.position,
                            grammatical_case=payload.grammatical_case,
                        )
                    )

                if relations:
                    TextTokenRelation.objects.bulk_create(relations, batch_size=2000)

                return text_document.id

        except (IntegrityError, ValueError, OSError) as exc:
            logger.exception("Falha ao processar e persistir texto em alemão.")
            raise TextDissectorError("Erro ao processar o texto em alemão.") from exc
