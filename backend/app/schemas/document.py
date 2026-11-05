from typing import Literal, Any
from pydantic import BaseModel, Field, ConfigDict

class Options(BaseModel):
    model_config = ConfigDict(extra='forbid')
    engine: Literal['AUTO', 'MARKER', 'DOCLING', 'LIGHTWEIGHT'] = 'AUTO'
    languages: list[str] = Field(default_factory=lambda: ['eng'], min_length=1, max_length=20)
    force_ocr: bool = False
    language: str = Field('und', pattern=r'^[a-zA-Z0-9-]{2,35}$')
    dpi: int = Field(200, ge=100, le=300)

class Block(BaseModel):
    blockId: str
    blockType: Literal['heading','paragraph','list','listItem','table','image','caption','blockquote','equation','code','pageBreak']
    sourcePage: int | None
    language: str = 'und'
    direction: Literal['ltr','rtl','auto'] = 'auto'
    content: str
    inlineFormatting: list[dict[str, Any]] = Field(default_factory=list)
    readingOrder: int
    provenance: dict[str, Any] = Field(default_factory=dict)

class Document(BaseModel):
    schemaVersion: int = 1
    documentId: str
    sourceFileName: str
    sourceChecksum: str
    title: str
    language: str = 'und'
    revision: int = 1
    pages: list[dict[str, Any]] = Field(default_factory=list)
    blocks: list[Block] = Field(default_factory=list)
    assets: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)

class RevisionInput(BaseModel):
    baseRevision: int = Field(ge=1)
    html: str = Field(max_length=10_000_000)

class Quote(BaseModel):
    exact: str = Field(min_length=1, max_length=200000)
    prefix: str = Field('', max_length=64)
    suffix: str = Field('', max_length=64)

class Position(BaseModel):
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    unit: Literal['unicode-codepoint'] = 'unicode-codepoint'

class Highlight(BaseModel):
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,80}$')
    documentId: str
    revision: int = Field(ge=1)
    blockIds: list[str] = Field(min_length=1)
    quote: Quote
    position: Position
    color: str = Field('#ffdf70', pattern=r'^#[0-9a-fA-F]{6}$')
    status: Literal['resolved','unresolved'] = 'resolved'

class HighlightPatch(BaseModel):
    color: str = Field(pattern=r'^#[0-9a-fA-F]{6}$')
