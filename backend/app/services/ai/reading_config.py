"""Configuration data for IELTS Academic Reading exercise generation.

120 topics across 12 categories, 10 diversity dimensions, paragraph blueprints,
question compositions, synonym distance weights, and numerical ranges —
all used by the generation pipeline in practice_generator.py.
"""

import random

# ─── 120 Topics (12 categories × 10) ────────────────────────────────────────

TOPICS = {
    "environment_ecology": [
        "coral reef conservation",
        "wetland restoration",
        "urban green spaces",
        "desertification in dry regions",
        "forest regeneration after wildfires",
        "biodiversity loss in island ecosystems",
        "plastic pollution in oceans",
        "soil erosion and land management",
        "rewilding projects in rural landscapes",
        "migratory bird habitat protection",
    ],
    "climate_energy": [
        "household solar energy adoption",
        "offshore wind farm development",
        "battery storage for renewable power",
        "water scarcity and conservation systems",
        "geothermal energy in urban areas",
        "hydrogen as an alternative fuel",
        "public attitudes toward nuclear energy",
        "energy-efficient building materials",
        "recycling systems in large cities",
        "sustainable management of freshwater reservoirs",
    ],
    "biology_life": [
        "pollination and bee population decline",
        "plant communication and chemical signaling",
        "animal migration patterns",
        "microbiomes in the human body",
        "sleep and memory formation",
        "genetic adaptation in extreme environments",
        "the biology of aging",
        "marine food chains and predator balance",
        "seed dispersal in tropical forests",
        "disease resistance in crops",
    ],
    "health_medicine": [
        "the impact of exercise on mental health",
        "vaccination campaigns and public trust",
        "sleep deprivation in modern society",
        "urban design and physical activity",
        "antibiotic resistance",
        "nutrition education in schools",
        "the rise of telemedicine",
        "early detection of chronic disease",
        "stress in high-pressure workplaces",
        "aging populations and healthcare systems",
    ],
    "psychology_behaviour": [
        "decision fatigue in daily life",
        "habit formation and behavior change",
        "memory accuracy and false memories",
        "motivation in long-term learning",
        "group decision-making",
        "attention span in digital environments",
        "emotional contagion in social groups",
        "risk perception and personal judgment",
        "the psychology of procrastination",
        "how rewards influence behavior",
    ],
    "education_learning": [
        "bilingual education in primary schools",
        "the effectiveness of online learning",
        "project-based learning in science classes",
        "the role of homework in achievement",
        "early childhood literacy development",
        "adult education and career change",
        "testing methods and student performance",
        "arts education and creativity",
        "classroom design and concentration",
        "peer learning and collaborative study",
    ],
    "technology_innovation": [
        "robotics in warehouse operations",
        "artificial intelligence in healthcare",
        "wearable technology and health tracking",
        "3D printing in manufacturing",
        "smart home systems and energy use",
        "digital privacy and personal data",
        "autonomous public transport",
        "drone use in agriculture",
        "translation technology and communication",
        "human interaction with service robots",
    ],
    "society_work": [
        "remote work and productivity",
        "the gig economy and job flexibility",
        "demographic aging and labor markets",
        "urban housing affordability",
        "tourism and local economies",
        "small business survival in changing markets",
        "women in leadership roles",
        "workplace design and employee wellbeing",
        "consumer behavior in online shopping",
        "skills shortages in modern industries",
    ],
    "history_heritage": [
        "the development of ancient road networks",
        "archaeological methods for studying settlements",
        "preservation of historical buildings",
        "the spread of early agriculture",
        "ancient water management systems",
        "the history of writing materials",
        "maritime trade in ancient societies",
        "museum collections and cultural memory",
        "lost cities and modern discovery methods",
        "heritage tourism and site protection",
    ],
    "language_culture": [
        "language change over time",
        "endangered languages and preservation",
        "storytelling traditions in oral cultures",
        "gestures and non-verbal communication",
        "the influence of media on vocabulary",
        "multilingualism in global cities",
        "translation challenges across cultures",
        "naming systems in different societies",
        "communication styles in teamwork",
        "the spread of global English",
    ],
    "cities_transport": [
        "bicycle-friendly city planning",
        "high-speed rail development",
        "airport design and passenger flow",
        "pedestrian zones in city centers",
        "underground transport systems",
        "smart traffic management",
        "bridge engineering and maintenance",
        "flood-resistant urban infrastructure",
        "public transport accessibility",
        "waste management in megacities",
    ],
    "science_research": [
        "citizen science projects",
        "the role of fieldwork in research",
        "Antarctic scientific stations",
        "telescope technology and astronomy",
        "volcanic monitoring systems",
        "scientific collaboration across countries",
        "research in extreme weather conditions",
        "data visualization in science",
        "accidental discoveries in laboratories",
        "ethical questions in scientific experimentation",
    ],
}

# ─── Article Angles ──────────────────────────────────────────────────────────

ARTICLE_ANGLES = [
    "historical development",
    "environmental impact",
    "public health benefits",
    "policy debate",
    "technological innovation",
    "case study of one city or region",
    "research experiment",
    "economic cost-benefit",
    "comparison between countries",
    "future trends and projections",
]

# ─── Text Structures ─────────────────────────────────────────────────────────

TEXT_STRUCTURES = [
    "problem → solution",
    "cause → effect",
    "theory → evidence",
    "experiment → results",
    "comparison of two approaches",
    "chronological development",
    "question → competing explanations",
    "process explanation",
    "debate between researchers",
    "case study with conclusions",
]

# ─── Geographic Contexts ─────────────────────────────────────────────────────

GEOGRAPHIC_CONTEXTS = [
    "Netherlands",
    "Australia",
    "Canada",
    "China",
    "Kenya",
    "Norway",
    "Brazil",
    "Indonesia",
    "Iceland",
    "United States",
]

# ─── Research Contexts ───────────────────────────────────────────────────────

RESEARCH_CONTEXTS = [
    "university research project",
    "long-term field observation",
    "controlled laboratory experiment",
    "international collaboration study",
    "government-funded research program",
    "technology pilot project",
    "archaeological excavation",
    "large-scale statistical analysis",
    "citizen science initiative",
    "historical archive analysis",
]

# ─── Stakeholder Perspectives ────────────────────────────────────────────────

STAKEHOLDER_PERSPECTIVES = [
    "scientists",
    "engineers",
    "local residents",
    "government planners",
    "environmental organizations",
    "economists",
    "industry professionals",
    "educators",
    "healthcare workers",
    "urban planners",
]

# ─── Evidence Types ──────────────────────────────────────────────────────────

EVIDENCE_TYPES = [
    "survey results",
    "experiment data",
    "historical records",
    "population statistics",
    "satellite observations",
    "economic indicators",
    "behavioral experiments",
    "archaeological artifacts",
    "environmental measurements",
    "technology performance metrics",
]

# ─── Passage Tones ───────────────────────────────────────────────────────────

PASSAGE_TONES = [
    "explain a scientific concept",
    "describe a research discovery",
    "evaluate competing theories",
    "analyze policy outcomes",
    "describe technological innovation",
    "discuss environmental challenges",
    "present historical developments",
    "summarize research findings",
    "explain a natural process",
    "explore social implications",
]

# ─── Paragraph Blueprints ───────────────────────────────────────────────────

PARAGRAPH_BLUEPRINTS = [
    ["introduction", "problem", "research", "solution", "future direction"],
    ["introduction", "historical background", "experiment", "comparison", "conclusion"],
    ["introduction", "theory A", "theory B", "evaluation", "conclusion"],
    ["introduction", "cause", "effect", "policy response", "outlook"],
    ["introduction", "case study", "analysis", "implications", "conclusion"],
]

# ─── Numerical Ranges ───────────────────────────────────────────────────────

NUMERICAL_RANGES = {
    "year": (1800, 2025),
    "percentage": (5, 85),
    "distance_km": (5, 600),
    "population": (10000, 5000000),
    "temperature_c": (-10, 45),
    "area_sq_km": (50, 50000),
    "cost_million": (1, 500),
    "sample_size": (50, 10000),
    "duration_years": (2, 30),
    "growth_rate": (1, 25),
}

# Topic keywords → relevant number categories
TOPIC_NUMBER_MAP = {
    "coral": ["temperature_c", "area_sq_km", "percentage"],
    "wetland": ["area_sq_km", "percentage", "year"],
    "urban": ["population", "percentage", "cost_million"],
    "forest": ["area_sq_km", "percentage", "year"],
    "biodiversity": ["percentage", "sample_size", "year"],
    "pollution": ["percentage", "population", "cost_million"],
    "soil": ["area_sq_km", "percentage", "duration_years"],
    "bird": ["distance_km", "population", "percentage"],
    "solar": ["percentage", "cost_million", "growth_rate"],
    "wind": ["cost_million", "percentage", "distance_km"],
    "battery": ["percentage", "cost_million", "growth_rate"],
    "water": ["population", "percentage", "cost_million"],
    "energy": ["percentage", "cost_million", "growth_rate"],
    "hydrogen": ["percentage", "cost_million", "temperature_c"],
    "nuclear": ["percentage", "cost_million", "population"],
    "recycling": ["percentage", "population", "cost_million"],
    "reservoir": ["area_sq_km", "population", "percentage"],
    "bee": ["percentage", "sample_size", "distance_km"],
    "plant": ["sample_size", "percentage", "temperature_c"],
    "migration": ["distance_km", "population", "percentage"],
    "microbiome": ["sample_size", "percentage", "duration_years"],
    "sleep": ["sample_size", "percentage", "duration_years"],
    "genetic": ["sample_size", "percentage", "year"],
    "aging": ["population", "percentage", "duration_years"],
    "marine": ["temperature_c", "area_sq_km", "percentage"],
    "seed": ["distance_km", "sample_size", "percentage"],
    "disease": ["sample_size", "percentage", "population"],
    "exercise": ["sample_size", "percentage", "duration_years"],
    "vaccination": ["population", "percentage", "cost_million"],
    "health": ["population", "percentage", "cost_million"],
    "antibiotic": ["percentage", "sample_size", "year"],
    "telemedicine": ["population", "percentage", "growth_rate"],
    "stress": ["sample_size", "percentage", "duration_years"],
    "decision": ["sample_size", "percentage", "duration_years"],
    "habit": ["sample_size", "percentage", "duration_years"],
    "memory": ["sample_size", "percentage", "duration_years"],
    "motivation": ["sample_size", "percentage", "duration_years"],
    "attention": ["sample_size", "percentage", "duration_years"],
    "education": ["population", "percentage", "sample_size"],
    "learning": ["sample_size", "percentage", "duration_years"],
    "homework": ["sample_size", "percentage", "duration_years"],
    "literacy": ["population", "percentage", "year"],
    "classroom": ["sample_size", "percentage", "cost_million"],
    "robotics": ["percentage", "cost_million", "growth_rate"],
    "artificial intelligence": ["percentage", "cost_million", "growth_rate"],
    "wearable": ["sample_size", "percentage", "growth_rate"],
    "3D printing": ["percentage", "cost_million", "growth_rate"],
    "smart home": ["percentage", "cost_million", "sample_size"],
    "privacy": ["population", "percentage", "sample_size"],
    "autonomous": ["percentage", "cost_million", "distance_km"],
    "drone": ["percentage", "cost_million", "area_sq_km"],
    "translation": ["population", "percentage", "sample_size"],
    "robot": ["percentage", "cost_million", "sample_size"],
    "remote work": ["sample_size", "percentage", "population"],
    "gig economy": ["population", "percentage", "growth_rate"],
    "housing": ["population", "cost_million", "percentage"],
    "tourism": ["population", "cost_million", "percentage"],
    "business": ["percentage", "cost_million", "growth_rate"],
    "leadership": ["sample_size", "percentage", "population"],
    "workplace": ["sample_size", "percentage", "cost_million"],
    "shopping": ["population", "percentage", "cost_million"],
    "skills": ["population", "percentage", "growth_rate"],
    "ancient": ["year", "distance_km", "population"],
    "archaeological": ["year", "area_sq_km", "sample_size"],
    "heritage": ["year", "cost_million", "population"],
    "agriculture": ["year", "area_sq_km", "percentage"],
    "maritime": ["year", "distance_km", "population"],
    "museum": ["year", "population", "cost_million"],
    "language": ["population", "percentage", "year"],
    "storytelling": ["population", "year", "percentage"],
    "multilingual": ["population", "percentage", "sample_size"],
    "bicycle": ["distance_km", "population", "percentage"],
    "rail": ["distance_km", "cost_million", "population"],
    "airport": ["population", "cost_million", "percentage"],
    "pedestrian": ["population", "percentage", "distance_km"],
    "transport": ["population", "cost_million", "distance_km"],
    "traffic": ["population", "percentage", "cost_million"],
    "bridge": ["distance_km", "cost_million", "year"],
    "flood": ["area_sq_km", "cost_million", "population"],
    "waste": ["population", "percentage", "cost_million"],
    "citizen science": ["sample_size", "percentage", "population"],
    "fieldwork": ["sample_size", "distance_km", "duration_years"],
    "Antarctic": ["temperature_c", "distance_km", "area_sq_km"],
    "telescope": ["distance_km", "cost_million", "year"],
    "volcanic": ["temperature_c", "distance_km", "year"],
    "collaboration": ["sample_size", "population", "cost_million"],
    "weather": ["temperature_c", "distance_km", "percentage"],
    "visualization": ["sample_size", "percentage", "population"],
    "laboratory": ["sample_size", "percentage", "cost_million"],
    "ethical": ["sample_size", "percentage", "population"],
}

# ─── Question Compositions ──────────────────────────────────────────────────

# Flexible question mix — 6-8 questions using any combination of types
# Each composition is a list of (type, count) tuples
QUESTION_COMPOSITIONS = [
    [("true_false_not_given", 4), ("multiple_choice", 2), ("sentence_completion", 2)],
    [("true_false_not_given", 4), ("summary_completion", 3), ("short_answer", 1)],
    [("true_false_not_given", 3), ("matching_headings", 3), ("short_answer", 2)],
    [("matching_headings", 4), ("multiple_choice", 2), ("sentence_completion", 2)],
    [("true_false_not_given", 4), ("matching_information", 2), ("multiple_choice", 2)],
    [("summary_completion", 3), ("true_false_not_given", 3), ("multiple_choice", 2)],
    [("matching_headings", 3), ("sentence_completion", 3), ("short_answer", 2)],
    [("true_false_not_given", 5), ("sentence_completion", 3)],
    [("matching_information", 3), ("summary_completion", 3), ("multiple_choice", 2)],
    [("true_false_not_given", 4), ("short_answer", 2), ("multiple_choice", 2)],
]

# ─── Synonym Distance Weights ───────────────────────────────────────────────

SYNONYM_DISTANCE_WEIGHTS = {
    2: 0.20,  # standard synonym substitution
    3: 0.35,  # grammatical transformation
    4: 0.30,  # structural paraphrase
    5: 0.15,  # conceptual paraphrase
}


# ─── Metadata Generator ─────────────────────────────────────────────────────

def generate_metadata(avoid_topics: list[str] | None = None) -> dict:
    """Generate reading exercise metadata via pure Python randomization.

    Returns a dict with: topic, category, angle, structure, region, research,
    stakeholder, evidence, tone, blueprint, numbers, question_composition,
    synonym_distances.
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

    # Pick one value from each dimension
    angle = random.choice(ARTICLE_ANGLES)
    structure = random.choice(TEXT_STRUCTURES)
    region = random.choice(GEOGRAPHIC_CONTEXTS)
    research = random.choice(RESEARCH_CONTEXTS)
    stakeholder = random.choice(STAKEHOLDER_PERSPECTIVES)
    evidence = random.choice(EVIDENCE_TYPES)
    tone = random.choice(PASSAGE_TONES)
    blueprint = random.choice(PARAGRAPH_BLUEPRINTS)

    # Pre-generate numbers relevant to topic
    numbers = _pick_numbers(topic)

    # Pick question composition
    composition = random.choice(QUESTION_COMPOSITIONS)
    total_questions = sum(count for _, count in composition)

    # Assign synonym distance levels to each question
    levels = list(SYNONYM_DISTANCE_WEIGHTS.keys())
    weights = list(SYNONYM_DISTANCE_WEIGHTS.values())
    synonym_distances = random.choices(levels, weights=weights, k=total_questions)

    return {
        "topic": topic,
        "category": category,
        "angle": angle,
        "structure": structure,
        "region": region,
        "research": research,
        "stakeholder": stakeholder,
        "evidence": evidence,
        "tone": tone,
        "blueprint": blueprint,
        "numbers": numbers,
        "question_composition": composition,
        "total_questions": total_questions,
        "synonym_distances": synonym_distances,
    }


def _pick_numbers(topic: str) -> dict[str, int | float]:
    """Pick 3-5 random numbers relevant to the topic from NUMERICAL_RANGES."""
    topic_lower = topic.lower()
    relevant_keys = set()
    for keyword, num_keys in TOPIC_NUMBER_MAP.items():
        if keyword in topic_lower:
            relevant_keys.update(num_keys)

    # Always include a few defaults if nothing matched
    if not relevant_keys:
        relevant_keys = {"year", "percentage", "sample_size"}

    # Pick 3-5 from relevant
    keys = list(relevant_keys)
    if len(keys) > 5:
        keys = random.sample(keys, 5)
    elif len(keys) < 3:
        # Pad with random extras
        extras = [k for k in NUMERICAL_RANGES if k not in relevant_keys]
        keys += random.sample(extras, min(3 - len(keys), len(extras)))

    result = {}
    for k in keys:
        lo, hi = NUMERICAL_RANGES[k]
        val = random.randint(lo, hi)
        # Avoid round numbers: nudge if divisible by 50 or 100
        if k not in ("year",):  # don't nudge years
            if val % 100 == 0 and val > lo:
                val += random.choice([-17, 13, 23, -27, 37, 43])
            elif val % 50 == 0 and val > lo:
                val += random.choice([-7, 3, 13, -3, 17])
        val = max(lo, min(hi, val))
        result[k] = val

    return result
