from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class CEFRLevel(models.TextChoices):
    A1 = "A1", "A1"
    B1 = "B1", "B1"
    C1 = "C1", "C1"


class TextDocument(models.Model):
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="text_documents",
        null=True,
        blank=True,
        db_index=True,
    )
    title = models.CharField(max_length=255, db_index=True)
    raw_text = models.TextField()
    complexity_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Complexidade calculada do texto (ex.: 0.00 a 99.99).",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "text_documents"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["title"], name="idx_textdoc_title"),
            models.Index(fields=["complexity_score"], name="idx_textdoc_complexity"),
        ]

    def __str__(self) -> str:
        return self.title


class WordToken(models.Model):
    class POSTag(models.TextChoices):
        NOUN = "NOUN", "Noun"
        VERB = "VERB", "Verb"
        ADJ = "ADJ", "Adjective"
        ADV = "ADV", "Adverb"
        PRON = "PRON", "Pronoun"
        ADP = "ADP", "Adposition"
        AUX = "AUX", "Auxiliary"
        CCONJ = "CCONJ", "Coordinating Conjunction"
        SCONJ = "SCONJ", "Subordinating Conjunction"
        DET = "DET", "Determiner"
        INTJ = "INTJ", "Interjection"
        NUM = "NUM", "Numeral"
        PART = "PART", "Particle"
        PROPN = "PROPN", "Proper Noun"
        PUNCT = "PUNCT", "Punctuation"
        SYM = "SYM", "Symbol"
        X = "X", "Other"

    class Gender(models.TextChoices):
        MASCULINE = "M", "Masculine"
        FEMININE = "F", "Feminine"
        NEUTER = "N", "Neuter"
        NONE = "X", "Not Applicable"

    lemma = models.CharField(max_length=128)
    pos_tag = models.CharField(max_length=10, choices=POSTag.choices, db_index=True)
    gender = models.CharField(
        max_length=1,
        choices=Gender.choices,
        default=Gender.NONE,
        db_index=True,
    )

    class Meta:
        db_table = "word_tokens"
        constraints = [
            models.UniqueConstraint(
                fields=["lemma", "pos_tag", "gender"],
                name="uq_wordtoken_lemma_pos_gender",
            )
        ]
        indexes = [
            models.Index(fields=["lemma"], name="idx_wordtoken_lemma"),
            models.Index(fields=["lemma", "pos_tag"], name="idx_wordtoken_lemma_pos"),
        ]

    def __str__(self) -> str:
        return f"{self.lemma} ({self.pos_tag})"


class TextTokenRelation(models.Model):
    class GrammaticalCase(models.TextChoices):
        NOMINATIV = "NOM", "Nominativ"
        AKKUSATIV = "AKK", "Akkusativ"
        DATIV = "DAT", "Dativ"
        GENITIV = "GEN", "Genitiv"
        NONE = "NONE", "Not Applicable"

    text_document = models.ForeignKey(
        TextDocument,
        on_delete=models.CASCADE,
        related_name="token_relations",
        db_index=True,
    )
    word_token = models.ForeignKey(
        WordToken,
        on_delete=models.CASCADE,
        related_name="document_relations",
        db_index=True,
    )
    position = models.PositiveIntegerField(
        help_text="Posição do token no texto (base 0 ou 1, conforme convenção da aplicação)."
    )
    grammatical_case = models.CharField(
        max_length=4,
        choices=GrammaticalCase.choices,
        default=GrammaticalCase.NONE,
        db_index=True,
    )

    class Meta:
        db_table = "text_token_relations"
        constraints = [
            models.UniqueConstraint(
                fields=["text_document", "position"],
                name="uq_texttokenrelation_doc_position",
            )
        ]
        indexes = [
            models.Index(fields=["text_document", "position"], name="idx_ttr_doc_pos"),
            models.Index(fields=["text_document", "word_token"], name="idx_ttr_doc_word"),
            models.Index(fields=["word_token", "grammatical_case"], name="idx_ttr_word_case"),
        ]

    def __str__(self) -> str:
        return f"{self.text_document_id}:{self.position} -> {self.word_token_id}"


class UserKnowledge(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="word_knowledge",
        db_index=True,
    )
    word_token = models.ForeignKey(
        WordToken,
        on_delete=models.CASCADE,
        related_name="user_knowledge",
        db_index=True,
    )
    retention_level = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        default=0,
        db_index=True,
        help_text="Nível de retenção para SRS (0 a 5).",
    )
    next_review_at = models.DateTimeField(db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_knowledge"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "word_token"],
                name="uq_userknowledge_user_wordtoken",
            )
        ]
        indexes = [
            models.Index(fields=["user", "next_review_at"], name="idx_uk_user_nextreview"),
            models.Index(fields=["user", "retention_level"], name="idx_uk_user_retention"),
            models.Index(fields=["word_token", "retention_level"], name="idx_uk_word_retention"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} - {self.word_token_id} ({self.retention_level})"


class ClinicalScenario(models.Model):
    text = models.TextField(unique=True)
    proficiency_level = models.CharField(
        max_length=2,
        choices=CEFRLevel.choices,
        default=CEFRLevel.C1,
        db_index=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "clinical_scenarios"
        ordering = ["id"]
        indexes = [
            models.Index(fields=["is_active"], name="idx_cs_active"),
            models.Index(fields=["proficiency_level", "is_active"], name="idx_cs_level_active"),
        ]

    def __str__(self) -> str:
        return self.text[:80]


class WordClickEvent(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="word_click_events",
        db_index=True,
    )
    text_document = models.ForeignKey(
        TextDocument,
        on_delete=models.CASCADE,
        related_name="word_click_events",
        db_index=True,
    )
    word_token = models.ForeignKey(
        WordToken,
        on_delete=models.CASCADE,
        related_name="click_events",
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "word_click_events"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"], name="idx_wce_user_created"),
            models.Index(fields=["word_token", "created_at"], name="idx_wce_word_created"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} -> {self.word_token_id} @ {self.created_at.isoformat()}"


class TranslationAttempt(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="translation_attempts",
        db_index=True,
    )
    challenge_pt = models.TextField()
    attempt_de = models.TextField()
    context_original = models.TextField(blank=True, default="")
    is_correct = models.BooleanField(default=False, db_index=True)
    feedback = models.TextField(blank=True, default="")
    suggested_de = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "translation_attempts"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"], name="idx_ta_user_created"),
            models.Index(fields=["is_correct", "created_at"], name="idx_ta_correct_created"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} ({'ok' if self.is_correct else 'fail'})"


class ReviewEvent(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="review_events",
        db_index=True,
    )
    user_knowledge = models.ForeignKey(
        UserKnowledge,
        on_delete=models.CASCADE,
        related_name="review_events",
        db_index=True,
    )
    score = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(4)], db_index=True)
    previous_retention_level = models.PositiveSmallIntegerField()
    new_retention_level = models.PositiveSmallIntegerField()
    previous_next_review_at = models.DateTimeField()
    new_next_review_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "review_events"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"], name="idx_re_user_created"),
            models.Index(fields=["score", "created_at"], name="idx_re_score_created"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} score={self.score}"


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
        db_index=True,
    )
    proficiency_level = models.CharField(
        max_length=2,
        choices=CEFRLevel.choices,
        default=CEFRLevel.B1,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_profiles"
        indexes = [
            models.Index(fields=["proficiency_level"], name="idx_up_level"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} ({self.proficiency_level})"
