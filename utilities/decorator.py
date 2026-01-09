from functools import wraps
from user_service.models import UserProfile
from utilities import constants, status
from utilities.helper_functions import prepare_response, is_password_expire
from utilities.jwt_token import get_jwt_token, decode_jwt_token
# from property_management.models import Role, ApiPermissions, RolePermission
from utilities import constants

# #===================================================
# # ROLE AND PERMISSIONS DECORATOR
# #===================================================
# def check_api_permissions(request, function, *args, **kwargs):
#     user_detail = request.user

#     groups = user_detail.groups.all()
#     if not groups.exists():
#         return prepare_response(
#             message=constants.USER_DOES_NOT_EXIST,
#             status=status.HTTP_404_NOT_FOUND
#         )

#     if groups.filter(name="ORGANISATION-ADMIN").exists():
#         return function(request, *args, **kwargs)
    
#     api_permissions = ApiPermissions.objects.filter(path=request.path, request_method=request.method)
#     if not api_permissions.exists():
#         return prepare_response(
#             message=constants.PERMISSION_DENIED_SUCCESS,
#             status=status.HTTP_400_BAD_REQUEST
#         )
    
#     api_permission = api_permissions.first()
    
#     roles = Role.objects.filter(name__in=groups).order_by("priority")
#     if not roles.exists():
#         return prepare_response(
#             message=constants.USER_ROLE_DOES_NOT_EXIST,
#             status=status.HTTP_404_NOT_FOUND
#         )

#     highest_priority_role = roles.first()
#     user_permissions = RolePermission.objects.filter(
#         role=highest_priority_role,
#         permission=api_permission.permission
#     )

#     if not user_permissions.exists():
#         return prepare_response(
#             message=constants.PERMISSION_DOES_NOT_EXIST,
#             status=status.HTTP_404_NOT_FOUND
#         )

#     user_permission = user_permissions.first()

#     if api_permission.permission_type == constants.VIEW_ONLY and user_permission.view_only:
#         return function(request, *args, **kwargs)
#     elif api_permission.permission_type == constants.MODIFIED and user_permission.modified:
#         return function(request, *args, **kwargs)
#     elif api_permission.permission_type == constants.ADD and user_permission.add:
#         return function(request, *args, **kwargs)
#     elif api_permission.permission_type == constants.DELETE and user_permission.delete:
#         return function(request, *args, **kwargs)
#     elif api_permission.permission_type == constants.TERMINATED and user_permission.terminate:
#         return function(request, *args, **kwargs)
    
#     else:
#         return prepare_response(
#             message=constants.PERMISSION_DOES_NOT_EXIST,
#             status=status.HTTP_400_BAD_REQUEST
#         )

# # ------ Check api's permissions ------
# def is_permission_authenticate(function):
#     def wrap(request, *args, **kwargs):
#         return check_api_permissions(request, function, *args, **kwargs)
    
#     wrap.__doc__ = function.__doc__
#     wrap.__name__ = function.__name__
#     return wrap



def is_request_authenticated(function):
    def wrap(request, *args, **kwargs):
        token = request.headers.get('Authorization')
        if token:
            token = get_jwt_token(token) 
            if not token: 
                return prepare_response(
                    message=constants.INVALID_TOKEN_PAYLOAD, 
                    status=status.HTTP_401_UNAUTHORIZED
                )   
            decoded_token = decode_jwt_token(token)
            if 'error' in decoded_token:
                return prepare_response(
                    message=decoded_token.get('error'), 
                    status=status.HTTP_401_UNAUTHORIZED
                ) 
            user_email = decoded_token.get("email")
            user_profile = UserProfile.objects.filter(user__email=user_email).first()
            if not user_profile:
                return prepare_response(
                    message=constants.AUTH_USER_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )
            
            if user_profile.token != token:
                return prepare_response(
                    message=constants.TOKEN_INVALID_OR_EXPIRED,
                    status=status.HTTP_401_UNAUTHORIZED
                )
                        
            request.user = user_profile  

            if is_password_expire(user_profile):
                return prepare_response(
                    message=constants.PASSWORD_EXPIRED,
                    status=status.HTTP_401_UNAUTHORIZED
                )
            # return check_api_permissions(request, function, *args, **kwargs)
        else:
            return prepare_response(
                message=constants.INVALID_LOGIN_DETAILS,
                status=status.HTTP_401_UNAUTHORIZED
            )
            
    wrap.__doc__ = function.__doc__
    wrap.__name__ = function.__name__
    return wrap