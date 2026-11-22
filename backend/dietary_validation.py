"""Conservative ingredient screening for plainly incompatible dietary requests.

This is a best-effort screen, NOT food-allergen certification. Generated
recipes may omit ingredients or cross-contact information. Unknown ingredients
require user verification.
"""
import re


# Specific terms avoid rejecting e.g. coconut milk or plant-based cheese.
_MEAT = r"\b(?:chicken|beef|pork|lamb|mutton|bacon|ham|turkey|duck|gelatin|lard|sausage|pepperoni)\b"
_FISH = r"\b(?:fish|salmon|tuna|anchov(?:y|ies)|shrimp|prawn|crab|lobster|oyster|clam|mussel|sardine)\b"
_EGG = r"\b(?:egg|eggs|mayonnaise|honey)\b"
_DAIRY = r"\b(?:butter|ghee|paneer|whey|casein|yogurt|yoghurt|cream|cheese|cow'?s milk|whole milk|skim milk|dairy milk|(?<!coconut )(?<!almond )(?<!oat )(?<!soy )(?<!cashew )(?<!rice )milk)\b"
_GLUTEN = r"\b(?:wheat|barley|rye|semolina|couscous|bulgur|seitan|all-purpose flour|plain flour|maida|farina|malt extract|regular soy sauce|breadcrumbs)\b"
_RULES = {
    "vegetarian": [_MEAT, _FISH],
    "vegan": [_MEAT, _FISH, _EGG, _DAIRY],
    "pescatarian": [_MEAT],
    "dairy-free": [_DAIRY],
    "gluten-free": [_GLUTEN],
}
_SUPPORTED = frozenset(_RULES)


def incompatible_ingredients(recipe, restrictions):
    """Return ingredient strings containing explicit conflicts; never certify safety."""
    if not isinstance(recipe, dict) or not isinstance(recipe.get("ingredients"), list):
        raise ValueError("Recipe must contain an ingredients list")
    unsupported = set(restrictions) - _SUPPORTED
    if unsupported:
        raise ValueError(f"Unsupported dietary restrictions: {', '.join(sorted(unsupported))}")

    conflicts = []
    for ingredient in recipe["ingredients"]:
        if not isinstance(ingredient, str):
            raise ValueError("Ingredient entries must be text")
        cleaned = ingredient.casefold()
        # Gluten-free variants of soy sauce and alternative flours may be permitted;
        # still require humans to verify their packaging and cross-contact.
        if any(re.search(pattern, cleaned) for restriction in restrictions for pattern in _RULES[restriction]):
            conflicts.append(ingredient)
    return conflicts
