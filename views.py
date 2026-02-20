from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .learning_engine_service import LearningEngineError, generate_study_plan
from .models import TextDocument, TextTokenRelation
from .serializers import TextDocumentSerializer, TextTokenRelationSerializer
from .text_processing_service import TextDissector, TextDissectorError


class DocumentCreateAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        text = (request.data.get("text") or "").strip()
        title = (request.data.get("title") or "Texto em alemão").strip()

        if not text:
            return Response(
                {"detail": "Campo 'text' é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            document_id = TextDissector(raw_text=text, title=title).process_and_persist()
            return Response({"document_id": document_id}, status=status.HTTP_201_CREATED)
        except TextDissectorError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {"detail": "Erro interno ao processar documento."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class DocumentDetailAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, document_id: int):
        try:
            document = TextDocument.objects.get(id=document_id)
        except TextDocument.DoesNotExist:
            return Response({"detail": "Documento não encontrado."}, status=status.HTTP_404_NOT_FOUND)

        relations = (
            TextTokenRelation.objects.select_related("word_token")
            .filter(text_document_id=document_id)
            .order_by("position")
        )

        return Response(
            {
                "document": TextDocumentSerializer(document).data,
                "tokens": TextTokenRelationSerializer(relations, many=True).data,
            },
            status=status.HTTP_200_OK,
        )


class StudyGenerateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        document_id = request.data.get("document_id")
        word_id = request.data.get("word_id")

        if not document_id:
            return Response(
                {"detail": "Campo 'document_id' é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            document_id = int(document_id)
        except (TypeError, ValueError):
            return Response(
                {"detail": "Campo 'document_id' deve ser inteiro."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        parsed_word_id = None
        if word_id is not None:
            try:
                parsed_word_id = int(word_id)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "Campo 'word_id' deve ser inteiro."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            study_payload = generate_study_plan(request.user, document_id)

            if parsed_word_id is not None:
                study_payload["items"] = [
                    item for item in study_payload.get("items", []) if item.get("word_token_id") == parsed_word_id
                ]

                llm_items = study_payload.get("llm_result", {}).get("items", [])
                filtered_llm_items = [
                    item for item in llm_items if item.get("word_token_id") == parsed_word_id
                ]
                study_payload["llm_result"] = {"items": filtered_llm_items}
                study_payload["study_items_count"] = len(study_payload["items"])

            return Response(study_payload, status=status.HTTP_200_OK)
        except LearningEngineError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {"detail": "Erro interno ao gerar flashcard."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
