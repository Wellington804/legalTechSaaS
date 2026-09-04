from celery import Celery
from app.core.config import settings
from app.core.observability import init_sentry

init_sentry()

celery_app = Celery(
    "legaltech_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.services.tasks", "app.services.push_tasks", "app.services.routine_tasks", "app.services.controladoria_tasks", "app.services.document_tasks", "app.services.calendar_sync_tasks", "app.services.autentique_tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Sao_Paulo",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,
    result_expires=3600,
    beat_schedule={
        "reconcile-notification-deliveries": {
            "task": "tasks.reconcile_notification_deliveries",
            "schedule": 60.0,
        },
        "dispatch-web-push": {"task": "push.dispatch_pending", "schedule": 30.0},
        "dispatch-routine-reminders": {"task": "routines.dispatch_reminders", "schedule": 30.0},
        "poll-datajud-monitoring": {"task": "controladoria.poll_datajud", "schedule": 900.0},
        "reconcile-active-calendars": {"task": "calendar.reconcile_active", "schedule": 900.0},
        "reconcile-autentique-artifacts": {"task": "autentique.reconcile_signed_artifacts", "schedule": 300.0},
        "purge-document-trash": {"task": "documents.purge_trash", "schedule": 3600.0, "options": {"queue": "documents"}},
        "purge-expired-ai-conversations": {"task": "tasks.purge_expired_ai_conversations", "schedule": 3600.0},
    },
)
