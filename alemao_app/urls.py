from django.urls import path

from .views import (
    AuthCsrfAPIView,
    AuthLoginAPIView,
    AuthLogoutAPIView,
    AuthMeAPIView,
    ClinicalScenarioListAPIView,
    DocumentCreateAPIView,
    DocumentDetailAPIView,
    StudyEvaluateAPIView,
    StudyGenerateAPIView,
    StudyReviewListAPIView,
    StudyReviewSubmitAPIView,
)


urlpatterns = [
    path("api/auth/csrf/", AuthCsrfAPIView.as_view(), name="api-auth-csrf"),
    path("api/auth/login/", AuthLoginAPIView.as_view(), name="api-auth-login"),
    path("api/auth/me/", AuthMeAPIView.as_view(), name="api-auth-me"),
    path("api/auth/logout/", AuthLogoutAPIView.as_view(), name="api-auth-logout"),
    path("api/scenarios/", ClinicalScenarioListAPIView.as_view(), name="api-scenarios-list"),
    path("api/documents/", DocumentCreateAPIView.as_view(), name="api-documents-create"),
    path("api/documents/<int:document_id>/", DocumentDetailAPIView.as_view(), name="api-documents-detail"),
    path("api/study/generate/", StudyGenerateAPIView.as_view(), name="api-study-generate"),
    path("api/study/evaluate/", StudyEvaluateAPIView.as_view(), name="api-study-evaluate"),
    path("api/study/review/", StudyReviewListAPIView.as_view(), name="api-study-review-list"),
    path("api/study/review/<int:review_id>/", StudyReviewSubmitAPIView.as_view(), name="api-study-review-submit"),
]
