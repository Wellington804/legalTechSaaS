"""Validated document-design tokens. No arbitrary CSS, paths or remote assets."""
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Font = Literal[
    "Liberation Serif", "Liberation Sans", "Liberation Mono",
    "DejaVu Serif", "DejaVu Sans", "DejaVu Sans Mono",
    "Noto Serif", "Noto Sans", "Noto Mono",
    "Carlito", "Caladea", "Lato", "Tinos",
]
FONT_FAMILIES = get_args(Font)
Alignment = Literal["left", "center", "right"]
AssetKind = Literal["reference", "logo", "logo_dark", "logo_mono", "watermark", "background"]
DocumentType = Literal["general", "petition", "contract", "power_of_attorney", "notice", "correspondence"]
ProfessionalField = Literal[
    "professional_name", "oab", "professional_email", "professional_phone", "professional_address",
    "office_name", "office_email", "office_phone", "office_address", "website",
]
LayerKind = Literal["rectangle", "line", "image", "text", "icon_text"]
LayerRole = Literal["decoration", "logo", "watermark", "heading", "contact"]
LayerIcon = Literal["none", "whatsapp", "phone", "email", "location", "website"]
LayerPageScope = Literal["first", "all", "continuation"]
ReferenceIntent = Literal["reproduce", "modernize", "inspire"]
EditorElement = Literal["identity", "cover", "header", "body", "footer", "logo", "watermark", "paper", "layers"]


class BrandInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class BrandCrop(BrandInput):
    x_percent: float = Field(ge=0, le=100)
    y_percent: float = Field(ge=0, le=100)
    width_percent: float = Field(gt=0, le=100)
    height_percent: float = Field(gt=0, le=100)

    @model_validator(mode="after")
    def inside_page(self):
        if self.x_percent + self.width_percent > 100 or self.y_percent + self.height_percent > 100:
            raise ValueError("O recorte da camada precisa ficar dentro da página.")
        return self


class BrandLayer(BrandInput):
    """One safe, editable primitive on the fixed document-branding plane."""

    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    kind: LayerKind
    role: LayerRole = "decoration"
    label: str = Field(min_length=1, max_length=80)
    x_percent: float = Field(ge=0, le=100)
    y_percent: float = Field(ge=0, le=100)
    width_percent: float = Field(gt=0, le=100)
    height_percent: float = Field(gt=0, le=100)
    rotation_deg: float = Field(default=0, ge=-180, le=180)
    opacity: float = Field(default=1, ge=0, le=1)
    visible: bool = True
    locked: bool = False
    image_contrast: float = Field(default=1, ge=0.5, le=3)
    z_index: int = Field(default=0, ge=0, le=100)
    page_scope: LayerPageScope = "all"
    color: str = Field(default="#17324D", pattern=r"^#[0-9A-Fa-f]{6}$")
    asset_id: str | None = Field(default=None, max_length=64)
    text: str = Field(default="", max_length=500)
    binding: ProfessionalField | None = None
    icon: LayerIcon = "none"
    font_family: Font = "Liberation Sans"
    font_size_pt: float = Field(default=8, ge=5, le=40)
    font_weight: Literal["normal", "bold"] = "normal"
    alignment: Alignment = "left"
    letter_spacing_pt: float = Field(default=0, ge=0, le=5)
    uppercase: bool = False
    line_thickness_pt: float = Field(default=1, ge=0.25, le=12)

    @field_validator("color")
    @classmethod
    def normalize_layer_color(cls, value: str) -> str:
        return value.upper()

    @field_validator("label", "text")
    @classmethod
    def safe_layer_text(cls, value: str) -> str:
        return BrandSettings.safe_text(value) if "BrandSettings" in globals() else value.strip()

    @model_validator(mode="after")
    def valid_geometry_and_content(self):
        if self.x_percent + self.width_percent > 100 or self.y_percent + self.height_percent > 100:
            raise ValueError("A camada precisa ficar dentro da página.")
        if self.kind == "image" and not self.asset_id:
            raise ValueError("Camada de imagem requer uma imagem do perfil.")
        if self.kind == "icon_text" and not self.binding:
            raise ValueError("Camada de contato requer um dado profissional cadastrado.")
        if self.binding and self.kind not in {"text", "icon_text"}:
            raise ValueError("Somente camadas de texto podem usar dados profissionais.")
        return self


class BrandLayerSuggestion(BrandInput):
    """AI-only layer; source crops are converted to private profile assets before returning."""

    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    kind: LayerKind
    role: LayerRole = "decoration"
    label: str = Field(min_length=1, max_length=80)
    x_percent: float = Field(ge=0, le=100)
    y_percent: float = Field(ge=0, le=100)
    width_percent: float = Field(gt=0, le=100)
    height_percent: float = Field(gt=0, le=100)
    rotation_deg: float = Field(default=0, ge=-180, le=180)
    opacity: float = Field(default=1, ge=0, le=1)
    visible: bool = True
    locked: bool = False
    image_contrast: float = Field(default=1, ge=0.5, le=3)
    z_index: int = Field(default=0, ge=0, le=100)
    page_scope: LayerPageScope = "all"
    color: str = Field(default="#17324D", pattern=r"^#[0-9A-Fa-f]{6}$")
    text: str = Field(default="", max_length=500)
    binding: ProfessionalField | None = None
    icon: LayerIcon = "none"
    font_family: Font = "Liberation Sans"
    font_size_pt: float = Field(default=8, ge=5, le=40)
    font_weight: Literal["normal", "bold"] = "normal"
    alignment: Alignment = "left"
    letter_spacing_pt: float = Field(default=0, ge=0, le=5)
    uppercase: bool = False
    line_thickness_pt: float = Field(default=1, ge=0.25, le=12)
    source_reference_index: int | None = Field(default=None, ge=1, le=3)
    source_crop: BrandCrop | None = None

    @model_validator(mode="after")
    def valid_suggestion(self):
        if self.x_percent + self.width_percent > 100 or self.y_percent + self.height_percent > 100:
            raise ValueError("A camada sugerida precisa ficar dentro da página.")
        if self.kind == "image" and (self.source_reference_index is None or self.source_crop is None):
            raise ValueError("Imagem sugerida requer referência e recorte.")
        if self.kind == "icon_text" and not self.binding:
            raise ValueError("Contato sugerido requer um dado profissional.")
        if self.binding and self.kind not in {"text", "icon_text"}:
            raise ValueError("Somente texto sugerido pode usar dados profissionais.")
        return self


class BrandSettings(BrandInput):
    font_family: Font = "Liberation Serif"
    heading_font_family: Font = "Liberation Sans"
    utility_font_family: Font = "Liberation Sans"
    body_size_pt: float = Field(default=12, ge=9, le=16)
    heading_size_pt: float = Field(default=16, ge=12, le=28)
    line_spacing: float = Field(default=1.5, ge=1, le=2)
    primary_color: str = Field(default="#17324D", pattern=r"^#[0-9A-Fa-f]{6}$")
    accent_color: str = Field(default="#8B6F47", pattern=r"^#[0-9A-Fa-f]{6}$")
    text_color: str = Field(default="#202020", pattern=r"^#[0-9A-Fa-f]{6}$")
    paper_color: str = Field(default="#FFFFFF", pattern=r"^#[0-9A-Fa-f]{6}$")
    heading_letter_spacing_pt: float = Field(default=0, ge=0, le=3)
    heading_uppercase: bool = False
    paper_size: Literal["A4", "LETTER"] = "A4"
    layout_mode: Literal["structured", "reconstructed", "composed", "exact"] = "structured"
    background_asset_id: str | None = Field(default=None, max_length=64)
    background_scope: Literal["first", "all"] = "all"
    show_document_title: bool = True
    margin_top_mm: float = Field(default=30, ge=20, le=80)
    margin_bottom_mm: float = Field(default=25, ge=20, le=80)
    margin_left_mm: float = Field(default=30, ge=15, le=50)
    margin_right_mm: float = Field(default=20, ge=15, le=50)
    header_text: str = Field(default="", max_length=500)
    footer_text: str = Field(default="", max_length=500)
    header_alignment: Alignment = "left"
    footer_alignment: Alignment = "center"
    header_divider: bool = True
    footer_divider: bool = True
    header_font_size_pt: float = Field(default=9, ge=6, le=18)
    footer_font_size_pt: float = Field(default=9, ge=6, le=18)
    header_letter_spacing_pt: float = Field(default=0, ge=0, le=5)
    footer_letter_spacing_pt: float = Field(default=0, ge=0, le=5)
    header_uppercase: bool = False
    footer_uppercase: bool = False
    header_top_mm: float = Field(default=10, ge=0, le=60)
    footer_bottom_mm: float = Field(default=8, ge=0, le=60)
    header_divider_thickness_pt: float = Field(default=0.75, ge=0.25, le=3)
    footer_divider_thickness_pt: float = Field(default=0.75, ge=0.25, le=3)
    header_divider_width_percent: float = Field(default=100, ge=20, le=100)
    footer_divider_width_percent: float = Field(default=100, ge=20, le=100)
    different_first_page: bool = False
    first_header_text: str = Field(default="", max_length=500)
    page_numbers: bool = True
    logo_asset_id: str | None = Field(default=None, max_length=64)
    logo_dark_asset_id: str | None = Field(default=None, max_length=64)
    logo_mono_asset_id: str | None = Field(default=None, max_length=64)
    logo_width_mm: float = Field(default=30, ge=10, le=60)
    logo_top_mm: float = Field(default=8, ge=0, le=60)
    watermark_asset_id: str | None = Field(default=None, max_length=64)
    watermark_text: str = Field(default="", max_length=80)
    watermark_opacity: float = Field(default=0.12, ge=0.03, le=0.3)
    watermark_position: Literal["center", "diagonal"] = "diagonal"
    watermark_rotation_deg: float = Field(default=35, ge=-90, le=90)
    watermark_width_mm: float = Field(default=100, ge=30, le=150)
    watermark_x_percent: float = Field(default=50, ge=0, le=100)
    watermark_y_percent: float = Field(default=50, ge=0, le=100)
    watermark_font_size_pt: float = Field(default=100, ge=24, le=180)
    header_fields: list[ProfessionalField] = Field(default_factory=list, max_length=10)
    footer_fields: list[ProfessionalField] = Field(default_factory=list, max_length=10)
    professional_overrides: dict[ProfessionalField, str] = Field(default_factory=dict, max_length=10)
    layout_layers: list[BrandLayer] = Field(default_factory=list, max_length=24)

    @field_validator("primary_color", "text_color", "paper_color")
    @classmethod
    def normalize_color(cls, value: str) -> str:
        return value.upper()

    @field_validator("accent_color")
    @classmethod
    def normalize_accent(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def readable_on_paper(self):
        def luminance(value: str) -> float:
            channels = [int(value[i:i + 2], 16) / 255 for i in (1, 3, 5)]
            linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
            return sum(c * weight for c, weight in zip(linear, (0.2126, 0.7152, 0.0722)))

        paper = luminance(self.paper_color)
        for color in (self.primary_color, self.text_color):
            foreground = luminance(color)
            contrast = (max(paper, foreground) + 0.05) / (min(paper, foreground) + 0.05)
            if contrast < 4.5:
                raise ValueError("Texto e cabeçalhos precisam de contraste mínimo de 4,5:1 com a cor do papel.")
        if self.layout_mode == "exact" and not self.background_asset_id:
            raise ValueError("O modo fiel exige uma página de referência aplicada como fundo.")
        if self.layout_mode == "composed" and not self.layout_layers:
            raise ValueError("A composição editável exige ao menos uma camada visual.")
        if len({layer.id for layer in self.layout_layers}) != len(self.layout_layers):
            raise ValueError("Cada camada visual precisa ter um identificador único.")
        return self

    @field_validator("header_text", "footer_text", "first_header_text", "watermark_text")
    @classmethod
    def safe_text(cls, value: str) -> str:
        if any(ord(char) < 32 and char not in "\n\t" for char in value) or any(0xD800 <= ord(char) <= 0xDFFF for char in value):
            raise ValueError("Texto contém caracteres de controle inválidos.")
        return value.strip()

    @field_validator("header_fields", "footer_fields")
    @classmethod
    def unique_fields(cls, value: list[ProfessionalField]) -> list[ProfessionalField]:
        if len(value) != len(set(value)):
            raise ValueError("Cada dado profissional pode aparecer somente uma vez por área.")
        return value

    @field_validator("professional_overrides")
    @classmethod
    def safe_overrides(cls, value: dict[ProfessionalField, str]) -> dict[ProfessionalField, str]:
        result = {}
        for key, text in value.items():
            if len(text) > 500:
                raise ValueError("Ajuste profissional deve ter no máximo 500 caracteres.")
            result[key] = cls.safe_text(text)
        return result


class BrandVariantSettings(BrandInput):
    margin_top_mm: float | None = Field(default=None, ge=20, le=80)
    margin_bottom_mm: float | None = Field(default=None, ge=20, le=80)
    margin_left_mm: float | None = Field(default=None, ge=15, le=50)
    margin_right_mm: float | None = Field(default=None, ge=15, le=50)
    header_text: str | None = Field(default=None, max_length=500)
    footer_text: str | None = Field(default=None, max_length=500)
    header_alignment: Alignment | None = None
    footer_alignment: Alignment | None = None
    header_divider: bool | None = None
    footer_divider: bool | None = None
    background_scope: Literal["first", "all"] | None = None
    show_document_title: bool | None = None
    different_first_page: bool | None = None
    first_header_text: str | None = Field(default=None, max_length=500)
    page_numbers: bool | None = None
    logo_width_mm: float | None = Field(default=None, ge=10, le=60)
    watermark_opacity: float | None = Field(default=None, ge=0.03, le=0.3)
    watermark_position: Literal["center", "diagonal"] | None = None
    watermark_rotation_deg: float | None = Field(default=None, ge=-90, le=90)
    watermark_width_mm: float | None = Field(default=None, ge=30, le=150)
    header_fields: list[ProfessionalField] | None = Field(default=None, max_length=10)
    footer_fields: list[ProfessionalField] | None = Field(default=None, max_length=10)

    @field_validator("header_text", "footer_text", "first_header_text")
    @classmethod
    def safe_optional_text(cls, value: str | None) -> str | None:
        return BrandSettings.safe_text(value) if value is not None else None

    @field_validator("header_fields", "footer_fields")
    @classmethod
    def unique_optional_fields(cls, value: list[ProfessionalField] | None) -> list[ProfessionalField] | None:
        return BrandSettings.unique_fields(value) if value is not None else None


BrandVariants = dict[DocumentType, BrandVariantSettings]


class BrandCreate(BrandInput):
    name: str = Field(min_length=2, max_length=100)
    scope: Literal["personal", "office"] = "personal"
    settings: BrandSettings = Field(default_factory=BrandSettings)
    variants: BrandVariants = Field(default_factory=dict, max_length=6)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        if len(value.strip()) < 2 or any(ord(c) < 32 for c in value):
            raise ValueError("Informe um nome válido.")
        return value.strip()


class BrandRevision(BrandInput):
    expected_revision: int = Field(ge=1)


class BrandUpdate(BrandRevision):
    name: str = Field(min_length=2, max_length=100)
    settings: BrandSettings
    variants: BrandVariants = Field(default_factory=dict, max_length=6)

    _clean_name = field_validator("name")(BrandCreate.clean_name.__func__)


class BrandSuggestion(BrandRevision):
    brief: str = Field(min_length=10, max_length=4000)
    reference_ids: list[str] = Field(default_factory=list, max_length=3)
    reference_pages: dict[str, int] = Field(default_factory=dict, max_length=3)
    consent: bool = False
    generate_logo: bool = False
    reference_intent: ReferenceIntent = "inspire"
    document_type: DocumentType = "general"
    selected_element: EditorElement = "identity"
    selected_layer_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,64}$")

    @field_validator("reference_pages")
    @classmethod
    def valid_reference_pages(cls, value: dict[str, int]) -> dict[str, int]:
        if any(not key or len(key) > 64 or not 1 <= page <= 200 for key, page in value.items()):
            raise ValueError("Página de referência inválida.")
        return value


class BrandAssetExtract(BrandRevision):
    kind: Literal["logo", "watermark", "background"]
    page: int = Field(default=1, ge=1, le=200)
    x_percent: float = Field(default=0, ge=0, le=100)
    y_percent: float = Field(default=0, ge=0, le=100)
    width_percent: float = Field(default=100, gt=0, le=100)
    height_percent: float = Field(default=100, gt=0, le=100)

    @model_validator(mode="after")
    def crop_inside_page(self):
        if self.x_percent + self.width_percent > 100 or self.y_percent + self.height_percent > 100:
            raise ValueError("A área escolhida precisa ficar dentro da página.")
        if self.kind == "background" and (self.x_percent, self.y_percent, self.width_percent, self.height_percent) != (0, 0, 100, 100):
            raise ValueError("O fundo fiel deve usar a página inteira.")
        return self


class BrandPreview(BrandRevision):
    document_type: DocumentType = "general"


class BrandDuplicate(BrandRevision):
    name: str | None = Field(default=None, min_length=2, max_length=100)

    @field_validator("name")
    @classmethod
    def clean_optional_name(cls, value: str | None) -> str | None:
        return BrandCreate.clean_name(value) if value is not None else None


class BrandExportInput(BrandInput):
    expected_version: int = Field(ge=1)
    profile_id: str | None = Field(default=None, max_length=64)
    document_type: DocumentType | None = None
