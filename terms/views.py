from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework import status
from .models import TermsAndConditions

@csrf_exempt
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticatedOrReadOnly])
def terms_list_create(request):
    
    # --- GET METHOD ---
    if request.method == "GET":
        term_type = request.query_params.get("type")
        
        # Filtering using the exact keys you requested
        if term_type == "login":
            terms = TermsAndConditions.objects.filter(key="login/signup", is_active=True)
            msg = "Login/Signup terms fetched"
        elif term_type == "commercial":
            terms = TermsAndConditions.objects.filter(key="commercial", is_active=True)
            msg = "Commercial terms fetched"
        else:
            terms = TermsAndConditions.objects.all()
            msg = "All terms fetched"

        contents = [{"key": t.key, "title": t.title, "description": t.description} for t in terms]

        return Response({
            "status": "success",
            "message": msg,
            "contents": contents
        }, status=status.HTTP_200_OK)

    # --- POST METHOD ---
    elif request.method == "POST":
        try:
            # Check for the keys in the request body
            if "login/signup" in request.data:
                target_data = request.data.get("login/signup")
                key_val = "login/signup"
            elif "commercial" in request.data:
                target_data = request.data.get("commercial")
                key_val = "commercial"
            else:
                return Response({
                    "status": "failed", 
                    "message": "Key 'login/signup' or 'commercial' required", 
                    "contents": None
                }, status=400)

            new_term = TermsAndConditions.objects.create(
                key=key_val,
                title=target_data.get("title"),
                description=target_data.get("description")
            )

            return Response({
                "status": "success",
                "message": "Data inserted successfully",
                "contents": {
                    "key": new_term.key,
                    "title": new_term.title,
                    "description": new_term.description
                }
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"status": "failed", "message": str(e), "contents": None}, status=500)

'''from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Terms
import json


@csrf_exempt
def terms_api(request):
    if request.method == 'GET':
        terms = Terms.objects.all()
        content = [{
            "key": term.key,
            "title": term.title,
            "description": term.description
        } for term in terms]
        
        response_data = {
            "content": content,
            "message": "",
            "status": 200
        }
        return JsonResponse(response_data)
    
    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            term = Terms.objects.create(
                key=data.get('key'),
                title=data.get('title'),
                description=data.get('description')
            )
            
            response_data = {
                "content": {
                    "key": term.key,
                    "title": term.title,
                    "description": term.description
                },
                "message": "Terms inserted successfully",
                "status": 201
            }
            return JsonResponse(response_data, status=201)
            
        except json.JSONDecodeError:
            return JsonResponse({
                "content": None,
                "message": "Invalid JSON data",
                "status": 400
            }, status=400)'''