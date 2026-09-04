"""Pinned Google Calendar and Microsoft Graph transports.

Provider cursors and identifiers are treated as credentials.  Callers persist
them encrypted and this module never logs bodies, tokens or URLs.
"""

import hashlib
import json
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

import httpx

from app.core.config import settings


GOOGLE_SCOPES = (
    "openid",
    "email",
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
    "https://www.googleapis.com/auth/calendar.events.owned",
)
MICROSOFT_SCOPES = ("openid", "email", "offline_access", "User.Read", "Calendars.ReadWrite")
MAX_SYNC_PAGES = 50
MAX_SYNC_EVENTS = 5000


class CalendarProviderError(RuntimeError):
    def __init__(self, message: str, *, reauthorization_required: bool = False, conflict: bool = False):
        super().__init__(message)
        self.reauthorization_required = reauthorization_required
        self.conflict = conflict


class CalendarCursorExpired(CalendarProviderError):
    pass


@dataclass(frozen=True)
class OAuthTokens:
    access_token: str
    refresh_token: str
    expires_at: datetime
    scopes: tuple[str, ...]


@dataclass(frozen=True)
class ProviderAccount:
    identifier: str
    label: str | None


@dataclass(frozen=True)
class ProviderCalendar:
    identifier: str
    name: str
    primary: bool
    can_write: bool


@dataclass(frozen=True)
class RemoteEvent:
    identifier: str
    etag: str | None
    deleted: bool
    title: str | None
    starts_at: datetime | None
    location: str | None
    notes: str | None
    linked_task_id: str | None = None
    linked_connection_id: str | None = None

    def canonical_hash(self) -> str:
        body = {
            "deleted": self.deleted,
            "title": self.title,
            "starts_at": self.starts_at.astimezone(timezone.utc).isoformat() if self.starts_at else None,
            "location": self.location,
            "notes": self.notes,
        }
        return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class RemoteChangePage:
    events: tuple[RemoteEvent, ...]
    cursor: str


@dataclass(frozen=True)
class WatchRegistration:
    reference: str
    resource: str | None
    token: str
    expires_at: datetime


def _setting(name: str) -> str:
    value = getattr(settings, name, "")
    if not isinstance(value, str) or not value.strip():
        raise CalendarProviderError("Integração de calendário ainda não configurada.")
    return value.strip()


def authorization_url(provider: Literal["google", "microsoft"], *, state: str, challenge: str) -> str:
    if provider == "google":
        query = urlencode(
            {
                "client_id": _setting("GOOGLE_CALENDAR_CLIENT_ID"),
                "redirect_uri": _setting("GOOGLE_CALENDAR_REDIRECT_URI"),
                "response_type": "code",
                "scope": " ".join(GOOGLE_SCOPES),
                "access_type": "offline",
                "include_granted_scopes": "true",
                "prompt": "consent",
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
        return f"https://accounts.google.com/o/oauth2/v2/auth?{query}"
    if provider == "microsoft":
        tenant = getattr(settings, "MICROSOFT_CALENDAR_TENANT", "common") or "common"
        query = urlencode(
            {
                "client_id": _setting("MICROSOFT_CALENDAR_CLIENT_ID"),
                "redirect_uri": _setting("MICROSOFT_CALENDAR_REDIRECT_URI"),
                "response_type": "code",
                "response_mode": "query",
                "scope": " ".join(MICROSOFT_SCOPES),
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
        return f"https://login.microsoftonline.com/{quote(tenant, safe='')}/oauth2/v2.0/authorize?{query}"
    raise ValueError("unsupported calendar provider")


async def exchange_code(
    provider: Literal["google", "microsoft"], code: str, verifier: str, *, client: httpx.AsyncClient | None = None
) -> OAuthTokens:
    owned = client is None
    http = client or httpx.AsyncClient(timeout=httpx.Timeout(20, connect=5), follow_redirects=False)
    try:
        if provider == "google":
            url = "https://oauth2.googleapis.com/token"
            data = {
                "client_id": _setting("GOOGLE_CALENDAR_CLIENT_ID"),
                "client_secret": _setting("GOOGLE_CALENDAR_CLIENT_SECRET"),
                "redirect_uri": _setting("GOOGLE_CALENDAR_REDIRECT_URI"),
                "grant_type": "authorization_code",
                "code": code,
                "code_verifier": verifier,
            }
            required = GOOGLE_SCOPES
        else:
            tenant = getattr(settings, "MICROSOFT_CALENDAR_TENANT", "common") or "common"
            url = f"https://login.microsoftonline.com/{quote(tenant, safe='')}/oauth2/v2.0/token"
            data = {
                "client_id": _setting("MICROSOFT_CALENDAR_CLIENT_ID"),
                "client_secret": _setting("MICROSOFT_CALENDAR_CLIENT_SECRET"),
                "redirect_uri": _setting("MICROSOFT_CALENDAR_REDIRECT_URI"),
                "grant_type": "authorization_code",
                "scope": " ".join(MICROSOFT_SCOPES),
                "code": code,
                "code_verifier": verifier,
            }
            required = MICROSOFT_SCOPES
        response = await http.post(url, data=data)
        payload = _json_response(response, "Não foi possível concluir a autorização.")
        access = payload.get("access_token")
        refresh = payload.get("refresh_token")
        expires = payload.get("expires_in")
        scope_value = payload.get("scope", "")
        scopes = tuple(str(scope_value).split())
        normalized = {item.casefold() for item in scopes}
        if not isinstance(access, str) or not access or not isinstance(refresh, str) or not refresh:
            raise CalendarProviderError("O provedor não retornou autorização renovável.")
        if not isinstance(expires, (int, float)) or expires <= 0:
            raise CalendarProviderError("O provedor retornou validade de token inválida.")
        if not {item.casefold() for item in required}.issubset(normalized):
            raise CalendarProviderError("As permissões mínimas de calendário não foram concedidas.")
        return OAuthTokens(access, refresh, datetime.now(timezone.utc) + timedelta(seconds=int(expires)), scopes)
    finally:
        if owned:
            await http.aclose()


async def refresh_tokens(
    provider: Literal["google", "microsoft"], refresh_token: str, *, client: httpx.AsyncClient | None = None
) -> OAuthTokens:
    owned = client is None
    http = client or httpx.AsyncClient(timeout=httpx.Timeout(20, connect=5), follow_redirects=False)
    try:
        if provider == "google":
            url = "https://oauth2.googleapis.com/token"
            required = GOOGLE_SCOPES
            data = {
                "client_id": _setting("GOOGLE_CALENDAR_CLIENT_ID"),
                "client_secret": _setting("GOOGLE_CALENDAR_CLIENT_SECRET"),
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            }
        else:
            tenant = getattr(settings, "MICROSOFT_CALENDAR_TENANT", "common") or "common"
            url = f"https://login.microsoftonline.com/{quote(tenant, safe='')}/oauth2/v2.0/token"
            required = MICROSOFT_SCOPES
            data = {
                "client_id": _setting("MICROSOFT_CALENDAR_CLIENT_ID"),
                "client_secret": _setting("MICROSOFT_CALENDAR_CLIENT_SECRET"),
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "scope": " ".join(MICROSOFT_SCOPES),
            }
        response = await http.post(url, data=data)
        if response.status_code in {400, 401}:
            raise CalendarProviderError("A autorização do calendário precisa ser renovada.", reauthorization_required=True)
        payload = _json_response(response, "Não foi possível renovar o calendário.")
        access = payload.get("access_token")
        replacement = payload.get("refresh_token") or refresh_token
        expires = payload.get("expires_in")
        scopes = tuple(str(payload.get("scope", " ".join(required))).split())
        if not isinstance(access, str) or not access or not isinstance(replacement, str) or not replacement:
            raise CalendarProviderError("Resposta de renovação inválida.")
        return OAuthTokens(access, replacement, datetime.now(timezone.utc) + timedelta(seconds=int(expires or 3600)), scopes)
    finally:
        if owned:
            await http.aclose()


async def revoke_google_token(token: str) -> None:
    async with httpx.AsyncClient(timeout=10, follow_redirects=False) as http:
        response = await http.post("https://oauth2.googleapis.com/revoke", data={"token": token})
    if response.status_code not in {200, 400}:
        raise CalendarProviderError("O Google não confirmou a revogação; os tokens locais foram removidos.")


def _json_response(response: httpx.Response, safe_message: str) -> dict[str, Any]:
    if 300 <= response.status_code < 400:
        raise CalendarProviderError("Redirecionamento inesperado do provedor.")
    try:
        body = response.json()
    except ValueError as exc:
        raise CalendarProviderError(safe_message) from exc
    if not 200 <= response.status_code < 300 or not isinstance(body, dict):
        raise CalendarProviderError(safe_message, reauthorization_required=response.status_code in {401, 403})
    return body


class CalendarClient:
    def __init__(self, provider: Literal["google", "microsoft"], access_token: str, *, http: httpx.AsyncClient | None = None):
        self.provider = provider
        self.headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
        self._http = http

    async def _request(
        self,
        method: str,
        url: str,
        *,
        json_body: dict | None = None,
        extra_headers: dict | None = None,
        allow_not_found: bool = False,
    ) -> dict | None:
        parsed = urlsplit(url)
        allowed = "www.googleapis.com" if self.provider == "google" else "graph.microsoft.com"
        if parsed.scheme != "https" or parsed.hostname != allowed or parsed.username or parsed.password or parsed.port not in {None, 443}:
            raise CalendarProviderError("Cursor de sincronização inválido.")
        owned = self._http is None
        http = self._http or httpx.AsyncClient(timeout=httpx.Timeout(20, connect=5), follow_redirects=False)
        try:
            headers = {**self.headers, **(extra_headers or {})}
            response = await http.request(method, url, headers=headers, json=json_body)
        finally:
            if owned:
                await http.aclose()
        if response.status_code == 410:
            raise CalendarCursorExpired("Cursor expirado.")
        if response.status_code in {401, 403}:
            raise CalendarProviderError("A autorização do calendário precisa ser renovada.", reauthorization_required=True)
        if response.status_code in {409, 412}:
            raise CalendarProviderError("O evento foi alterado no provedor.", conflict=True)
        if allow_not_found and response.status_code == 404:
            return None
        if method == "DELETE" and response.status_code == 404:
            return {}
        if response.status_code == 204:
            return {}
        return _json_response(response, "O provedor de calendário recusou a operação.")

    async def account(self) -> ProviderAccount:
        if self.provider == "google":
            payload = await self._request("GET", "https://www.googleapis.com/oauth2/v2/userinfo")
            identifier, label = payload.get("id"), payload.get("email")
        else:
            payload = await self._request("GET", "https://graph.microsoft.com/v1.0/me?$select=id,mail,userPrincipalName")
            identifier, label = payload.get("id"), payload.get("mail") or payload.get("userPrincipalName")
        if not isinstance(identifier, str) or not identifier:
            raise CalendarProviderError("O provedor não identificou a conta autorizada.")
        return ProviderAccount(identifier, label if isinstance(label, str) else None)

    async def calendars(self) -> tuple[ProviderCalendar, ...]:
        if self.provider == "google":
            payload = await self._request("GET", "https://www.googleapis.com/calendar/v3/users/me/calendarList")
            rows = payload.get("items", [])
            return tuple(
                # calendar.events.owned is intentionally narrower than the
                # all-calendars scope, so writer access to someone else's
                # calendar must not be presented as writable by LexFlow.
                ProviderCalendar(str(row["id"]), str(row.get("summary") or row["id"]), bool(row.get("primary")), row.get("accessRole") == "owner")
                for row in rows if isinstance(row, dict) and row.get("id")
            )
        payload = await self._request("GET", "https://graph.microsoft.com/v1.0/me/calendars?$select=id,name,canEdit,isDefaultCalendar")
        rows = payload.get("value", [])
        return tuple(
            ProviderCalendar(str(row["id"]), str(row.get("name") or row["id"]), bool(row.get("isDefaultCalendar")), bool(row.get("canEdit", False)))
            for row in rows if isinstance(row, dict) and row.get("id")
        )

    async def create_event(self, calendar_id: str, task_id: str, body: dict[str, Any], connection_id: str) -> RemoteEvent:
        if self.provider == "google":
            event_id = hashlib.sha256(f"{connection_id}:{task_id}".encode()).hexdigest()[:40]
            payload = await self._request(
                "POST", f"https://www.googleapis.com/calendar/v3/calendars/{quote(calendar_id, safe='')}/events",
                json_body={"id": event_id, **_google_body(body), "extendedProperties": {"private": {"lexflow_task_id": task_id, "lexflow_connection_id": connection_id}}},
            )
        else:
            payload = await self._request(
                "POST", f"https://graph.microsoft.com/v1.0/me/calendars/{quote(calendar_id, safe='')}/events",
                json_body={**_microsoft_body(body, task_id, connection_id), "transactionId": hashlib.sha256(f"{connection_id}:{task_id}".encode()).hexdigest()},
            )
        return _parse_event(self.provider, payload)

    async def get_event(self, calendar_id: str, event_id: str) -> RemoteEvent:
        url = (
            f"https://www.googleapis.com/calendar/v3/calendars/{quote(calendar_id, safe='')}/events/{quote(event_id, safe='')}"
            if self.provider == "google" else
            f"https://graph.microsoft.com/v1.0/me/calendars/{quote(calendar_id, safe='')}/events/{quote(event_id, safe='')}"
        )
        payload = await self._request("GET", url, allow_not_found=True)
        if payload is None:
            return RemoteEvent(event_id, None, True, None, None, None, None)
        if not isinstance(payload.get("id"), str) or not secrets.compare_digest(payload["id"], event_id):
            raise CalendarProviderError("O provedor retornou identidade de evento divergente.")
        return _parse_event(self.provider, payload)

    async def update_event(
        self,
        calendar_id: str,
        event_id: str,
        etag: str | None,
        task_id: str,
        body: dict[str, Any],
        connection_id: str,
    ) -> RemoteEvent:
        if not etag:
            raise CalendarProviderError("O provedor não informou a versão do evento.", conflict=True)
        url = (
            f"https://www.googleapis.com/calendar/v3/calendars/{quote(calendar_id, safe='')}/events/{quote(event_id, safe='')}"
            if self.provider == "google" else
            f"https://graph.microsoft.com/v1.0/me/calendars/{quote(calendar_id, safe='')}/events/{quote(event_id, safe='')}"
        )
        payload = await self._request(
            "PATCH", url, json_body=_google_body(body) if self.provider == "google" else _microsoft_body(body, task_id, connection_id),
            extra_headers={"If-Match": etag},
        )
        return _parse_event(self.provider, payload)

    async def delete_event(self, calendar_id: str, event_id: str, etag: str | None) -> None:
        if not etag:
            raise CalendarProviderError("O provedor não informou a versão do evento.", conflict=True)
        url = (
            f"https://www.googleapis.com/calendar/v3/calendars/{quote(calendar_id, safe='')}/events/{quote(event_id, safe='')}"
            if self.provider == "google" else
            f"https://graph.microsoft.com/v1.0/me/calendars/{quote(calendar_id, safe='')}/events/{quote(event_id, safe='')}"
        )
        await self._request("DELETE", url, extra_headers={"If-Match": etag})

    async def changes(self, calendar_id: str, connection_id: str, cursor: str | None, start: datetime, end: datetime) -> RemoteChangePage:
        events: list[RemoteEvent] = []
        if cursor:
            url = cursor
        elif self.provider == "google":
            # Google forbids privateExtendedProperty together with syncToken.
            # Read the selected calendar delta and let the tenant-scoped service
            # discard every event not present in its explicit link allowlist.
            query = urlencode({"showDeleted": "true", "singleEvents": "true", "timeMin": start.isoformat(), "timeMax": end.isoformat()})
            url = f"https://www.googleapis.com/calendar/v3/calendars/{quote(calendar_id, safe='')}/events?{query}"
        else:
            query = urlencode({"startDateTime": start.isoformat(), "endDateTime": end.isoformat()})
            url = f"https://graph.microsoft.com/v1.0/me/calendars/{quote(calendar_id, safe='')}/calendarView/delta?{query}"
        cursor_value: str | None = None
        pages = 0
        seen_urls: set[str] = set()
        while url:
            pages += 1
            if pages > MAX_SYNC_PAGES or url in seen_urls:
                raise CalendarProviderError("O provedor excedeu o limite de páginas da sincronização.")
            seen_urls.add(url)
            current_url = url
            payload = await self._request("GET", url)
            rows = payload.get("items", []) if self.provider == "google" else payload.get("value", [])
            if not isinstance(rows, list) or len(events) + len(rows) > MAX_SYNC_EVENTS:
                raise CalendarProviderError("O provedor excedeu o limite de eventos da sincronização.")
            events.extend(_parse_event(self.provider, row) for row in rows if isinstance(row, dict) and row.get("id"))
            url = payload.get("nextPageToken") if self.provider == "google" else payload.get("@odata.nextLink")
            if self.provider == "google" and url:
                parsed = urlsplit(current_url)
                query_items = [(key, value) for key, value in parse_qsl(parsed.query) if key != "pageToken"]
                query_items.append(("pageToken", str(url)))
                url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query_items), ""))
            if not url:
                cursor_value = payload.get("nextSyncToken") if self.provider == "google" else payload.get("@odata.deltaLink")
        if not isinstance(cursor_value, str) or not cursor_value:
            raise CalendarProviderError("O provedor não retornou cursor de sincronização.")
        if self.provider == "google":
            cursor_value = f"https://www.googleapis.com/calendar/v3/calendars/{quote(calendar_id, safe='')}/events?" + urlencode({"showDeleted": "true", "singleEvents": "true", "syncToken": cursor_value})
        return RemoteChangePage(tuple(events), cursor_value)

    async def create_watch(self, calendar_id: str, connection_id: str) -> WatchRegistration:
        reference = secrets.token_urlsafe(24)
        token = secrets.token_urlsafe(32)
        if self.provider == "google":
            expires = datetime.now(timezone.utc) + timedelta(days=6)
            payload = await self._request(
                "POST", f"https://www.googleapis.com/calendar/v3/calendars/{quote(calendar_id, safe='')}/events/watch",
                json_body={"id": reference, "type": "web_hook", "address": _setting("GOOGLE_CALENDAR_WEBHOOK_URL"), "token": token, "expiration": str(int(expires.timestamp() * 1000))},
            )
            resource = payload.get("resourceId")
            returned_expiration = payload.get("expiration")
            if returned_expiration:
                expires = datetime.fromtimestamp(int(returned_expiration) / 1000, tz=timezone.utc)
        else:
            expires = datetime.now(timezone.utc) + timedelta(days=6)
            payload = await self._request(
                "POST", "https://graph.microsoft.com/v1.0/subscriptions",
                json_body={"changeType": "created,updated,deleted", "notificationUrl": _setting("MICROSOFT_CALENDAR_WEBHOOK_URL"), "resource": f"me/calendars/{calendar_id}/events", "expirationDateTime": expires.isoformat(), "clientState": token},
            )
            reference = str(payload.get("id") or "")
            resource = payload.get("resource")
            returned_expiration = payload.get("expirationDateTime")
            if returned_expiration:
                expires = _parse_datetime(returned_expiration)
        if not reference:
            raise CalendarProviderError("O provedor não confirmou o webhook.")
        if self.provider == "google" and (not isinstance(resource, str) or not resource):
            raise CalendarProviderError("O Google não confirmou a identidade do recurso observado.")
        return WatchRegistration(reference, str(resource) if resource else None, token, expires)

    async def delete_watch(self, reference: str, resource: str | None) -> None:
        if self.provider == "google":
            await self._request("POST", "https://www.googleapis.com/calendar/v3/channels/stop", json_body={"id": reference, "resourceId": resource})
        else:
            await self._request("DELETE", f"https://graph.microsoft.com/v1.0/subscriptions/{quote(reference, safe='')}")


def _google_body(body: dict[str, Any]) -> dict[str, Any]:
    start = body["starts_at"]
    return {
        "summary": body["title"],
        "start": {"dateTime": start.isoformat()},
        "end": {"dateTime": (start + timedelta(hours=1)).isoformat()},
        "location": body.get("location") or "",
        "description": body.get("notes") or "",
    }


def _microsoft_body(body: dict[str, Any], task_id: str, connection_id: str) -> dict[str, Any]:
    start = body["starts_at"]
    note = body.get("notes") or ""
    return {
        "subject": body["title"],
        "start": {"dateTime": start.astimezone(timezone.utc).replace(tzinfo=None).isoformat(), "timeZone": "UTC"},
        "end": {"dateTime": (start + timedelta(hours=1)).astimezone(timezone.utc).replace(tzinfo=None).isoformat(), "timeZone": "UTC"},
        "location": {"displayName": body.get("location") or ""},
        "body": {
            "contentType": "text",
            "content": f"{note}\n\nLexFlow-Task-ID: {task_id}\nLexFlow-Connection-ID: {connection_id}".strip(),
        },
        "categories": ["LexFlow"],
    }


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_event(provider: str, row: dict[str, Any]) -> RemoteEvent:
    deleted = row.get("status") == "cancelled" if provider == "google" else "@removed" in row or bool(row.get("isCancelled"))
    if provider == "google":
        start = row.get("start", {}).get("dateTime") if isinstance(row.get("start"), dict) else None
        title, location, notes = row.get("summary"), row.get("location"), row.get("description")
        etag = row.get("etag")
        private = row.get("extendedProperties", {}).get("private") if isinstance(row.get("extendedProperties"), dict) else None
        linked_task_id = private.get("lexflow_task_id") if isinstance(private, dict) else None
        linked_connection_id = private.get("lexflow_connection_id") if isinstance(private, dict) else None
    else:
        start = row.get("start", {}).get("dateTime") if isinstance(row.get("start"), dict) else None
        title = row.get("subject")
        location = row.get("location", {}).get("displayName") if isinstance(row.get("location"), dict) else None
        notes = row.get("body", {}).get("content") if isinstance(row.get("body"), dict) else None
        linked_task_id = None
        linked_connection_id = None
        if isinstance(notes, str):
            marker = re.search(
                r"(?:^|\n\n)LexFlow-Task-ID:\s*([^\s]{1,64})\nLexFlow-Connection-ID:\s*([^\s]{1,64})\s*$",
                notes,
            )
            if marker:
                linked_task_id = marker.group(1)
                linked_connection_id = marker.group(2)
                notes = notes[: marker.start()].strip()
        etag = row.get("@odata.etag") or row.get("changeKey")
    return RemoteEvent(
        str(row["id"]),
        str(etag) if etag else None,
        deleted,
        title if isinstance(title, str) else None,
        _parse_datetime(start) if start and not deleted else None,
        location if isinstance(location, str) else None,
        notes if isinstance(notes, str) else None,
        linked_task_id if isinstance(linked_task_id, str) else None,
        linked_connection_id if isinstance(linked_connection_id, str) else None,
    )
