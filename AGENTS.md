<!-- bmad:context -->
<!-- Verified 2026-09-01 against 49ae5667e16fe831abca52d12667872e9bd7fbe3. Managed by bmad-project-context; edits inside this block are replaced on refresh. Keep anything you want preserved outside the markers. -->

## units-backend

Django REST backend for Units, a UAE on-prem property management platform (tenant, PMC, and owner workflows). Django project `property_management`, apps: `auth_service`, `user_service`, `property`, `payment`, `charges`, `lead`, `complaint`, `lease`, `terms`, `notification`. DRF + drf_yasg (Swagger). Deployed via gunicorn behind the parent repo's docker-compose/nginx (`../../docker-compose.yml`).

## Policy

- Branch off `develop`, PR back into `develop` — no direct pushes.

## Where things are

- Django settings: `property_management/settings.py`.
- Container build/start (WeasyPrint system deps, collectstatic, migrate, gunicorn): `../../docker_config/python_config/`.

<!-- /bmad:context -->
