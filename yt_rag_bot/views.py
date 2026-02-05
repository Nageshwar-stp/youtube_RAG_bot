import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .rag.services import ingest, answer
from django.shortcuts import render


@csrf_exempt
def ingest_video(request):
    data = json.loads(request.body)
    ingest(data["url"])
    return JsonResponse({"status": "ingested"})


@csrf_exempt
def ask_question(request):
    data = json.loads(request.body)
    reply = answer(data["question"])
    return JsonResponse({"answer": reply})

def home(request):
    return render(request, "home.html")