import unittest
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

import httpx

from app.services.calendar_providers import CalendarClient, CalendarProviderError, authorization_url


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


if __name__ == "__main__":
    unittest.main()
