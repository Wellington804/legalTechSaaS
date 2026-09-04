"""Internal-only, audited subscription support commands.

Run from an operator-controlled backend environment; these commands never
charge a payment method or represent that a payment was received.
"""
import argparse
import asyncio
import json
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import func, select, text

from app.core.database import AsyncSessionLocal
from app.models.account import PrivacyRequest, SubscriptionRequest
from app.models.tenant import Tenant
from app.models.user import User
from app.services.audit_service import AuditService


STATUSES = {"trial", "active", "past_due", "suspended", "cancelled"}
PENDING_REQUEST_STATUSES = {"received", "in_progress"}
PENDING_PRIVACY_STATUSES = {"received", "in_review"}
MAX_QUOTA_USERS = 10_000
MAX_QUOTA_STORAGE_BYTES = 10 * 1024**4  # 10 TiB
MAX_QUOTA_MESSAGES = 10_000_000


def required_text(value: str, flag: str, *, maximum: int) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise SystemExit(f"{flag} must not be blank")
    if len(normalized) > maximum:
        raise SystemExit(f"{flag} must contain at most {maximum} characters")
    return normalized


def bounded_positive(value: str | int, flag: str, *, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(f"{flag} must be an integer") from exc
    if not 1 <= parsed <= maximum:
        raise argparse.ArgumentTypeError(f"{flag} must be between 1 and {maximum}")
    return parsed


def parse_aware_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("--ends-at must be an ISO-8601 timestamp with timezone") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("--ends-at must include a timezone offset")
    return parsed.astimezone(timezone.utc)


def _positive_argument(flag: str, maximum: int):
    return lambda value: bounded_positive(value, flag, maximum=maximum)


async def _set_tenant_context(db, tenant_id: str) -> None:
    if db.bind and db.bind.dialect.name == "postgresql":
        await db.execute(
            text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
            {"tenant_id": tenant_id},
        )


def _apply_end_date(tenant: Tenant, status: str, ends_at: datetime | None) -> None:
    if status == "trial":
        if ends_at is not None:
            tenant.trial_ends_at = ends_at
        return
    if ends_at is not None:
        tenant.subscription_ends_at = ends_at
    elif status == "active":
        tenant.subscription_ends_at = None
    elif status == "cancelled":
        tenant.subscription_ends_at = datetime.now(timezone.utc)


async def set_subscription_status(args: argparse.Namespace) -> None:
    async with AsyncSessionLocal() as db:
        tenant = await db.scalar(select(Tenant).where(Tenant.id == args.tenant_id).with_for_update())
        if not tenant:
            raise SystemExit("Tenant not found")
        await _set_tenant_context(db, tenant.id)

        subscription_request = None
        if args.request_id:
            subscription_request = await db.scalar(
                select(SubscriptionRequest)
                .where(
                    SubscriptionRequest.id == args.request_id,
                    SubscriptionRequest.tenant_id == tenant.id,
                    SubscriptionRequest.status.in_(PENDING_REQUEST_STATUSES),
                )
                .with_for_update()
            )
            if not subscription_request:
                raise SystemExit("Pending subscription request not found for this tenant")

        previous_status = tenant.subscription_status
        tenant.subscription_status = args.status
        if args.plan:
            tenant.subscription_plan = args.plan
        for field in ("quota_users", "quota_storage_bytes", "quota_messages"):
            value = getattr(args, field)
            if value is not None:
                setattr(tenant, field, value)
        if args.status in {"active", "cancelled"}:
            tenant.cancel_at_period_end = False
        _apply_end_date(tenant, args.status, args.ends_at)

        if subscription_request:
            subscription_request.status = "resolved"
            subscription_request.resolved_at = datetime.now(timezone.utc)

        quota_updates = {
            field: getattr(args, field)
            for field in ("quota_users", "quota_storage_bytes", "quota_messages")
            if getattr(args, field) is not None
        }
        await AuditService.log_action(
            db,
            tenant_id=tenant.id,
            user_id=None,
            action="SUPPORT_SUBSCRIPTION_STATUS_CHANGED",
            resource_type="tenant",
            resource_id=tenant.id,
            details={
                "operator": args.operator,
                "from": previous_status,
                "to": args.status,
                "plan": tenant.subscription_plan,
                "quota_updates": quota_updates,
                "ends_at": args.ends_at.isoformat() if args.ends_at else None,
                "subscription_request_id": subscription_request.id if subscription_request else None,
                "reason": args.reason,
            },
        )
        await db.commit()
    resolution = f"; resolved request {args.request_id}" if args.request_id else ""
    print(f"Updated subscription status for tenant {args.tenant_id} to {args.status}{resolution}.")


async def list_pending_requests(args: argparse.Namespace) -> None:
    async with AsyncSessionLocal() as db:
        tenant = await db.scalar(select(Tenant).where(Tenant.id == args.tenant_id))
        if not tenant:
            raise SystemExit("Tenant not found")
        await _set_tenant_context(db, tenant.id)
        rows = (
            await db.scalars(
                select(SubscriptionRequest)
                .where(
                    SubscriptionRequest.tenant_id == tenant.id,
                    SubscriptionRequest.status.in_(PENDING_REQUEST_STATUSES),
                )
                .order_by(SubscriptionRequest.created_at.asc())
                .limit(200)
            )
        ).all()
    for request in rows:
        print(
            json.dumps(
                {
                    "id": request.id,
                    "tenant_id": request.tenant_id,
                    "request_type": request.request_type,
                    "status": request.status,
                    "created_at": request.created_at.isoformat(),
                },
                sort_keys=True,
            )
        )
    if not rows:
        print("No pending subscription requests.")


async def list_privacy_requests(args: argparse.Namespace) -> None:
    async with AsyncSessionLocal() as db:
        tenant = await db.scalar(select(Tenant).where(Tenant.id == args.tenant_id))
        if not tenant:
            raise SystemExit("Tenant not found")
        await _set_tenant_context(db, tenant.id)
        rows = (await db.scalars(select(PrivacyRequest).where(PrivacyRequest.tenant_id == tenant.id, PrivacyRequest.status.in_(PENDING_PRIVACY_STATUSES)).order_by(PrivacyRequest.created_at.asc()).limit(200))).all()
    for item in rows:
        print(json.dumps({"id": item.id, "request_type": item.request_type, "scope": item.scope, "status": item.status, "created_at": item.created_at.isoformat()}, sort_keys=True))
    if not rows:
        print("No pending privacy requests.")


async def resolve_privacy_request(args: argparse.Namespace) -> None:
    async with AsyncSessionLocal() as db:
        tenant = await db.scalar(select(Tenant).where(Tenant.id == args.tenant_id))
        if not tenant:
            raise SystemExit("Tenant not found")
        await _set_tenant_context(db, tenant.id)
        item = await db.scalar(select(PrivacyRequest).where(PrivacyRequest.id == args.request_id, PrivacyRequest.tenant_id == tenant.id, PrivacyRequest.status.in_(PENDING_PRIVACY_STATUSES)).with_for_update())
        if not item:
            raise SystemExit("Pending privacy request not found for this tenant")
        item.status = args.status
        item.resolution_note = args.resolution_note
        item.resolved_at = datetime.now(timezone.utc)
        await AuditService.log_action(db, tenant_id=tenant.id, user_id=None, action="SUPPORT_PRIVACY_REQUEST_RESOLVED", resource_type="privacy_request", resource_id=item.id, details={"operator": args.operator, "status": args.status, "resolution_note": args.resolution_note})
        await db.commit()
    print(f"Resolved privacy request {args.request_id} as {args.status}.")


async def approve_pilot_email(args: argparse.Namespace) -> None:
    """Record an operator-confirmed email for a private pilot without email delivery."""
    async with AsyncSessionLocal() as db:
        user = await db.scalar(
            select(User).where(func.lower(User.email) == args.user_email).with_for_update()
        )
        if not user:
            raise SystemExit("User not found; run this command with the migrate service")
        await _set_tenant_context(db, user.tenant_id)
        if user.email_verified_at is not None:
            print(f"Pilot email was already approved for user {user.id}.")
            return
        user.email_verified_at = datetime.now(timezone.utc)
        await AuditService.log_action(
            db,
            tenant_id=user.tenant_id,
            user_id=None,
            action="SUPPORT_PILOT_EMAIL_APPROVED",
            resource_type="user",
            resource_id=user.id,
            details={"operator": args.operator, "reason": args.reason},
        )
        await db.commit()
    print(f"Approved pilot email for user {user.id} in tenant {user.tenant_id}.")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audited LegalTech subscription support")
    commands = parser.add_subparsers(dest="command", required=True)

    status_command = commands.add_parser("set-subscription-status")
    status_command.add_argument("--tenant-id", required=True)
    status_command.add_argument("--status", choices=sorted(STATUSES), required=True)
    status_command.add_argument("--plan")
    status_command.add_argument("--quota-users", type=_positive_argument("--quota-users", MAX_QUOTA_USERS))
    status_command.add_argument("--quota-storage-bytes", type=_positive_argument("--quota-storage-bytes", MAX_QUOTA_STORAGE_BYTES))
    status_command.add_argument("--quota-messages", type=_positive_argument("--quota-messages", MAX_QUOTA_MESSAGES))
    status_command.add_argument("--ends-at", type=parse_aware_datetime)
    status_command.add_argument("--request-id")
    status_command.add_argument("--operator", required=True)
    status_command.add_argument("--reason", required=True)

    pending_command = commands.add_parser("list-pending-requests")
    pending_command.add_argument("--tenant-id", required=True)
    privacy_list = commands.add_parser("list-privacy-requests")
    privacy_list.add_argument("--tenant-id", required=True)
    privacy_resolve = commands.add_parser("resolve-privacy-request")
    privacy_resolve.add_argument("--tenant-id", required=True)
    privacy_resolve.add_argument("--request-id", required=True)
    privacy_resolve.add_argument("--status", choices=["completed", "rejected"], required=True)
    privacy_resolve.add_argument("--operator", required=True)
    privacy_resolve.add_argument("--resolution-note", required=True)
    pilot_email = commands.add_parser("approve-pilot-email")
    pilot_email.add_argument("--user-email", required=True)
    pilot_email.add_argument("--operator", required=True)
    pilot_email.add_argument("--reason", required=True)
    return parser.parse_args(argv)


def validate_args(args: argparse.Namespace) -> argparse.Namespace:
    if args.command != "approve-pilot-email":
        args.tenant_id = required_text(args.tenant_id, "--tenant-id", maximum=64)
    if args.command == "set-subscription-status":
        args.operator = required_text(args.operator, "--operator", maximum=200)
        args.reason = required_text(args.reason, "--reason", maximum=1_000)
        args.request_id = required_text(args.request_id, "--request-id", maximum=64) if args.request_id else None
        args.plan = required_text(args.plan, "--plan", maximum=100) if args.plan else None
    elif args.command == "resolve-privacy-request":
        args.request_id = required_text(args.request_id, "--request-id", maximum=64)
        args.operator = required_text(args.operator, "--operator", maximum=200)
        args.resolution_note = required_text(args.resolution_note, "--resolution-note", maximum=2_000)
    elif args.command == "approve-pilot-email":
        args.user_email = required_text(args.user_email, "--user-email", maximum=320).lower()
        if "@" not in args.user_email:
            raise SystemExit("--user-email must be an email address")
        args.operator = required_text(args.operator, "--operator", maximum=200)
        args.reason = required_text(args.reason, "--reason", maximum=1_000)
    return args


def main() -> None:
    args = validate_args(parse_args())
    if args.command == "set-subscription-status":
        asyncio.run(set_subscription_status(args))
    elif args.command == "list-pending-requests":
        asyncio.run(list_pending_requests(args))
    elif args.command == "list-privacy-requests":
        asyncio.run(list_privacy_requests(args))
    elif args.command == "resolve-privacy-request":
        asyncio.run(resolve_privacy_request(args))
    elif args.command == "approve-pilot-email":
        asyncio.run(approve_pilot_email(args))


if __name__ == "__main__":
    main()
