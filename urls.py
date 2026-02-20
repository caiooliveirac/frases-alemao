from django.urls import path

from .views import DocumentCreateAPIView, DocumentDetailAPIView, StudyGenerateAPIView


urlpatterns = [
    path("api/documents/", DocumentCreateAPIView.as_view(), name="api-documents-create"),
    path("api/documents/<int:document_id>/", DocumentDetailAPIView.as_view(), name="api-documents-detail"),
    path("api/study/generate/", StudyGenerateAPIView.as_view(), name="api-study-generate"),
]
