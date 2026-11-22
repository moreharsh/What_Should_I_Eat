"""Best-effort screen for explicit dietary conflicts, not an allergy certification.

This intentionally cannot determine ingredient provenance or cross-contact.
Unknown or ambiguous ingredient names require manual checking.
"""
import re

SUPPORTED_RESTRICTIONS = frozenset(
    ("vegetarian", "vegan", "pescatarian", "dairy-free", "gluten-free")
)

_MEAT = r"\b(?:chicken|beef|pork|lamb|mutton|bacon|ham|turkey|duck|gelatin|lard|sausage|pepperoni)\b"
_FISH = r"\b(?:fish|salmon|tuna|anchov(?:y|ies)|shrimp|prawn|crab|lobster|oyster|clam|mussel|sardine)\b"
_EGG = r"\b(?:eggs?|mayonnaise|honey)\b"
_DAIRY = r"\b(?:butter|ghee|paneer|whey|casein|yogurt|yoghurt|cream|cheese|milk)\b"
_GLUTEN = r"\b(?:wheat|barley|rye|semolina|couscous|bulgur|seitan|all-purpose flour|plain flour|maida|farina|malt extract|regular soy sauce|breadcrumbs)\b"
_RULES = {
    "vegetarian": (_MEAT, _FISH),
    "vegan": (_MEAT, _FISH, _EGG, _DAIRY),
    "pescatarian": (_MEAT,),
    "dairy-free": (_DAIRY,),
    "gluten-free": (_GLUTEN,),
}

# Mask only explicit substitutions, not an entire ingredient entry. A statement
# such as "vegan cheese with cow's milk" must still flag the milk.
_PLANT_PREFIX = r"(?:vegan|plant[ -]based|dairy[ -]free|non[ -]dairy)"
_PLANT_MILKS = r"(?:almond|coconut|oat|soy|cashew|rice|pea|hemp) milk"
_SUBSTITUTION = re.compile(
    rf"\b(?:{_PLANT_PREFIX}\s+(?:milk|cheese|butter|yogurt|yoghurt|cream|mayonnaise|sausage|bacon)|{_PLANT_MILKS})\b",
    re.IGNORECASE,
)


def incompatible_ingredients(recipe, restrictions):
    """Return explicit conflicting ingredient strings; an empty result is NOT proof of safety."""
    if not isinstance(recipe, dict) or not isinstance(recipe.get("ingredients"), list):
        raise ValueError("Recipe must contain an ingredients list")
    unsupported = set(restrictions) - SUPPORTED_RESTRICTIONS
    if unsupported:
        raise ValueError("Unsupported dietary restriction")

    conflicts = []
    for ingredient in recipe["ingredients"]:
        if not isinstance(ingredient, str) or not ingredient.strip():
            raise ValueError("Ingredient entries must be nonempty text")
        # Preserve the other words so conflicting ingredients after a safe
        # substitution are still detected.
        checked = _SUBSTITUTION.sub(" ", ingredient.casefold())
        if any(re.search(pattern, checked) for restriction in restrictions for pattern in _RULES[restriction]):
            conflicts.append(ingredient)
    return conflicts
