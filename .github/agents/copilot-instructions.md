# nimr-billing Development Guidelines

Auto-generated from all feature plans. Last updated: 2025-12-29

## Active Technologies

- Python 3.10 + Django 4.2, Django REST Framework, Celery, Redis, django-weasyprint/WeasyPrint, requests (001-email-invoice-receipt)

## Project Structure

```text
src/
tests/
```

## Commands

cd src [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] pytest [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] ruff check .

## Code Style

Python 3.10: Follow standard conventions

## Recent Changes

- 001-email-invoice-receipt: Added Python 3.10 + Django 4.2, Django REST Framework, Celery, Redis, django-weasyprint/WeasyPrint, requests

<!-- MANUAL ADDITIONS START -->
## Repo Reality (Manual)

### Actual Project Structure

```text
accounts/
api/
auth/
billing/
core/
home/
templates/
static/
manage.py
requirements.txt
```

### Common Dev Commands

- Run web: `python manage.py runserver`
- Run tests: `python manage.py test`
- Run Celery worker: `celery -A core worker -l info`
- Run Celery beat: `celery -A core beat -l info`

<!-- MANUAL ADDITIONS END -->
