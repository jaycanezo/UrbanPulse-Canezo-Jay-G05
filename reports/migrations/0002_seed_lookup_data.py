from django.db import migrations

SEED_BARANGAYS = [
    ("Lahug", "NORTH-1"),
    ("Guadalupe", "SOUTH-1"),
    ("Mabolo", "NORTH-2"),
    ("Apas", "NORTH-1"),
    ("Banilad", "NORTH-1"),
    ("Capitol Site", "NORTH-2"),
    ("Talamban", "NORTH-1"),
    ("Labangon", "SOUTH-1"),
    ("Pardo", "SOUTH-2"),
    ("Sambag I", "SOUTH-1"),
    ("Sambag II", "SOUTH-1"),
    ("Bulacao", "SOUTH-2"),
]

SEED_CATEGORIES = [
    (
        "Pothole / Road Damage",
        "Deep potholes, cracked asphalt, or eroded roadway surfaces obstructing safe transit.",
    ),
    (
        "Broken Streetlight",
        "Non-functioning, flickering, or damaged public streetlamps creating dark zones.",
    ),
    (
        "Clogged Drainage / Flooding",
        "Blocked storm drains, overflowing canals, or standing floodwater on public roads.",
    ),
    (
        "Damaged Sidewalk",
        "Broken concrete slabs, missing curb ramps, or unsafe pedestrian walkways.",
    ),
    (
        "Fallen Tree / Debris",
        "Uprooted trees, fallen branches, or heavy debris blocking streets or sidewalks.",
    ),
    (
        "Traffic Signal Malfunction",
        "Dark, stuck, or mistimed traffic lights and damaged pedestrian crossing signals.",
    ),
    (
        "Open Manhole / Utility Hazard",
        "Uncovered manholes, loose utility covers, or sagging/exposed public cables.",
    ),
]


def seed_lookup_data(apps, schema_editor):
    Barangay = apps.get_model("reports", "Barangay")
    HazardCategory = apps.get_model("reports", "HazardCategory")

    for name, district_code in SEED_BARANGAYS:
        Barangay.objects.get_or_create(name=name, defaults={"district_code": district_code})

    for name, description in SEED_CATEGORIES:
        HazardCategory.objects.get_or_create(name=name, defaults={"description": description})


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_lookup_data, noop_reverse),
    ]
