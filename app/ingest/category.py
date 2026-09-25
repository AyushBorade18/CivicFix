import re


CIVIC_CATEGORY_KEYWORDS = {
    "pothole_road": [
        "pothole", "road concret", "road construction", "tar road", "asphalt",
        "resurfac", "cc road", "carpet road", "road widening", "road repair",
    ],
    "drainage_sewage": [
        "drainage", "sewage", "sewer", "storm water", "waterlogging", "nala", "gutter",
    ],
    "water_supply": [
        "water supply", "water tank", "borewell", "bore well", "pipeline",
        "drinking water", "water pump", "overhead tank",
    ],
    "streetlight": [
        "street light", "streetlight", "led light", "lighting", "lamp post",
        "high mast", "solar lamp", "lamp pol",
    ],
    "garbage_waste": [
        "garbage", "waste management", "solid waste", "dustbin", "sanitation", "compost",
    ],
    "footpath": [
        "footpath", "pavement", "walkway", "foot path",
        # paved public ground; closest of our 8 categories, and what citizens
        # complain about when the blocks break or sink
        "paving block", "paver block", "pathway",
    ],
    "traffic_signage": [
        "traffic signal", "signage", "zebra crossing", "speed breaker",
        "road safety", "traffic sign",
    ],
}


# MPLADS phrasings of road works ("Construction of internal road", "road ... to
# be concretized"). The construction word must be about the road itself, so
# "Construction of a wall at SB Road" is not a road work.
_ROAD_WORK_PATTERNS = [
    re.compile(r"\b(construct\w*|concreti[sz]\w*|repair\w*|widening)\s+(of\s+)?(an?\s+|the\s+)?"
               r"(concrete\s+|internal\s+|cc\s+|approach\s+)?(roads?|raod|lane|galli)\b", re.I),
    re.compile(r"\b(roads?|galli)\b[^.]{0,80}\bto\s+be\s+concreti[sz]ed\b", re.I),
    re.compile(r"\broad[- ]related\s+works?\b", re.I),
]
# A hall is the main work even when paving or washrooms come with it.
_HALL_PROJECT = re.compile(r"\bhall\b|sabhagruh", re.I)


def map_work_category(description: str) -> str:
    """Maps a free-text MPLADS work description onto our civic_category enum.

    workCategory in the source data ("Normal/Others", "Trust and Society", ...)
    is almost entirely uninformative for this purpose, so classification runs
    on workDescription keywords instead. Most MPLADS works fund things outside
    our 8 categories entirely (community halls, trusts, equipment) and
    correctly fall to 'other' rather than being forced into a wrong bucket.
    """
    text = (description or "").lower()
    if any(p.search(text) for p in _ROAD_WORK_PATTERNS):
        return "pothole_road"
    if _HALL_PROJECT.search(text):
        return "other"
    for category, keywords in CIVIC_CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return category
    return "other"
