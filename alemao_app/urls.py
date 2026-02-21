from django.views.generic import TemplateView
from django.urls import path

from .views import (
    AnalyzeDeepAPIView,
    AnalyzeLiteAPIView,
    AuthCsrfAPIView,
    AuthLoginAPIView,
    AuthLogoutAPIView,
    AuthMeAPIView,
    ClinicalScenarioListAPIView,
    DocumentCreateAPIView,
    DocumentDetailAPIView,
    PhraseAnalysisStrictAPIView,
    StudyEvaluateAPIView,
    StudyGenerateAPIView,
    StudyReviewListAPIView,
    StudyReviewSubmitAPIView,
)


urlpatterns = [
    path("", TemplateView.as_view(template_name="index.html"), name="app-root"),
    path("api/auth/csrf/", AuthCsrfAPIView.as_view(), name="api-auth-csrf"),
    path("api/auth/login/", AuthLoginAPIView.as_view(), name="api-auth-login"),
    path("api/auth/me/", AuthMeAPIView.as_view(), name="api-auth-me"),
    path("api/auth/logout/", AuthLogoutAPIView.as_view(), name="api-auth-logout"),
    path("api/scenarios/", ClinicalScenarioListAPIView.as_view(), name="api-scenarios-list"),
    path("api/analyze_lite", AnalyzeLiteAPIView.as_view(), name="api-analyze-lite"),
    path("api/analyze_lite/", AnalyzeLiteAPIView.as_view(), name="api-analyze-lite-slash"),
    path("api/analyze_deep", AnalyzeDeepAPIView.as_view(), name="api-analyze-deep"),
    path("api/analyze_deep/", AnalyzeDeepAPIView.as_view(), name="api-analyze-deep-slash"),
    path("api/documents/", DocumentCreateAPIView.as_view(), name="api-documents-create"),
    path("api/documents/<int:document_id>/", DocumentDetailAPIView.as_view(), name="api-documents-detail"),
    path("api/documents/<int:document_id>/analysis/", PhraseAnalysisStrictAPIView.as_view(), name="api-documents-analysis"),
    path("api/study/generate/", StudyGenerateAPIView.as_view(), name="api-study-generate"),
    path("api/study/evaluate/", StudyEvaluateAPIView.as_view(), name="api-study-evaluate"),
    path("api/study/review/", StudyReviewListAPIView.as_view(), name="api-study-review-list"),
    path("api/study/review/<int:review_id>/", StudyReviewSubmitAPIView.as_view(), name="api-study-review-submit"),
]
