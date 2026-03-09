"""Configuration data for IELTS listening exercise generation.

120 micro-context topics, speaker roles, complications, detail focuses,
numerical ranges, and accent vocabulary hints — all used by the 3-step
generation pipeline in listening_generator.py.
"""

import random

# ─── 120 Micro-Context Topics ────────────────────────────────────────────────

TOPICS = {
    "daily_life": [
        "renting an apartment",
        "student dormitory inquiry",
        "moving company booking",
        "furniture delivery problem",
        "gym membership cancellation",
        "library membership registration",
        "lost ID card report",
        "booking a driving test",
        "scheduling a dentist appointment",
        "university health center visit",
        "reserving a tennis court",
        "swimming class registration",
        "volunteer program sign-up",
        "language exchange meetup",
        "museum guided tour booking",
        "concert ticket refund",
        "train delay complaint",
        "airport shuttle reservation",
        "hotel late check-in request",
        "car rental damage report",
        "parking permit application",
        "pet adoption inquiry",
        "dog training course",
        "photography workshop signup",
        "art class enrollment",
        "cooking class booking",
        "bicycle repair service",
        "community garden membership",
        "internet service installation",
        "phone plan upgrade",
        "insurance policy inquiry",
        "bank account opening",
        "scholarship application inquiry",
        "conference registration",
        "campus tour booking",
        "student housing complaint",
        "cafeteria meal plan question",
        "recycling program registration",
        "charity event volunteer coordination",
        "neighborhood meeting announcement",
    ],
    "academic": [
        "research project planning",
        "lab safety briefing",
        "biology field trip briefing",
        "geology field study",
        "archaeology excavation update",
        "psychology experiment instructions",
        "economics lecture summary",
        "climate change research talk",
        "marine biology lecture",
        "astronomy observation session",
        "computer science seminar",
        "statistics workshop",
        "environmental policy debate",
        "architecture design critique",
        "engineering prototype review",
        "robotics lab introduction",
        "anthropology lecture",
        "art history museum talk",
        "linguistics pronunciation research",
        "neuroscience experiment overview",
        "agriculture innovation lecture",
        "renewable energy seminar",
        "transportation planning lecture",
        "public health study briefing",
        "AI ethics discussion",
        "social media research study",
        "behavioral economics lecture",
        "urban development seminar",
        "wildlife conservation briefing",
        "supply chain logistics lecture",
        "medical research conference summary",
        "education reform lecture",
        "digital privacy seminar",
        "ocean pollution research",
        "genetic engineering lecture",
        "nanotechnology introduction",
        "space exploration research update",
        "pharmaceutical trial explanation",
        "sustainable farming lecture",
        "biodiversity research project",
    ],
    "workplace": [
        "job interview scheduling",
        "internship orientation",
        "workplace safety training",
        "office relocation announcement",
        "staff meeting update",
        "project deadline discussion",
        "customer complaint call",
        "IT support ticket",
        "marketing campaign briefing",
        "product launch planning",
        "logistics delivery issue",
        "restaurant staff training",
        "hotel staff briefing",
        "tour guide training",
        "airline crew schedule update",
        "construction safety meeting",
        "retail store inventory discussion",
        "warehouse shipping delay",
        "HR benefits explanation",
        "company training seminar",
    ],
    "public_info": [
        "city bus service update",
        "subway maintenance announcement",
        "park opening hours notice",
        "festival schedule announcement",
        "weather emergency notice",
        "library event calendar",
        "road construction warning",
        "recycling schedule change",
        "new museum exhibition introduction",
        "tourist attraction guide",
        "zoo animal talk",
        "historical site explanation",
        "public health campaign",
        "water conservation announcement",
        "wildlife protection announcement",
        "fire safety notice",
        "earthquake preparedness talk",
        "hiking trail safety advice",
        "boating safety briefing",
        "airport security announcement",
    ],
}

# Category → allowed IELTS section formats
CATEGORY_FORMAT_MAP = {
    "daily_life": ["conversation"],
    "academic": ["discussion", "lecture"],
    "workplace": ["conversation", "discussion"],
    "public_info": ["monologue", "lecture"],
}

# ─── Speaker Role Pairs ──────────────────────────────────────────────────────

SPEAKER_ROLES_DIALOGUE = [
    ("landlord", "tenant"),
    ("librarian", "student"),
    ("travel agent", "tourist"),
    ("professor", "student"),
    ("receptionist", "caller"),
    ("researcher", "assistant"),
    ("HR manager", "employee"),
    ("museum guide", "visitor"),
    ("volunteer coordinator", "applicant"),
    ("gym instructor", "member"),
    ("bank clerk", "customer"),
    ("IT technician", "staff member"),
    ("hotel manager", "guest"),
    ("course advisor", "student"),
    ("mechanic", "car owner"),
    ("veterinarian", "pet owner"),
    ("event organizer", "participant"),
    ("nurse", "patient"),
    ("real estate agent", "buyer"),
    ("chef", "trainee"),
]

SPEAKER_ROLES_MONOLOGUE = [
    "tour guide",
    "museum curator",
    "city council representative",
    "park ranger",
    "airport announcer",
    "radio presenter",
    "orientation coordinator",
    "safety officer",
    "community leader",
    "transport official",
]

SPEAKER_ROLES_LECTURE = [
    "Professor",
    "Dr.",
    "Lecturer",
    "Guest speaker",
    "Research fellow",
]

# ─── Complications / Twists ──────────────────────────────────────────────────

COMPLICATIONS = [
    "change of plan",
    "budget constraint",
    "time conflict",
    "missing information",
    "special requirement",
    "unexpected closure",
    "discount or promotion",
    "recommendation from a friend",
    "medical or dietary need",
    "transport difficulty",
    "last-minute cancellation",
    "double booking",
    "equipment malfunction",
    "policy change",
    "weather disruption",
]

# ─── Detail Focuses ──────────────────────────────────────────────────────────

DETAIL_FOCUSES = [
    "dates and times",
    "prices and payments",
    "names and addresses",
    "phone numbers and emails",
    "room or seat numbers",
    "dietary preferences",
    "transport schedules",
    "equipment and materials",
    "membership tiers",
    "event schedules and deadlines",
]

# ─── Numerical Ranges ────────────────────────────────────────────────────────

NUMERICAL_RANGES = {
    "rent": (650, 3200),
    "deposit": (200, 1800),
    "utility": (40, 280),
    "course_fee": (50, 900),
    "membership_fee": (10, 120),
    "event_ticket": (8, 150),
    "train_ticket": (12, 220),
    "meal_price": (6, 45),
    "research_sample_size": (30, 5000),
    "distance_km": (2, 850),
    "time_minutes": (5, 240),
    "temperature_c": (-5, 40),
    "room_number": (101, 950),
    "phone_extension": (200, 999),
    "capacity": (15, 500),
}

# Topic keywords → relevant number categories
TOPIC_NUMBER_MAP = {
    "rent": ["rent", "deposit", "utility"],
    "apartment": ["rent", "deposit", "utility"],
    "dormitory": ["rent", "deposit"],
    "hotel": ["room_number", "meal_price"],
    "gym": ["membership_fee"],
    "membership": ["membership_fee"],
    "course": ["course_fee", "capacity"],
    "class": ["course_fee", "capacity", "room_number"],
    "ticket": ["event_ticket", "train_ticket"],
    "concert": ["event_ticket"],
    "train": ["train_ticket", "time_minutes"],
    "shuttle": ["train_ticket", "time_minutes"],
    "booking": ["room_number"],
    "research": ["research_sample_size"],
    "lecture": ["room_number", "capacity"],
    "seminar": ["room_number", "capacity", "course_fee"],
    "safety": ["phone_extension", "capacity"],
    "temperature": ["temperature_c"],
    "climate": ["temperature_c", "research_sample_size"],
    "field": ["distance_km", "research_sample_size"],
    "hiking": ["distance_km", "temperature_c"],
    "bus": ["train_ticket", "time_minutes"],
    "delivery": ["time_minutes"],
    "restaurant": ["meal_price", "capacity"],
    "cafeteria": ["meal_price"],
    "insurance": ["membership_fee"],
    "bank": ["deposit"],
    "phone": ["phone_extension", "membership_fee"],
    "parking": ["membership_fee"],
    "pet": ["course_fee"],
    "zoo": ["event_ticket", "capacity"],
}

# ─── Accent Configuration ────────────────────────────────────────────────────

ACCENTS = ["british", "australian", "american"]

ACCENT_VOCAB = {
    "british": (
        "Use British English vocabulary: 'flat' (not 'apartment'), 'queue' (not 'line'), "
        "'holiday' (not 'vacation'), 'post' (not 'mail'), 'lift' (not 'elevator'), "
        "'lorry' (not 'truck'), 'rubbish' (not 'garbage'), 'underground' (not 'subway')."
    ),
    "australian": (
        "Use Australian English vocabulary: 'uni' (not 'university'), casual tone, "
        "'arvo' (afternoon), 'reckon' (think), 'heaps' (a lot), 'no worries' (you're welcome)."
    ),
    "american": (
        "Use American English vocabulary: 'apartment' (not 'flat'), 'vacation' (not 'holiday'), "
        "'line' (not 'queue'), 'elevator' (not 'lift'), 'sidewalk' (not 'pavement'), "
        "'truck' (not 'lorry'), 'subway' (not 'underground')."
    ),
}

# Accent → TTS voice mapping
ACCENT_VOICE_PAIRS = {
    "british": ("british_female", "british_male"),
    "australian": ("australian_female", "australian_male"),
    "american": ("american_female", "american_male"),
}

ACCENT_SOLO_VOICES = {
    "british": ["british_female", "british_male"],
    "australian": ["australian_female", "australian_male"],
    "american": ["american_female", "american_male"],
}


# ─── Metadata Generator ─────────────────────────────────────────────────────

def generate_metadata(avoid_topics: list[str] | None = None, format_hint: str = "") -> dict:
    """Generate exercise metadata via pure Python randomization (no GPT call).

    Returns a dict with: topic, category, format, speaker_roles, accent,
    complication, detail_focus, numbers, word_count_range.
    """
    avoid_set = set(t.lower() for t in (avoid_topics or []))

    # Pick category and topic, filtering out recently used
    all_topics = []
    for cat, topics in TOPICS.items():
        for t in topics:
            if t.lower() not in avoid_set:
                all_topics.append((cat, t))

    if not all_topics:
        # Fallback: ignore avoidance if everything is used
        all_topics = [(cat, t) for cat, topics in TOPICS.items() for t in topics]

    category, topic = random.choice(all_topics)

    # Pick format — respect format_hint if given, else pick from category's allowed formats
    allowed_formats = CATEGORY_FORMAT_MAP.get(category, ["conversation"])
    if format_hint and format_hint in ("conversation", "monologue", "discussion", "lecture"):
        fmt = format_hint
    else:
        fmt = random.choice(allowed_formats)

    # Speaker roles
    if fmt in ("conversation", "discussion"):
        roles = random.choice(SPEAKER_ROLES_DIALOGUE)
    elif fmt == "monologue":
        roles = (random.choice(SPEAKER_ROLES_MONOLOGUE),)
    else:  # lecture
        title = random.choice(SPEAKER_ROLES_LECTURE)
        roles = (f"{title} {_random_surname()}",)

    # Accent
    accent = random.choice(ACCENTS)

    # Complication + detail focus
    complication = random.choice(COMPLICATIONS)
    detail_focus = random.choice(DETAIL_FOCUSES)

    # Pre-generate numbers relevant to topic
    numbers = _pick_numbers(topic)

    # Word count range by format
    if fmt in ("conversation", "discussion"):
        word_count = "600–800 words"
    else:
        word_count = "700–900 words"

    return {
        "topic": topic,
        "category": category,
        "format": fmt,
        "speaker_roles": roles,
        "accent": accent,
        "accent_hints": ACCENT_VOCAB[accent],
        "complication": complication,
        "detail_focus": detail_focus,
        "numbers": numbers,
        "word_count": word_count,
    }


def _pick_numbers(topic: str) -> dict[str, int]:
    """Pick 3-5 random numbers relevant to the topic from NUMERICAL_RANGES."""
    topic_lower = topic.lower()
    relevant_keys = set()
    for keyword, num_keys in TOPIC_NUMBER_MAP.items():
        if keyword in topic_lower:
            relevant_keys.update(num_keys)

    # Always include a few defaults if nothing matched
    if not relevant_keys:
        relevant_keys = {"course_fee", "room_number", "time_minutes"}

    # Pick 3-5 from relevant
    keys = list(relevant_keys)
    if len(keys) > 5:
        keys = random.sample(keys, 5)

    result = {}
    for k in keys:
        lo, hi = NUMERICAL_RANGES[k]
        # Avoid round numbers: if value is divisible by 50 or 100, nudge it
        val = random.randint(lo, hi)
        if val % 100 == 0 and val > lo:
            val += random.choice([-17, 13, 23, -27, 37, 43])
        elif val % 50 == 0 and val > lo:
            val += random.choice([-7, 3, 13, -3, 17])
        val = max(lo, min(hi, val))
        result[k] = val

    return result


_SURNAMES = [
    "Chen", "Wilson", "Patel", "Santos", "Kim", "Anderson", "Singh",
    "Brown", "Garcia", "Nguyen", "Miller", "Taylor", "Thomas",
    "Jackson", "White", "Harris", "Martin", "Thompson", "Moore",
    "Clark", "Lewis", "Robinson", "Walker", "Hall", "Young",
]


def _random_surname() -> str:
    return random.choice(_SURNAMES)
