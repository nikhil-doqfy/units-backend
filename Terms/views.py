import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import TermsAndConditions


@csrf_exempt
def terms_api(request):

    if request.method == 'GET':
        terms = list(TermsAndConditions.objects.values())
        return JsonResponse({
            "status": "HTTP_200_OK",
            "message": "Data retrieved successfully",
            "data": terms
        }, status=200)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)

            if not data.get('title') or not data.get('description'):
                return JsonResponse({
                    "status": "HTTP_400_BAD_REQUEST",
                    "message": "Title and Description are required"
                }, status=400)

            term = TermsAndConditions.objects.create(
                title=data.get('title'),
                description=data.get('description')
            )

            return JsonResponse({
                "status": "HTTP_201_CREATED",
                "message": "Terms and Conditions created successfully",
                "id": term.id
            }, status=201)

        except Exception as e:
            return JsonResponse({
                "status": "HTTP_500_INTERNAL_SERVER_ERROR",
                "message": str(e)
            }, status=500)

    return JsonResponse({
        "status": "HTTP_405_METHOD_NOT_ALLOWED",
        "message": f"Method {request.method} is not allowed"
    }, status=405)