import unittest

from app.services.omnichannel import (
    MAX_INBOUND_BODY,
    extract_whatsapp_message,
    match_status,
    resend_recipient_token,
    resend_sender,
)


class OmnichannelInputTests(unittest.TestCase):
    def test_resend_identity_is_strictly_scoped_to_configured_domain(self):
        token = "A_secure-token_1234567890"
        recipients = [f"LexFlow <inbox+{token}@mail.lexflow.com.br>"]
        self.assertEqual(resend_recipient_token(recipients, "mail.lexflow.com.br"), token)
        self.assertIsNone(resend_recipient_token(recipients, "other.example.com"))
        self.assertIsNone(resend_recipient_token(["inbox+short@mail.lexflow.com.br"], "mail.lexflow.com.br"))

    def test_resend_sender_returns_only_a_normalized_email(self):
        self.assertEqual(resend_sender("Cliente <CLIENTE@EXAMPLE.COM>"), "cliente@example.com")
        self.assertIsNone(resend_sender("sem-endereco"))

    def test_auto_link_requires_exactly_one_client_and_case(self):
        self.assertEqual(match_status(1, 1), "linked")
        self.assertEqual(match_status(2, 1), "ambiguous")
        self.assertEqual(match_status(1, 2), "ambiguous")
        self.assertEqual(match_status(0, 0), "unmatched")

    def test_whatsapp_accepts_only_direct_inbound_messages(self):
        payload = {
            "event": "Message",
            "data": {
                "key": {"fromMe": False, "remoteJid": "5511999999999@s.whatsapp.net", "id": "msg-1"},
                "message": {"conversation": "Preciso falar sobre meu processo"},
            },
        }
        message = extract_whatsapp_message(payload)
        self.assertIsNotNone(message)
        self.assertEqual(message.sender, "+5511999999999")
        self.assertEqual(message.body, "Preciso falar sobre meu processo")

        payload["data"]["key"]["fromMe"] = True
        self.assertIsNone(extract_whatsapp_message(payload))
        payload["data"]["key"] = {"fromMe": False, "remoteJid": "5511999999999@g.us", "id": "msg-2"}
        self.assertIsNone(extract_whatsapp_message(payload))

    def test_whatsapp_marks_media_and_bounds_provider_input(self):
        payload = {
            "event": "Message",
            "data": {
                "key": {"fromMe": False, "remoteJid": "5511999999999@s.whatsapp.net", "id": "msg-3"},
                "message": {"documentMessage": {"caption": "x" * (MAX_INBOUND_BODY + 1)}},
            },
        }
        message = extract_whatsapp_message(payload)
        self.assertTrue(message.has_attachments)
        self.assertTrue(message.body_truncated)
        self.assertEqual(len(message.body), MAX_INBOUND_BODY)

    def test_whatsapp_accepts_current_evolution_go_payload(self):
        payload = {
            "event": "Message",
            "data": {
                "Info": {
                    "Sender": "5511999999999:7@s.whatsapp.net",
                    "SenderAlt": "123234343434@lid",
                    "IsFromMe": False,
                    "IsGroup": False,
                    "ID": "msg-current",
                },
                "Message": {"conversation": "Formato atual"},
            },
        }
        message = extract_whatsapp_message(payload)
        self.assertIsNotNone(message)
        self.assertEqual(message.sender, "+5511999999999")
        self.assertEqual(message.body, "Formato atual")

        payload["data"]["Info"]["IsGroup"] = True
        self.assertIsNone(extract_whatsapp_message(payload))


if __name__ == "__main__":
    unittest.main()
