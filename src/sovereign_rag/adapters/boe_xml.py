"""Parser for BOE disposition XML (https://www.boe.es/diario_boe/xml.php?id=...)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date

from sovereign_rag.domain.models import Document

URL = "https://www.boe.es/diario_boe/xml.php?id={id}"


def _clean(text: str) -> str:
    return text.replace("\u00a0", " ").strip()


def _text(root: ET.Element, path: str) -> str:
    el = root.find(path)
    return _clean("".join(el.itertext())) if el is not None else ""


def parse_boe(payload: bytes) -> Document:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ValueError(f"invalid XML: {exc}") from exc
    doc_id = _text(root, "metadatos/identificador")
    title = _text(root, "metadatos/titulo")
    if not doc_id or not title:
        raise ValueError("missing identificador or titulo")
    raw_date = _text(root, "metadatos/fecha_publicacion")
    try:
        published = date(int(raw_date[:4]), int(raw_date[4:6]), int(raw_date[6:8]))
    except ValueError:
        published = None
    paragraphs = tuple(t for p in root.findall("texto/p") if (t := _clean("".join(p.itertext()))))
    notes = tuple(t for n in root.findall("analisis/notas/nota") if (t := _clean(n.text or "")))
    return Document(
        id=doc_id,
        title=title,
        department=_text(root, "metadatos/departamento"),
        published=published,
        url=URL.format(id=doc_id),
        paragraphs=notes + paragraphs,
    )
