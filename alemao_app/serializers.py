from rest_framework import serializers

from .models import TextDocument, TextTokenRelation, WordToken


class WordTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = WordToken
        fields = ["id", "lemma", "pos_tag", "gender"]


class TextTokenRelationSerializer(serializers.ModelSerializer):
    word = WordTokenSerializer(source="word_token", read_only=True)

    class Meta:
        model = TextTokenRelation
        fields = [
            "id",
            "text_document",
            "word_token",
            "word",
            "position",
            "grammatical_case",
        ]


class TextDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = TextDocument
        fields = ["id", "created_by", "title", "raw_text", "complexity_score", "created_at"]
