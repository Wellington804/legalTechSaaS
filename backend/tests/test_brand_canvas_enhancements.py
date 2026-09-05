import io
import unittest
from PIL import Image

from app.schemas.branding import BrandPreview, BrandSuggestion
from app.services.brand_ai import extract_reference_palette


class TestBrandCanvasEnhancements(unittest.TestCase):
    def test_brand_suggestion_accepts_valid_text_or_audio(self):
        # 1. Valid text only
        suggestion_text = BrandSuggestion(
            expected_revision=1,
            brief="Criar identidade moderna para direito empresarial com tons azuis.",
        )
        self.assertIn("empresarial", suggestion_text.brief)

        # 2. Audio provided with empty text
        audio_dummy = "UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=" * 10
        suggestion_audio = BrandSuggestion(
            expected_revision=1,
            brief="",
            audio_base64=audio_dummy,
            audio_mime="audio/webm",
        )
        self.assertTrue(bool(suggestion_audio.audio_base64))
        self.assertIn("áudio gravado", suggestion_audio.brief)

        # 3. Reject if neither valid text nor audio provided
        with self.assertRaises(ValueError):
            BrandSuggestion(expected_revision=1, brief="")

    def test_brand_preview_supports_docx_and_pdf(self):
        preview_pdf = BrandPreview(expected_revision=1, format="pdf")
        self.assertEqual(preview_pdf.format, "pdf")

        preview_docx = BrandPreview(expected_revision=1, format="docx")
        self.assertEqual(preview_docx.format, "docx")

    def test_extract_reference_palette_extracts_clean_hex_colors(self):
        img = Image.new("RGB", (100, 100), (15, 23, 42))  # #0F172A (Navy)
        for x in range(30, 70):
            for y in range(30, 70):
                img.putpixel((x, y), (217, 119, 6))  # #D97706 (Amber/Gold)
        buf = io.BytesIO()
        img.save(buf, format="PNG")

        palette = extract_reference_palette(buf.getvalue())
        self.assertIsInstance(palette, list)
        self.assertTrue(any("#D97706" in c or "#0F172A" in c for c in palette))


if __name__ == "__main__":
    unittest.main()
