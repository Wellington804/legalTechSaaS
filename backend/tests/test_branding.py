import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from pydantic import ValidationError

from app.api.v1.endpoints.branding import brand_assets, can_edit, check_revision, download_asset, materialize_professional_text, settings_for_document, validate_professional_overrides
from app.models.branding import BrandProfile
from app.schemas.branding import BrandCreate, BrandSettings, BrandUpdate
from app.schemas.workspace import DocumentCreate


class BrandingTests(unittest.IsolatedAsyncioTestCase):
    def test_strict_tokens_and_plain_compatibility(self):
        for invalid in ({"font_family": "unlicensed.ttf"}, {"primary_color": "url(http://evil)"},
                        {"watermark_opacity": float("nan")}, {"text_color": "#FFFFFF"}, {"primary_color": "#CCCCCC"},
                        {"header_text": "bad\x00text"}, {"custom_css": "evil"}):
            with self.assertRaises(ValidationError):
                BrandSettings(**invalid)
        with self.assertRaises(ValidationError):
            BrandCreate(name="  ")
        with self.assertRaises(ValidationError):
            BrandUpdate(name="ok", settings={})
        self.assertEqual(BrandSettings(font_family="Noto Serif", heading_font_family="Lato").font_family, "Noto Serif")
        self.assertEqual(BrandSettings(paper_color="#ede7dd").paper_color, "#EDE7DD")
        with self.assertRaises(ValidationError):
            BrandSettings(paper_color="#202020", text_color="#202020")
        with self.assertRaises(ValidationError):
            BrandSettings(layout_mode="exact")
        self.assertEqual(BrandSettings(layout_mode="exact", background_asset_id="background").layout_mode, "exact")
        self.assertEqual(DocumentCreate(title="Texto existente").content_format, "plain")

    def test_only_owner_can_edit_personal_even_when_other_user_is_admin(self):
        personal = BrandProfile(id="profile", tenant_id="tenant", scope="personal", owner_user_id="owner", revision=2)
        self.assertTrue(can_edit(personal, SimpleNamespace(id="owner", role="lawyer")))
        self.assertFalse(can_edit(personal, SimpleNamespace(id="other", role="admin")))
        office = BrandProfile(scope="office")
        self.assertFalse(can_edit(office, SimpleNamespace(id="owner", role="lawyer")))
        self.assertTrue(can_edit(office, SimpleNamespace(id="other", role="partner")))
        with self.assertRaises(HTTPException) as stale:
            check_revision(personal, 1)
        self.assertEqual(stale.exception.status_code, 409)

    def test_professional_fields_and_document_variants_are_bounded(self):
        with self.assertRaises(ValidationError):
            BrandSettings(header_fields=["oab", "oab"])
        with self.assertRaises(ValidationError):
            BrandCreate(name="Identidade", variants={"petition": {"custom_css": "evil"}})
        base = BrandSettings(header_fields=["professional_name", "oab"], footer_fields=["office_name"]).model_dump()
        petition = settings_for_document(base, {"petition": {"margin_left_mm": 35, "header_fields": ["oab"]}}, "petition")
        self.assertEqual(petition["margin_left_mm"], 35)
        self.assertEqual(petition["header_fields"], ["oab"])
        rendered, missing = materialize_professional_text(petition, {"oab": "OAB/SP 123", "office_name": "Silva Advocacia"})
        self.assertEqual(rendered["header_text"], "OAB/SP 123")
        self.assertEqual(rendered["footer_text"], "Silva Advocacia")
        self.assertEqual(missing, [])
        with self.assertRaises(HTTPException) as invalid_office_override:
            validate_professional_overrides("office", {"professional_overrides": {"professional_name": "Nome fixo"}})
        self.assertEqual(invalid_office_override.exception.status_code, 422)

    def test_composed_contact_layer_binds_registered_data_and_rejects_unsafe_geometry(self):
        layer = {"id": "office-whatsapp", "kind": "icon_text", "role": "contact", "label": "WhatsApp",
                 "x_percent": 8, "y_percent": 90, "width_percent": 30, "height_percent": 4,
                 "binding": "office_phone", "icon": "whatsapp"}
        settings = BrandSettings(layout_mode="composed", layout_layers=[layer]).model_dump(mode="json")
        rendered, missing = materialize_professional_text(settings, {"office_phone": "(82) 99999-0000"})
        self.assertEqual(rendered["layout_layers"][0]["text"], "(82) 99999-0000")
        self.assertEqual(missing, [])
        with self.assertRaises(ValidationError):
            BrandSettings(layout_mode="composed", layout_layers=[{**layer, "x_percent": 90, "width_percent": 30}])
        with self.assertRaises(ValidationError):
            BrandSettings(layout_mode="composed", layout_layers=[{**layer, "binding": None}])

    async def test_assets_require_matching_tenant_profile_and_kind(self):
        db = SimpleNamespace(scalar=AsyncMock(return_value=None))
        user = SimpleNamespace(id="owner", tenant_id="tenant")
        profile = BrandProfile(id="profile", tenant_id="tenant")
        with self.assertRaises(HTTPException) as denied:
            await brand_assets(db, user, profile, {"logo_asset_id": "foreign"})
        self.assertEqual(denied.exception.status_code, 422)
        statement = str(db.scalar.call_args.args[0].compile(compile_kwargs={"literal_binds": True}))
        for clause in ("brand_assets.tenant_id = 'tenant'", "brand_assets.profile_id = 'profile'", "brand_assets.kind = 'logo'"):
            self.assertIn(clause, statement)
        db.scalar.reset_mock()
        with self.assertRaises(HTTPException) as denied_layer:
            await brand_assets(db, user, profile, {"layout_layers": [{"kind": "image", "asset_id": "foreign-layer"}]})
        self.assertEqual(denied_layer.exception.status_code, 422)
        layer_statement = str(db.scalar.call_args.args[0].compile(compile_kwargs={"literal_binds": True}))
        self.assertIn("brand_assets.profile_id = 'profile'", layer_statement)
        self.assertIn("brand_assets.kind != 'reference'", layer_statement)

    async def test_inline_external_asset_is_proxied_by_the_authenticated_api(self):
        asset = SimpleNamespace(id="asset", tenant_id="tenant", profile_id="profile", object_key="private/logo.png",
                                filename="logo.png", content_type="image/png")
        db = SimpleNamespace(scalar=AsyncMock(return_value=asset))
        user = SimpleNamespace(id="owner", tenant_id="tenant")
        with patch("app.api.v1.endpoints.branding.profile_for_editor", new=AsyncMock()), \
             patch("app.api.v1.endpoints.branding.asset_content", new=AsyncMock(return_value=b"private-png")), \
             patch("app.api.v1.endpoints.branding.create_download_url") as signed_url:
            response = await download_asset("asset", user, True, db)
        self.assertEqual(response.body, b"private-png")
        self.assertEqual(response.headers["content-disposition"], "inline; filename*=UTF-8''logo.png")
        signed_url.assert_not_called()


if __name__ == "__main__":
    unittest.main()
