from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, get_current_user, require_tenant_write
from app.models.routine import RoutineAction, RoutineReminder
from app.models.user import User
from app.models.workspace import WorkspaceCase, WorkspaceDocument, WorkspaceTask
from app.schemas.routine import ChecklistCreate, OutcomeCreate, ReminderResponse, ReminderSet
from app.schemas.workspace import DocumentCreate, DocumentResponse
from app.services.routine_service import CHECKLISTS, cancel_reminders, previous_action, reminder_response
from app.services.workspace_service import authorized_case_query, get_case, get_document, get_task, require_case_write, require_task_write


router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/checklists")
async def list_checklists(current_user: CurrentUser):
    return {"items": list(CHECKLISTS.values())}


@router.post("/cases/{case_id}/checklists", status_code=201)
async def apply_checklist(case_id: str, payload: ChecklistCreate, request: Request, current_user: CurrentUser,
                          db: AsyncSession = Depends(get_db), _write: User = Depends(require_tenant_write)):
    from app.api.v1.endpoints.workspace import commit_mutation
    action, fingerprint = await previous_action(db, current_user, case_id, payload.request_id, "checklist", {"key": payload.key})
    case = await get_case(db, current_user, case_id)
    if current_user.role == "paralegal":
        require_task_write(current_user)
    else:
        require_case_write(current_user, case)
    if action:
        return {"task_ids": action.result["task_ids"], "created": False}
    tasks = [WorkspaceTask(tenant_id=current_user.tenant_id, case_id=case.id, title=title,
                           assigned_user_id=current_user.id) for title in CHECKLISTS[payload.key]["items"]]
    db.add_all(tasks)
    await db.flush()
    result = {"task_ids": [task.id for task in tasks]}
    action = RoutineAction(tenant_id=current_user.tenant_id, user_id=current_user.id, case_id=case.id,
        request_id=str(payload.request_id), kind="checklist", request_hash=fingerprint, result=result)
    db.add(action)
    await db.flush()
    await commit_mutation(db, request, current_user, "ROUTINE_CHECKLIST_APPLIED", "routine_actions", action.id,
                          {"key": payload.key, "task_count": len(tasks)})
    return result | {"created": True}


@router.get("/cases/{case_id}/outcomes")
async def list_outcomes(case_id: str, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    await get_case(db, current_user, case_id)
    documents = (await db.scalars(select(WorkspaceDocument).where(WorkspaceDocument.tenant_id == current_user.tenant_id,
        WorkspaceDocument.case_id == case_id, WorkspaceDocument.kind == "note", WorkspaceDocument.archived_at.is_(None))
        .order_by(WorkspaceDocument.created_at.desc()).limit(50))).all()
    return {"items": [{"id": item.id, "title": item.title, "content_text": item.content_text,
                       "created_at": item.created_at} for item in documents]}


@router.post("/cases/{case_id}/outcomes", response_model=DocumentResponse, status_code=201)
async def create_outcome(case_id: str, payload: OutcomeCreate, request: Request, current_user: CurrentUser,
                         db: AsyncSession = Depends(get_db), _write: User = Depends(require_tenant_write)):
    from app.api.v1.endpoints.workspace import create_document_record
    action, fingerprint = await previous_action(db, current_user, case_id, payload.request_id, "outcome",
        {"title": payload.title, "content_text": payload.content_text})
    case = await get_case(db, current_user, case_id)
    if current_user.role != "paralegal":
        require_case_write(current_user, case)
    if action:
        document = await get_document(db, current_user, action.result["document_id"])
        return DocumentResponse.model_validate(document)
    document = await create_document_record(DocumentCreate(case_id=case.id, client_id=case.client_id,
        kind="note", title=payload.title, content_text=payload.content_text), request, current_user, db, commit=False)
    db.add(RoutineAction(tenant_id=current_user.tenant_id, user_id=current_user.id, case_id=case.id,
        request_id=str(payload.request_id), kind="outcome", request_hash=fingerprint, result={"document_id": document.id}))
    await db.commit()
    return DocumentResponse.model_validate(document)


@router.get("/attention")
async def attention(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    active_task = exists(select(WorkspaceTask.id).where(WorkspaceTask.tenant_id == current_user.tenant_id,
        WorkspaceTask.case_id == WorkspaceCase.id, WorkspaceTask.status.in_(("pending", "in_progress"))))
    cases = (await db.scalars(authorized_case_query(current_user).where(WorkspaceCase.status == "open",
        WorkspaceCase.archived_at.is_(None), ~active_task).order_by(WorkspaceCase.created_at).limit(50))).all()
    reminders = (await db.scalars(select(RoutineReminder).where(RoutineReminder.tenant_id == current_user.tenant_id,
        RoutineReminder.user_id == current_user.id, RoutineReminder.status == "due", RoutineReminder.acknowledged_at.is_(None))
        .order_by(RoutineReminder.remind_at).limit(50))).all()
    items = []
    for reminder in reminders:
        try:
            task = await get_task(db, current_user, reminder.task_id)
        except HTTPException as exc:
            if exc.status_code == 404:
                continue
            raise
        if task.status in {"pending", "in_progress"} and task.manually_reviewed and task.due_at == reminder.due_at_snapshot:
            items.append(await reminder_response(db, reminder, task))
    return {"cases_without_next_action": [{"id": case.id, "title": case.title} for case in cases], "reminders": items, "limit": 50}


@router.get("/tasks/{task_id}/reminder")
async def read_reminder(task_id: str, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    task = await get_task(db, current_user, task_id)
    reminder = await db.scalar(select(RoutineReminder).where(RoutineReminder.tenant_id == current_user.tenant_id,
        RoutineReminder.user_id == current_user.id, RoutineReminder.task_id == task_id)
        .order_by(RoutineReminder.created_at.desc()).limit(1))
    return {"item": await reminder_response(db, reminder, task) if reminder else None}


@router.put("/tasks/{task_id}/reminder", response_model=ReminderResponse)
async def set_reminder(task_id: str, payload: ReminderSet, request: Request, current_user: CurrentUser,
                       db: AsyncSession = Depends(get_db), _write: User = Depends(require_tenant_write)):
    from app.api.v1.endpoints.workspace import commit_mutation
    task = await get_task(db, current_user, task_id, for_update=True)
    if task.revision != payload.expected_revision:
        raise HTTPException(409, "Tarefa alterada. Recarregue e confira a data antes de agendar.")
    if task.status not in {"pending", "in_progress"} or not task.due_at or not task.manually_reviewed:
        raise HTTPException(422, "O lembrete exige tarefa ativa e data conferida manualmente.")
    if not datetime.now(timezone.utc) < payload.remind_at <= task.due_at:
        raise HTTPException(422, "Escolha uma data futura até o horário da tarefa.")
    current = await db.scalar(select(RoutineReminder).where(RoutineReminder.tenant_id == current_user.tenant_id,
        RoutineReminder.user_id == current_user.id, RoutineReminder.task_id == task_id,
        RoutineReminder.status == "scheduled").with_for_update())
    if current and current.remind_at == payload.remind_at and current.due_at_snapshot == task.due_at:
        return await reminder_response(db, current, task)
    await cancel_reminders(db, current_user.tenant_id, task_id, user_id=current_user.id)
    reminder = RoutineReminder(tenant_id=current_user.tenant_id, user_id=current_user.id, task_id=task.id,
        task_revision=task.revision, due_at_snapshot=task.due_at, remind_at=payload.remind_at)
    db.add(reminder)
    await db.flush()
    result = await reminder_response(db, reminder, task)
    await commit_mutation(db, request, current_user, "ROUTINE_REMINDER_SCHEDULED", "routine_reminders", reminder.id)
    return result


@router.delete("/tasks/{task_id}/reminder", status_code=204)
async def remove_reminder(task_id: str, request: Request, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    from app.api.v1.endpoints.workspace import commit_mutation
    await get_task(db, current_user, task_id, for_update=True)
    await cancel_reminders(db, current_user.tenant_id, task_id, user_id=current_user.id)
    await commit_mutation(db, request, current_user, "ROUTINE_REMINDER_CANCELLED", "workspace_tasks", task_id)
    return Response(status_code=204)


@router.post("/reminders/{reminder_id}/acknowledge", status_code=204)
async def acknowledge_reminder(reminder_id: str, request: Request, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    from app.api.v1.endpoints.workspace import commit_mutation
    reminder = await db.scalar(select(RoutineReminder).where(RoutineReminder.id == reminder_id,
        RoutineReminder.tenant_id == current_user.tenant_id, RoutineReminder.user_id == current_user.id))
    if not reminder:
        raise HTTPException(404, "Lembrete não encontrado.")
    await get_task(db, current_user, reminder.task_id, for_update=True)
    reminder = await db.scalar(select(RoutineReminder).where(RoutineReminder.id == reminder_id,
        RoutineReminder.tenant_id == current_user.tenant_id).with_for_update().execution_options(populate_existing=True))
    if reminder.status != "due":
        raise HTTPException(409, "O lembrete ainda não está disponível ou foi cancelado.")
    if not reminder.acknowledged_at:
        reminder.acknowledged_at = datetime.now(timezone.utc)
        await commit_mutation(db, request, current_user, "ROUTINE_REMINDER_ACKNOWLEDGED", "routine_reminders", reminder.id)
    return Response(status_code=204)
