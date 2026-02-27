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

    # -------- GET METHOD --------
    if request.method == "GET":
        term_type = request.query_params.get("type")

        if term_type == "login":
            terms = TermsAndConditions.objects.filter(
                key="login/signup",
                is_active=True
            )
            msg = "Login/Signup terms fetched"

        elif term_type == "commercial":
            terms = TermsAndConditions.objects.filter(
                key="commercial",
                is_active=True
            )
            msg = "Commercial terms fetched"

        else:
            terms = TermsAndConditions.objects.all()
            msg = "All terms fetched"

        contents = [
            {
                "key": t.key,
                "title": t.title,
                "description": t.description
            }
            for t in terms
        ]

        return Response({
            "contents": contents,
            "message": msg,
            "status": 200
        }, status=status.HTTP_200_OK)

    # -------- POST METHOD --------
    elif request.method == "POST":
        try:
            if "login/signup" in request.data:
                target_data = request.data.get("login/signup")
                key_val = "login/signup"

            elif "commercial" in request.data:
                target_data = request.data.get("commercial")
                key_val = "commercial"

            else:
                return Response({
                    "contents": None,
                    "message": "Key 'login/signup' or 'commercial' required",
                    "status": 400
                }, status=400)

            new_term = TermsAndConditions.objects.create(
                key=key_val,
                title=target_data.get("title"),
                description=target_data.get("description")
            )

            return Response({
                "contents": {
                    "key": new_term.key,
                    "title": new_term.title,
                    "description": new_term.description
                },
                "message": "Data inserted successfully",
                "status": 201
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({
                "contents": None,
                "message": str(e),
                "status": 500
            }, status=500)