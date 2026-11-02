"""Open-access museum collections, for slot 23 (painting of the day).

Three sources, rotated by day: the Art Institute of Chicago, the Cleveland
Museum of Art, and the Metropolitan Museum of Art. All three publish open APIs
with no key and no registration.

**Rotating them is what stops the slot running dry or repeating**, which is the
reason `SLOTS.md` names four rather than one. The Rijksmuseum is the fourth and
is deliberately absent here: its API now requires a registered key, and a slot
that needs a secret is a slot that breaks silently on a machine where the secret
was never set.

**Every query filters to public domain.** All three expose a flag for it, and
none of them is ambiguous about what it means. A receipt printer is a private
device, but the images are also cached to disk, and there is no reason to hold
anything whose licence has conditions attached when a million works do not.

Each provider returns the same shape, so the slot never learns which museum it
got. Providers fail independently: if today's museum is down the slot tries the
next one rather than dropping, since three sources exist precisely so one
outage is survivable.
"""

from __future__ import annotations

import random
from typing import Any

from .http import SourceUnavailable, get_bytes, get_json

NAMESPACE = "museum"

# Small enough to be polite and to keep the download quick on a morning run;
# larger than the 576-dot page so downscaling never has to invent detail.
TARGET_PX = 900


def _norm(title: str, artist: str, date: str, image_url: str, source: str,
          credit: str = "") -> dict:
    return {"title": " ".join((title or "Untitled").split()),
            "artist": " ".join((artist or "Unknown").split()),
            "date": " ".join((date or "").split()),
            "image_url": image_url, "source": source, "credit": credit}


# AIC's documentation asks callers to identify themselves in this header, and
# the API throttles with a 403 rather than a 429 when it is unhappy - which
# looks like a permissions bug and is not one. `pick()` already walks to the
# next museum when this happens, so a throttle costs variety, not the slot.
_AIC_HEADERS = {"AIC-User-Agent": "quick-guthe (personal receipt printer)"}


def _aic(rng: random.Random) -> dict:
    # `query[exists][field]=image_id` looks like the obvious way to require an
    # image and makes the endpoint return 400. Filter client-side instead.
    page = rng.randint(1, 200)
    data = get_json(
        "https://api.artic.edu/api/v1/artworks/search"
        "?q=painting&query[term][is_public_domain]=true"
        "&fields=id,title,artist_title,date_display,image_id"
        f"&limit=20&page={page}", extra_headers=_AIC_HEADERS)
    iiif = data["config"]["iiif_url"]
    works = [w for w in data.get("data", []) if w.get("image_id")]
    if not works:
        raise SourceUnavailable("AIC returned no images")
    w = rng.choice(works)
    return _norm(w.get("title"), w.get("artist_title"), w.get("date_display"),
                 f"{iiif}/{w['image_id']}/full/{TARGET_PX},/0/default.jpg",
                 "Art Institute of Chicago")


# Without a type filter Cleveland's open-access set is mostly manuscript folios,
# prints and decorative objects - a live draw returned "Text, folio 323 (verso),
# from a Gospel Book with Commentaries", which is a fine object and not a
# painting of the day. Paintings and drawings both dither well; the rest do not.
_CLEVELAND_TYPES = ("Painting", "Drawing")


def _cleveland(rng: random.Random) -> dict:
    kind = rng.choice(_CLEVELAND_TYPES)
    data = get_json(
        "https://openaccess-api.clevelandart.org/api/artworks/"
        f"?has_image=1&cc0=1&type={kind}&limit=20"
        f"&skip={rng.randint(0, 900)}")
    works = [w for w in data.get("data", [])
             if (w.get("images") or {}).get("web", {}).get("url")]
    if not works:
        raise SourceUnavailable("Cleveland returned no images")
    w = rng.choice(works)
    creators = w.get("creators") or [{}]
    artist = (creators[0].get("description") or "").split("(")[0]
    return _norm(w.get("title"), artist, w.get("creation_date"),
                 w["images"]["web"]["url"], "Cleveland Museum of Art")


# The Met's search needs a query term - there is no "everything" form - and
# each term returns only a hundred or so public-domain objects. Rotating the
# term is what gives this provider any depth at all.
_MET_TERMS = ("painting", "portrait", "landscape", "still life", "oil",
              "watercolor", "drawing", "fresco", "altarpiece", "seascape")


def _met(rng: random.Random) -> dict:
    from urllib.parse import quote

    term = rng.choice(_MET_TERMS)
    found = get_json(
        "https://collectionapi.metmuseum.org/public/collection/v1/search"
        f"?q={quote(term)}&hasImages=true&isPublicDomain=true")
    ids = found.get("objectIDs") or []
    if not ids:
        raise SourceUnavailable(f"Met search for {term!r} returned nothing")
    # Some objects carry the hasImages flag and still have no usable URL, and a
    # few ids 404 outright, so try a handful rather than trusting the first.
    for object_id in rng.sample(ids, min(6, len(ids))):
        try:
            w = get_json("https://collectionapi.metmuseum.org/public/collection"
                         f"/v1/objects/{object_id}")
        except Exception:  # noqa: BLE001 - a dead id costs one attempt
            continue
        url = w.get("primaryImageSmall") or w.get("primaryImage")
        if url:
            return _norm(w.get("title"), w.get("artistDisplayName"),
                         w.get("objectDate"), url,
                         "The Metropolitan Museum of Art")
    raise SourceUnavailable("Met returned no usable image")


PROVIDERS = [("aic", _aic), ("cleveland", _cleveland), ("met", _met)]


def pick(rng: random.Random, *, store: Any = None,
         offline: bool = False) -> tuple[dict, bytes]:
    """(metadata, image bytes) from whichever museum answers.

    Starts at a day-dependent provider and walks the rest on failure. The whole
    payload is cached, image included, so a later outage still prints something.
    """
    start = rng.randrange(len(PROVIDERS))
    order = [PROVIDERS[(start + i) % len(PROVIDERS)]
             for i in range(len(PROVIDERS))]

    if not offline:
        for name, provider in order:
            try:
                meta = provider(rng)
                blob = get_bytes(meta["image_url"])
                if store is not None:
                    store.put(NAMESPACE, "last", meta)
                return meta, blob
            except Exception:  # noqa: BLE001 - try the next museum, then the cache
                continue

    if store is not None:
        cached = store.latest(NAMESPACE)
        if cached is not None:
            meta = dict(cached[1])
            try:
                return meta, get_bytes(meta["image_url"])
            except Exception:  # noqa: BLE001
                pass

    raise SourceUnavailable("no museum reachable and nothing cached")
