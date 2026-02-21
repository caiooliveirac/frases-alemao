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


class AnalyzeRequestSerializer(serializers.Serializer):
    document_id = serializers.IntegerField(min_value=1)
    limit = serializers.IntegerField(min_value=1, max_value=20, default=20, required=False)


class AnalyzeLiteTokenSerializer(serializers.Serializer):
    token_id = serializers.IntegerField(min_value=1)
    lemma = serializers.CharField(allow_blank=False, trim_whitespace=False)
    pos = serializers.CharField(allow_blank=False, trim_whitespace=False)
    gender = serializers.CharField(allow_null=True, allow_blank=True, required=False)


class AnalyzeLiteResponseSerializer(serializers.Serializer):
    document_id = serializers.IntegerField(min_value=1)
    tokens = AnalyzeLiteTokenSerializer(many=True)

    def validate_tokens(self, value):
        if len(value) > 20:
            raise serializers.ValidationError("No máximo 20 tokens são permitidos.")
        return value


class PhraseAnalysisTokenSerializer(serializers.Serializer):
    token_id = serializers.IntegerField(min_value=1)
    surface = serializers.CharField(allow_blank=False, trim_whitespace=False)
    lemma = serializers.CharField(allow_blank=False, trim_whitespace=False)
    pos = serializers.CharField(allow_blank=False, trim_whitespace=False)
    gender = serializers.CharField(allow_null=True, allow_blank=True, required=False)
    case = serializers.ChoiceField(choices=["Nom", "Akk", "Dat", "?"])
    syntactic_role = serializers.ChoiceField(choices=["subject", "object", "modifier", "?"])
    confidence = serializers.FloatField(min_value=0.0, max_value=1.0)


class PhraseAnalysisResponseSerializer(serializers.Serializer):
    document_id = serializers.IntegerField(min_value=1)
    tokens = PhraseAnalysisTokenSerializer(many=True)

    def validate_tokens(self, value):
        if len(value) > 20:
            raise serializers.ValidationError("No máximo 20 tokens são permitidos.")
        return value
