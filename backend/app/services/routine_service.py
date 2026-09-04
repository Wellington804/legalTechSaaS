"""Manual-date reminders. No legal deadline calculation or external I/O here."""
import hashlib
import json
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select, update

from app.core.dependencies import ensure_tenant_write_access
from app.models.push import PushDelivery
from app.models.routine import RoutineAction, RoutineReminder
from app.models.user import User
from app.models.workspace import WorkspaceTask
from app.schemas.routine import ReminderResponse
from app.services.push_service import enqueue_user_push
from app.services.workspace_service import get_task, lock_workspace_tenant


CHECKLISTS = {
    "intake": {"key": "intake", "title": "Primeiro atendimento", "items": ["Conferir cadastro e meios de contato", "Registrar relato e objetivo do atendimento", "Conferir possíveis conflitos de interesse", "Definir próxima ação com o cliente"]},
    "documents": {"key": "documents", "title": "Conferência de documentos", "items": ["Listar documentos necessários ao atendimento", "Conferir legibilidade e identificação dos arquivos", "Registrar documentos pendentes", "Confirmar recebimento e organizar documentos no caso"]},
    "hearing": {"key": "hearing", "title": "Preparação de audiência ou diligência", "items": ["Conferir manualmente data, horário e local", "Confirmar contato e orientações com os participantes", "Separar documentos necessários", "Registrar resultado e próxima ação após o compromisso"]},
}


async def previous_action(db, user, case_id, request_id, kind, values):
    # Reuse the existing quota lock for bounded pilot actions and concurrent retries.
    await lock_workspace_tenant(db, user.tenant_id)
    fingerprint = hashlib.sha256(json.dumps([case_id, kind, values], ensure_ascii=True, sort_keys=True).encode()).hexdigest()
    action = await db.scalar(select(RoutineAction).where(RoutineAction.tenant_id == user.tenant_id,
        RoutineAction.user_id == user.id, RoutineAction.request_id == str(request_id)))
    if action and action.request_hash != fingerprint:
        raise HTTPException(409, "Identificador já utilizado em outra solicitação.")
    return action, fingerprint


async def cancel_reminders(db, tenant_id, task_id, *, user_id=None):
    statement = select(RoutineReminder).where(RoutineReminder.tenant_id == tenant_id,
        RoutineReminder.task_id == task_id, RoutineReminder.status.in_(("scheduled", "due"))).with_for_update()
    if user_id:
        statement = statement.where(RoutineReminder.user_id == user_id)
    reminders = (await db.scalars(statement)).all()
    for reminder in reminders:
        reminder.status = "cancelled"
        await db.execute(update(PushDelivery).where(PushDelivery.tenant_id == tenant_id,
            PushDelivery.reminder_id == reminder.id, PushDelivery.status == "queued")
            .values(status="cancelled", error_code="reminder_cancelled"))
    await db.flush()


async def reminder_is_authorized(db, reminder, *, user=None):
    """Recheck current ACL, account, subscription and manual date before either outbox stage."""
    if reminder.status == "cancelled" or reminder.acknowledged_at:
        return False
    user = user or await db.scalar(select(User).where(User.tenant_id == reminder.tenant_id,
        User.id == reminder.user_id, User.is_active.is_(True)))
    if not user or not user.is_active:
        return False
    try:
        await ensure_tenant_write_access(db, reminder.tenant_id)
        task = await get_task(db, user, reminder.task_id)
    except HTTPException:
        return False
    return bool(task.status in {"pending", "in_progress"} and task.manually_reviewed
                and task.due_at == reminder.due_at_snapshot)


async def reminder_response(db, reminder, task):
    statuses = set((await db.scalars(select(PushDelivery.status).where(PushDelivery.tenant_id == reminder.tenant_id,
        PushDelivery.user_id == reminder.user_id, PushDelivery.reminder_id == reminder.id))).all())
    push_status = reminder.push_requested
    if "accepted" in statuses:
        push_status = "accepted"
    elif statuses & {"processing", "queued"}:
        push_status = "pending"
    elif "unknown" in statuses:
        push_status = "unknown"
    elif statuses:
        push_status = "failed"
    return ReminderResponse(id=reminder.id, task_id=task.id, task_title=task.title, case_id=task.case_id,
        remind_at=reminder.remind_at, status=reminder.status, push_status=push_status,
        acknowledged_at=reminder.acknowledged_at)


async def dispatch_reminder(db, reminder_id, tenant_id):
    """One durable transaction; lock task before reminder, as with editing/rescheduling."""
    reminder = await db.scalar(select(RoutineReminder).where(RoutineReminder.id == reminder_id,
        RoutineReminder.tenant_id == tenant_id))
    if not reminder:
        return "ignored"
    task = await db.scalar(select(WorkspaceTask).where(WorkspaceTask.id == reminder.task_id,
        WorkspaceTask.tenant_id == tenant_id).with_for_update())
    reminder = await db.scalar(select(RoutineReminder).where(RoutineReminder.id == reminder_id,
        RoutineReminder.tenant_id == tenant_id).with_for_update().execution_options(populate_existing=True))
    now = datetime.now(timezone.utc)
    if reminder.status != "scheduled" or reminder.remind_at > now:
        return "ignored"
    if not task or not await reminder_is_authorized(db, reminder):
        reminder.status = "cancelled"
        return "cancelled"
    # The in-app record stays due even with disabled push/no device/network failure.
    reminder.status = "due"
    count = await enqueue_user_push(db, tenant_id=tenant_id, user_id=reminder.user_id,
        event_key=f"reminder:{reminder.id}", kind="task_reminder", case_id=task.case_id,
        task_id=task.id, reminder_id=reminder.id)
    reminder.push_requested = "pending" if count else "unavailable"
    return "due"
