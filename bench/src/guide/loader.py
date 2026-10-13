"""The Hanjeok export as a corpus, in the shape that crosses the bench's seam.

A place becomes a document: its path is the id a citation names, its body is
the text that stands for it in a similarity search, and its relatedness links
keep the rank Hanjeok gave them.

`place_text` lives here because it is the one definition of "what text
represents a place". The guide's own graph embeds exactly this, so a place is
found by the same words whichever pipeline is looking.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from bench.corpus.loader import Link, LoadedDoc, LoadResult, check_unique_paths
from guide.export import Event, Export, Place, read_export

CORPUS = "hanjeok"


def place_path(place_id: int) -> str:
    return f"place/{place_id}"


def place_text(place: Place) -> str:
    """Name, where it is, what kind of place, then the description.

    Absent fields are left out rather than written as "None" — an embedding of
    the word "None" is closer to other empty places than to anything real.
    """
    category = " ".join(part for part in (place.category_mid, place.category_small) if part)
    head = " · ".join(part for part in (place.name, place.region_label, category) if part)
    body = place.overview or place.summary or ""
    return f"{head}\n{body}".strip()


def event_text(event: Event) -> str:
    where = f" · {event.place_text}" if event.place_text else ""
    return f"{event.name}{where}\n{event.start_date} – {event.end_date}"


class HanjeokLoader:
    name = CORPUS

    def __init__(self, export: Export | Path | str) -> None:
        self._export = export if isinstance(export, Export) else read_export(export)

    def load(self) -> LoadResult:
        export = self._export
        links: dict[int, list[Link]] = {}
        for link in export.related:
            links.setdefault(link.base_id, []).append(
                Link(
                    place_path(link.related_id),
                    "related",
                    rank=link.rank,
                    attrs={
                        "score": link.score,
                        "distance_km": link.distance_km,
                        "travel_minutes": link.travel_minutes,
                    },
                )
            )

        docs = [
            LoadedDoc(
                path=place_path(place.id),
                corpus=CORPUS,
                title=place.name,
                doc_type="place",
                body=place_text(place),
                typed_links=tuple(links.get(place.id, ())),
                attrs=asdict(place),
            )
            for place in export.places
        ]
        docs += [
            LoadedDoc(
                path=f"event/{event.id}",
                corpus=CORPUS,
                title=event.name,
                doc_type=event.kind,
                body=event_text(event),
                typed_links=(Link(place_path(event.place_id), "held_at"),)
                if event.place_id
                else (),
                attrs=asdict(event),
            )
            for event in export.events
        ]
        check_unique_paths(docs)
        # The manifest hash is this corpus's revision: two loads of the same
        # export are the same corpus, and nothing else is.
        return LoadResult(tuple(docs), (), revision=export.sha256)
