from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from datetime import timedelta

from .learning_engine_service import LearningEngineError, evaluate_translation, generate_study_plan
from .models import (
    CEFRLevel,
    ClinicalScenario,
    ReviewEvent,
    TextDocument,
    TextTokenRelation,
    TranslationAttempt,
    UserKnowledge,
    UserProfile,
    WordClickEvent,
)
from .serializers import TextDocumentSerializer, TextTokenRelationSerializer
from .text_processing_service import TextDissector, TextDissectorError


def get_or_create_user_profile(user):
    default_level_by_username = {
        "marcos": CEFRLevel.C1,
        "caio": CEFRLevel.B1,
        "thais": CEFRLevel.A1,
    }
    level = default_level_by_username.get((user.username or "").strip().lower(), CEFRLevel.B1)
    profile, _ = UserProfile.objects.get_or_create(user=user, defaults={"proficiency_level": level})
    return profile


class AuthCsrfAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"csrfToken": get_token(request)}, status=status.HTTP_200_OK)


class AuthLoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = (request.data.get("username") or "").strip()
        password = request.data.get("password") or ""

        if not username or not password:
            return Response(
                {"detail": "Informe username e password."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(request, username=username, password=password)
        if not user:
            return Response({"detail": "Credenciais inválidas."}, status=status.HTTP_401_UNAUTHORIZED)

        login(request, user)
        profile = get_or_create_user_profile(user)
        return Response(
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "proficiency_level": profile.proficiency_level,
            },
            status=status.HTTP_200_OK,
        )


class AuthMeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = get_or_create_user_profile(request.user)
        return Response(
            {
                "id": request.user.id,
                "username": request.user.username,
                "email": request.user.email,
                "proficiency_level": profile.proficiency_level,
            },
            status=status.HTTP_200_OK,
        )


class AuthLogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response({"detail": "Logout realizado."}, status=status.HTTP_200_OK)


class ClinicalScenarioListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = get_or_create_user_profile(request.user)
        requested_level = (request.query_params.get("level") or "").strip().upper()
        valid_levels = {choice[0] for choice in CEFRLevel.choices}

        if requested_level:
            if requested_level not in valid_levels:
                return Response(
                    {"detail": "Parâmetro 'level' inválido. Use A1, B1 ou C1."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            selected_level = requested_level
        else:
            selected_level = profile.proficiency_level

        scenarios = list(
            ClinicalScenario.objects.filter(is_active=True, proficiency_level=selected_level)
            .order_by("id")
            .values("id", "text", "proficiency_level")
        )
        return Response(
            {
                "proficiency_level": profile.proficiency_level,
                "selected_level": selected_level,
                "count": len(scenarios),
                "items": scenarios,
            },
            status=status.HTTP_200_OK,
        )


class DocumentCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        text = (request.data.get("text") or "").strip()
        title = (request.data.get("title") or "Texto em alemão").strip()

        if not text:
            return Response(
                {"detail": "Campo 'text' é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            document_id = TextDissector(raw_text=text, title=title, created_by=request.user).process_and_persist()
            return Response({"document_id": document_id}, status=status.HTTP_201_CREATED)
        except TextDissectorError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {"detail": "Erro interno ao processar documento."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class DocumentDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

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
            user = request.user
            get_or_create_user_profile(user)

            study_payload = generate_study_plan(user, document_id, focus_word_id=parsed_word_id)

            for item in study_payload.get("items", []):
                word_token_id = item.get("word_token_id")
                if not word_token_id:
                    continue
                UserKnowledge.objects.get_or_create(
                    user=user,
                    word_token_id=word_token_id,
                    defaults={
                        "retention_level": 0,
                        "next_review_at": timezone.now(),
                    },
                )

            if parsed_word_id is not None:
                WordClickEvent.objects.create(
                    user=user,
                    text_document_id=document_id,
                    word_token_id=parsed_word_id,
                )

            if parsed_word_id is not None:
                study_payload["items"] = [
                    item for item in study_payload.get("items", []) if item.get("word_token_id") == parsed_word_id
                ]
                study_payload["study_items_count"] = len(study_payload["items"])

            return Response(study_payload, status=status.HTTP_200_OK)
        except LearningEngineError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {"detail": "Erro interno ao gerar flashcard."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class StudyEvaluateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        desafio_pt = (request.data.get("desafio_pt") or "").strip()
        tentativa_de = (request.data.get("tentativa_de") or "").strip()
        contexto_original = (request.data.get("contexto_original") or "").strip()

        if not desafio_pt:
            return Response(
                {"detail": "Campo 'desafio_pt' é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not tentativa_de:
            return Response(
                {"detail": "Campo 'tentativa_de' é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = request.user
            get_or_create_user_profile(user)

            result = evaluate_translation(
                desafio_pt=desafio_pt,
                tentativa_de=tentativa_de,
                contexto_original=contexto_original,
            )

            TranslationAttempt.objects.create(
                user=user,
                challenge_pt=desafio_pt,
                attempt_de=tentativa_de,
                context_original=contexto_original,
                is_correct=bool(result.get("correto", False)),
                feedback=result.get("feedback", ""),
                suggested_de=result.get("resposta_sugerida", ""),
            )
            return Response(result, status=status.HTTP_200_OK)
        except LearningEngineError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {"detail": "Erro interno ao avaliar tradução."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class StudyReviewListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            get_or_create_user_profile(user)

            due_knowledge = (
                UserKnowledge.objects.select_related("word_token")
                .filter(user=user, next_review_at__lte=timezone.now())
                .order_by("next_review_at")
            )

            cards = []
            for knowledge in due_knowledge:
                relation = (
                    TextTokenRelation.objects.select_related("text_document")
                    .filter(word_token_id=knowledge.word_token_id)
                    .order_by("-text_document__created_at")
                    .first()
                )

                if not relation:
                    continue

                context_sentence = ""
                desafio_traducao = ""
                nivel_c1 = []
                variacao_nativa = ""

                try:
                    study_payload = generate_study_plan(
                        user=user,
                        document_id=relation.text_document_id,
                        focus_word_id=knowledge.word_token_id,
                    )
                    item = (study_payload.get("items") or [{}])[0]
                    llm_result = study_payload.get("llm_result", {})
                    context_sentence = item.get("context_sentence", "")
                    desafio_traducao = llm_result.get("desafio_traducao", "")
                    nivel_c1 = llm_result.get("nivel_c1", []) or []
                    variacao_nativa = llm_result.get("variacao_nativa", "")
                except Exception:
                    context_sentence = relation.text_document.raw_text[:280]
                    desafio_traducao = f"Traduza mentalmente uma frase médica com '{knowledge.word_token.lemma}'."

                cards.append(
                    {
                        "id": knowledge.id,
                        "word_token_id": knowledge.word_token_id,
                        "word": knowledge.word_token.lemma,
                        "context_original": context_sentence,
                        "challenge_pt": desafio_traducao,
                        "nivel_c1": nivel_c1,
                        "variacao_nativa": variacao_nativa,
                        "next_review_at": knowledge.next_review_at,
                    }
                )

            return Response(cards, status=status.HTTP_200_OK)
        except Exception:
            return Response(
                {"detail": "Erro interno ao buscar revisões pendentes."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class StudyReviewSubmitAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, review_id: int):
        score = request.data.get("score")
        try:
            score = int(score)
        except (TypeError, ValueError):
            return Response(
                {"detail": "Campo 'score' deve ser inteiro entre 1 e 4."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if score not in [1, 2, 3, 4]:
            return Response(
                {"detail": "Campo 'score' deve ser 1, 2, 3 ou 4."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        day_map = {1: 1, 2: 2, 3: 3, 4: 7}

        try:
            user = request.user
            get_or_create_user_profile(user)

            knowledge = UserKnowledge.objects.get(id=review_id, user=user)
            previous_retention_level = knowledge.retention_level
            previous_next_review_at = knowledge.next_review_at
            knowledge.retention_level = score
            knowledge.next_review_at = timezone.now() + timedelta(days=day_map[score])
            knowledge.save(update_fields=["retention_level", "next_review_at", "updated_at"])

            ReviewEvent.objects.create(
                user=user,
                user_knowledge=knowledge,
                score=score,
                previous_retention_level=previous_retention_level,
                new_retention_level=knowledge.retention_level,
                previous_next_review_at=previous_next_review_at,
                new_next_review_at=knowledge.next_review_at,
            )

            return Response(
                {
                    "id": knowledge.id,
                    "retention_level": knowledge.retention_level,
                    "next_review_at": knowledge.next_review_at,
                },
                status=status.HTTP_200_OK,
            )
        except UserKnowledge.DoesNotExist:
            return Response({"detail": "Card de revisão não encontrado."}, status=status.HTTP_404_NOT_FOUND)
        except Exception:
            return Response(
                {"detail": "Erro interno ao salvar revisão."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
