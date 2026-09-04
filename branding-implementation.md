# Central de Identidade Documental — implementação

Escopo aprovado: proposta anexada em 28/08/2026. Reutilizar Next/FastAPI/PostgreSQL, sessões, permissões, quotas e documentos existentes. Não inclui PWA/push nem os blocos do piloto.

## Contratos e execução

1. Backend principal: schema/migration `20260828_0006_branding`, profiles, immutable published versions, private assets and immutable exports. Tenant RLS + case ACL + owner/office editing policy. Existing document content adds `content_format` (`plain` default, `markdown` opt-in) to document and history.
2. Rendering/import specialist: `services/brand_documents.py`; native DOCX, controlled LibreOffice PDF conversion, sanitized image/DOCX/PDF reference analysis, bounded parsing/rendering, tests. Own requirements and Docker dependency installation. No arbitrary uploaded file is executed or rendered by LibreOffice; only server-generated DOCX.
3. Frontend specialist: Branding page and document export/read flows, office/personal settings, publication/version history, references, AI proposals and actual PDF preview. Mobile-safe existing controls. No localStorage persistence.
4. AI specialist: bounded Gemini structured design suggestions and optional generated logo via server key. Explicit consent, tenant enablement and quotas enforced by endpoint; model output validated. Never publishes automatically.
5. Main integration: migrations, real PostgreSQL tenant/case tests, document generation tests, frontend build and browser checks; rebuild local services only, no VPS deployment or real provider sends.

## Stable service/API contract

Prefix `/branding`, current authenticated session and privileged MFA. `{items: []}` lists.

- GET `/capabilities`: `{fonts: ["Liberation Serif", "Liberation Sans", "Liberation Mono", "DejaVu Serif", "DejaVu Sans", "DejaVu Sans Mono", "Noto Serif", "Noto Sans", "Noto Mono", "Carlito", "Caladea", "Lato"], pdf_available, ai_available, image_ai_available}`.
- GET/POST `/profiles`: POST `{name, scope: "personal"|"office", settings}`; returns profile `{id,name,scope,owner_user_id,revision,settings,published_version,can_edit}`. Office edit admin/partner; personal edit owner, others can only use published brand for responsible case lawyer.
- PUT `/profiles/{id}` `{name,settings,expected_revision}`. Published identity immutable; update only draft.
- GET `/profiles/{id}/versions`: immutable `{id,version,settings,created_at}`.
- POST `/profiles/{id}/publish` `{expected_revision}` -> profile.
- POST `/profiles/{id}/assets` multipart file + `kind` (`reference`,`logo`,`logo_dark`,`logo_mono`,`watermark`); returns `{id,filename,kind,analysis}`. GET same path lists metadata. GET `/assets/{id}/download` private original/sanitized resource.
- POST `/profiles/{id}/suggest` `{brief,reference_ids:[],consent:true,generate_logo:false,expected_revision}` -> `{settings,observations,warnings,logo_asset_id?}`; proposal not automatically saved/published.
- POST `/profiles/{id}/preview` `{expected_revision}` -> PDF bytes from current draft, marked illustrative. Same rendering engine as export.
- GET `/documents/{id}/exports` -> `{items:[{id,document_version,brand_version,created_at,sha256_pdf,sha256_docx}]}`.
- POST `/documents/{id}/exports` `{expected_version,profile_id?: string|null}` -> metadata. If omitted/null use published responsible-lawyer profile then office; error if none. Explicit profile must be office or responsible lawyer; templates without case use current lawyer/office. Evidence files and binaries without authored content cannot be rebranded.
- GET `/exports/{id}/download?format=pdf|docx` -> immutable artifact, always current case ACL checked.

`settings` fields (strict validated, unknown rejected): `font_family`, `heading_font_family`, `body_size_pt`, `heading_size_pt`, `line_spacing`, `primary_color`, `text_color`, `paper_size` (`A4`|`LETTER`), `margin_top_mm`, `margin_bottom_mm`, `margin_left_mm`, `margin_right_mm`, `header_text`, `footer_text`, `header_alignment`, `footer_alignment` (`left`|`center`|`right`), `different_first_page` boolean, `first_header_text`, `page_numbers` boolean, `logo_asset_id` nullable, `logo_dark_asset_id` nullable, `logo_mono_asset_id` nullable, `logo_width_mm`, `watermark_asset_id` nullable, `watermark_text`, `watermark_opacity`, `watermark_position` (`center`|`diagonal`), `watermark_width_mm`. IDs must belong to same profile. Brand data user-confirmed; never invented by AI.

Renderer functions: `render_documents(title: str, content: str, settings: dict, assets: dict[str, bytes], content_format: str = "plain") -> tuple[bytes, bytes]` (DOCX, PDF); `pdf_available() -> bool`; `validate_reference(filename: str, content: bytes, kind: str) -> tuple[str, bytes, dict]` -> safe MIME, normalized bytes, `{identified:{},estimated:{},warnings:[]}`. Image references PNG/JPEG only; SVG/macros/active external relationships rejected. First-page/header/watermark image/text behavior must be testable.

AI service: `async suggest_brand(settings: dict, brief: str, references: list[dict], generate_logo: bool=False) -> dict` with strict settings proposal, observations and warnings, optional `logo_bytes`. References contain `{content_type,content,analysis}`. Config uses existing GEMINI_API_KEY/GEMINI_MODEL + optional GEMINI_IMAGE_MODEL (blank by default); no live calls in tests.

## Gates / limits

- No secrets in browser or version control; no claims of provider homologation without credentials.
- Preview/export maximum bounded content and render duration; no arbitrary HTML/CSS/JS from model.
- Uploaded originals never overwrite source documents. Export revision/hash remains unchanged after brand updates.
- Quotas include brand assets and export bytes as well as existing documents.
- Data remains inside current tenant; publication approval required before export; draft previews do not publish.
- Candidate font identification from image/PDF is estimated, not guaranteed. Only installed licensed fonts accepted for export.
- Final report separates verified local implementation from VPS/provider/physical-device checks.

Status: implementation integrated and verified locally.

## Resultado verificado

- Backend final Docker: 94 testes aprovados sem skips, incluindo banco descartável com RLS real, HTTP autenticado, isolamento, versões, quota e PDF/DOCX reais.
- Frontend final Docker: build e TypeScript aprovados; 8 testes Node; Branding e workspace no navegador aprovados, com contratos de API interceptados e telas 320/375/1440px.
- Serviços locais reconstruídos e ativos em localhost:3000/8000; health/ready OK e migration 20260828_0006 aplicada após backup fora do repositório.
- Configuração Gemini pronta, desabilitada por padrão; nenhuma chamada real ao provedor nem implantação na VPS.
- Operação, limites e ressalva de divergências legadas em `alembic check`: `docs/central-branding.md`.
