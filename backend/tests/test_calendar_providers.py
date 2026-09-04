import json
import unittest
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

import httpx

from app.services.calendar_providers import CalendarClient, CalendarProviderError, _parse_event, authorization_url


class CalendarProviderTests(unittest.IsolatedAsyncioTestCase):
    def test_google_authorization_uses_offline_code_flow_state_and_pkce(self):
        values = {
            "GOOGLE_CALENDAR_CLIENT_ID": "client-id",
            "GOOGLE_CALENDAR_REDIRECT_URI": "https://lexflow.example/api/v1/integrations/calendar-oauth/google/callback",
        }
        with patch("app.services.calendar_providers._setting", side_effect=lambda name: values[name]):
            url = authorization_url("google", state="opaque-state", challenge="s256-challenge")
        query = parse_qs(urlsplit(url).query)
        self.assertEqual(query["response_type"], ["code"])
        self.assertEqual(query["access_type"], ["offline"])
        self.assertEqual(query["state"], ["opaque-state"])
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertNotIn("client_secret", query)

    async def test_google_incremental_pagination_preserves_sync_token(self):
        urls = []

        def handler(request: httpx.Request):
            urls.append(str(request.url))
            query = parse_qs(request.url.query.decode())
            if "pageToken" not in query:
                return httpx.Response(200, json={"items": [], "nextPageToken": "page-2"})
            self.assertEqual(query["syncToken"], ["cursor-1"])
            return httpx.Response(200, json={"items": [], "nextSyncToken": "cursor-2"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            page = await CalendarClient("google", "access", http=http).changes(
                "calendar@example.com",
                "connection-a",
                "https://www.googleapis.com/calendar/v3/calendars/calendar%40example.com/events?showDeleted=true&singleEvents=true&syncToken=cursor-1",
                datetime.now(timezone.utc) - timedelta(days=1),
                datetime.now(timezone.utc) + timedelta(days=1),
            )
        self.assertEqual(len(urls), 2)
        self.assertIn("syncToken=cursor-2", page.cursor)
        self.assertNotIn("privateExtendedProperty", page.cursor)

    async def test_provider_cursor_cannot_escape_fixed_host(self):
        with self.assertRaises(CalendarProviderError):
            await CalendarClient("microsoft", "access").changes(
                "calendar-a",
                "connection-a",
                "https://attacker.example/steal",
                datetime.now(timezone.utc) - timedelta(days=1),
                datetime.now(timezone.utc) + timedelta(days=1),
            )

    async def test_google_owned_scope_does_not_offer_shared_writer_calendar(self):
        async def handler(request: httpx.Request):
            return httpx.Response(
                200,
                json={
                    "items": [
                        {"id": "mine", "summary": "Minha agenda", "accessRole": "owner"},
                        {"id": "shared", "summary": "Compartilhada", "accessRole": "writer"},
                    ]
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            calendars = await CalendarClient("google", "access", http=http).calendars()
        self.assertTrue(calendars[0].can_write)
        self.assertFalse(calendars[1].can_write)

    async def test_google_create_lets_provider_issue_fresh_id_and_keeps_recovery_markers(self):
        captured = {}

        async def handler(request: httpx.Request):
            captured.update(json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "id": "provider-generated-event",
                    "etag": '"etag"',
                    "summary": "Prazo",
                    "start": {"dateTime": "2026-09-10T12:00:00Z"},
                },
            )

        body = {
            "title": "Prazo",
            "starts_at": datetime(2026, 9, 10, 12, tzinfo=timezone.utc),
            "location": "",
            "notes": "",
        }
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            remote = await CalendarClient("google", "access", http=http).create_event(
                "calendar-a", "task-a", body, "connection-a"
            )

        self.assertEqual(remote.identifier, "provider-generated-event")
        self.assertNotIn("id", captured)
        self.assertEqual(
            captured["extendedProperties"]["private"],
            {"lexflow_task_id": "task-a", "lexflow_connection_id": "connection-a"},
        )

    async def test_calendar_inventory_paginates_google_with_bounded_page_tokens(self):
        urls = []

        def handler(request: httpx.Request):
            urls.append(str(request.url))
            query = parse_qs(request.url.query.decode())
            if "pageToken" not in query:
                return httpx.Response(
                    200,
                    json={"items": [{"id": "first", "accessRole": "owner"}], "nextPageToken": "page-2"},
                )
            self.assertEqual(query["pageToken"], ["page-2"])
            return httpx.Response(200, json={"items": [{"id": "second", "accessRole": "owner"}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            calendars = await CalendarClient("google", "access", http=http).calendars()
        self.assertEqual([item.identifier for item in calendars], ["first", "second"])
        self.assertEqual(len(urls), 2)

    async def test_calendar_inventory_rejects_host_escape_and_item_overflow(self):
        requests = 0

        def hostile(request: httpx.Request):
            nonlocal requests
            requests += 1
            return httpx.Response(200, json={"value": [], "@odata.nextLink": "https://attacker.example/steal"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(hostile)) as http:
            with self.assertRaises(CalendarProviderError):
                await CalendarClient("microsoft", "access", http=http).calendars()
        self.assertEqual(requests, 1)

        def too_many(_request: httpx.Request):
            return httpx.Response(200, json={"items": [{"id": "a"}, {"id": "b"}]})

        with patch("app.services.calendar_providers.MAX_CALENDAR_ITEMS", 1):
            async with httpx.AsyncClient(transport=httpx.MockTransport(too_many)) as http:
                with self.assertRaises(CalendarProviderError):
                    await CalendarClient("google", "access", http=http).calendars()

    async def test_calendar_inventory_page_count_is_bounded(self):
        requests = 0

        def paginated(_request: httpx.Request):
            nonlocal requests
            requests += 1
            return httpx.Response(
                200,
                json={
                    "value": [],
                    "@odata.nextLink": f"https://graph.microsoft.com/v1.0/me/calendars?$skiptoken={requests}",
                },
            )

        with patch("app.services.calendar_providers.MAX_CALENDAR_PAGES", 1):
            async with httpx.AsyncClient(transport=httpx.MockTransport(paginated)) as http:
                with self.assertRaises(CalendarProviderError):
                    await CalendarClient("microsoft", "access", http=http).calendars()
        self.assertEqual(requests, 1)

    async def test_microsoft_calendar_without_can_edit_is_read_only(self):
        async def handler(_request: httpx.Request):
            return httpx.Response(200, json={"value": [{"id": "calendar-a", "name": "Agenda"}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            calendars = await CalendarClient("microsoft", "access", http=http).calendars()
        self.assertFalse(calendars[0].can_write)

    async def test_update_and_delete_require_provider_etag_before_network(self):
        def handler(_request: httpx.Request):
            raise AssertionError("request must not be issued without ETag")

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = CalendarClient("google", "access", http=http)
            body = {"title": "Prazo", "starts_at": datetime.now(timezone.utc), "location": "", "notes": ""}
            with self.assertRaises(CalendarProviderError) as update_error:
                await client.update_event("calendar-a", "event-a", None, "task-a", body, "connection-a")
            with self.assertRaises(CalendarProviderError) as delete_error:
                await client.delete_event("calendar-a", "event-a", None)
        self.assertTrue(update_error.exception.conflict)
        self.assertTrue(delete_error.exception.conflict)

    async def test_event_lookup_distinguishes_confirmed_404_and_divergent_identity(self):
        def missing(_request: httpx.Request):
            return httpx.Response(404, json={"error": "not found"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(missing)) as http:
            remote = await CalendarClient("google", "access", http=http).get_event("calendar-a", "event-a")
        self.assertTrue(remote.deleted)
        self.assertEqual(remote.identifier, "event-a")

        def divergent(_request: httpx.Request):
            return httpx.Response(200, json={"id": "event-b", "etag": '"etag"'})

        async with httpx.AsyncClient(transport=httpx.MockTransport(divergent)) as http:
            with self.assertRaises(CalendarProviderError):
                await CalendarClient("google", "access", http=http).get_event("calendar-a", "event-a")

    async def test_google_watch_requires_resource_identity(self):
        def handler(_request: httpx.Request):
            return httpx.Response(200, json={"id": "channel-a", "expiration": "1788541200000"})

        with patch("app.services.calendar_providers._setting", return_value="https://api.example.com/webhook"):
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
                with self.assertRaises(CalendarProviderError):
                    await CalendarClient("google", "access", http=http).create_watch("calendar-a", "connection-a")

    async def test_delta_pagination_is_bounded(self):
        def handler(_request: httpx.Request):
            return httpx.Response(200, json={"value": [], "@odata.nextLink": "https://graph.microsoft.com/v1.0/next"})

        with patch("app.services.calendar_providers.MAX_SYNC_PAGES", 1):
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
                with self.assertRaises(CalendarProviderError):
                    await CalendarClient("microsoft", "access", http=http).changes(
                        "calendar-a",
                        "connection-a",
                        None,
                        datetime.now(timezone.utc) - timedelta(days=1),
                    datetime.now(timezone.utc) + timedelta(days=1),
                )

    def test_microsoft_link_markers_are_accepted_only_as_the_exact_trailer(self):
        remote = _parse_event(
            "microsoft",
            {
                "id": "event-a",
                "@odata.etag": '"etag"',
                "subject": "Prazo",
                "start": {"dateTime": "2026-09-04T12:00:00Z"},
                "body": {
                    "content": "Texto com LexFlow-Task-ID: não-é-metadado\n\nLexFlow-Task-ID: task-a\nLexFlow-Connection-ID: connection-a"
                },
            },
        )
        self.assertEqual(remote.linked_task_id, "task-a")
        self.assertEqual(remote.linked_connection_id, "connection-a")
        self.assertIn("não-é-metadado", remote.notes)


if __name__ == "__main__":
    unittest.main()
