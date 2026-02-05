from django.contrib import admin
from django.urls import path
from .views import ingest_video, ask_question, home

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home),

    # RAG API endpoints
    path("api/ingest/", ingest_video),
    path("api/ask/", ask_question),
]
