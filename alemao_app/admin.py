from django.contrib import admin

from .models import (
    ClinicalScenario,
    ReviewEvent,
    TextDocument,
    TextTokenRelation,
    TranslationAttempt,
    UserKnowledge,
    UserProfile,
    WordClickEvent,
    WordToken,
)


@admin.register(TextDocument)
class TextDocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "created_by", "title", "complexity_score", "created_at", "preview")
    list_filter = ("created_by",)
    search_fields = ("title", "raw_text", "created_by__username")
    ordering = ("-created_at",)

    @admin.display(description="Texto")
    def preview(self, obj):
        return (obj.raw_text[:100] + "...") if len(obj.raw_text) > 100 else obj.raw_text


@admin.register(WordToken)
class WordTokenAdmin(admin.ModelAdmin):
    list_display = ("id", "lemma", "pos_tag", "gender")
    list_filter = ("pos_tag", "gender")
    search_fields = ("lemma",)
    ordering = ("lemma",)


@admin.register(TextTokenRelation)
class TextTokenRelationAdmin(admin.ModelAdmin):
    list_display = ("id", "text_document", "word_token", "position", "grammatical_case")
    list_filter = ("grammatical_case",)
    search_fields = ("text_document__title", "word_token__lemma")
    ordering = ("text_document", "position")


@admin.register(UserKnowledge)
class UserKnowledgeAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "word_token", "retention_level", "next_review_at", "updated_at")
    list_filter = ("retention_level",)
    search_fields = ("user__username", "word_token__lemma")
    ordering = ("next_review_at",)


@admin.register(ClinicalScenario)
class ClinicalScenarioAdmin(admin.ModelAdmin):
    list_display = ("id", "proficiency_level", "is_active", "created_at", "preview")
    list_filter = ("proficiency_level", "is_active")
    search_fields = ("text",)
    ordering = ("id",)

    @admin.display(description="Frase")
    def preview(self, obj):
        return (obj.text[:140] + "...") if len(obj.text) > 140 else obj.text


@admin.register(WordClickEvent)
class WordClickEventAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "word_token", "text_document", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__username", "word_token__lemma", "text_document__title")
    ordering = ("-created_at",)


@admin.register(TranslationAttempt)
class TranslationAttemptAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "is_correct", "created_at", "challenge_preview", "attempt_preview")
    list_filter = ("is_correct", "created_at")
    search_fields = ("user__username", "challenge_pt", "attempt_de", "feedback", "suggested_de")
    ordering = ("-created_at",)

    @admin.display(description="Desafio (PT)")
    def challenge_preview(self, obj):
        return (obj.challenge_pt[:90] + "...") if len(obj.challenge_pt) > 90 else obj.challenge_pt

    @admin.display(description="Tentativa (DE)")
    def attempt_preview(self, obj):
        return (obj.attempt_de[:90] + "...") if len(obj.attempt_de) > 90 else obj.attempt_de


@admin.register(ReviewEvent)
class ReviewEventAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "user_knowledge",
        "score",
        "previous_retention_level",
        "new_retention_level",
        "created_at",
    )
    list_filter = ("score", "created_at")
    search_fields = ("user__username", "user_knowledge__word_token__lemma")
    ordering = ("-created_at",)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "proficiency_level", "created_at", "updated_at")
    list_filter = ("proficiency_level",)
    search_fields = ("user__username", "user__email")
    ordering = ("user__username",)
