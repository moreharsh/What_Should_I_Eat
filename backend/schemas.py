from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, TypedDict

class DishOption(BaseModel):
    dish_name: str = Field(min_length=1, max_length=120)
    teaser: str = Field(min_length=1, max_length=500)
    primary_protein: str = Field(min_length=1, max_length=120)

    @field_validator("dish_name", "teaser", "primary_protein")
    @classmethod
    def reject_blank_text(cls, value):
        if not value.strip():
            raise ValueError("Dish field cannot be blank")
        return value.strip()


class MenuSchema(BaseModel):
    options: List[DishOption] = Field(min_length=1, max_length=5)


class RecipeSchema(BaseModel):
    dish_name: str = Field(min_length=1, max_length=120)
    prep_time: str = Field(min_length=1, max_length=150)
    cook_time: str = Field(min_length=1, max_length=150)
    servings: str = Field(min_length=1, max_length=80)
    ingredients: List[str] = Field(min_length=1, max_length=100)
    instructions: List[str] = Field(min_length=1, max_length=100)
    chef_pro_tip: str = Field(min_length=1, max_length=1000)

    @field_validator("dish_name", "prep_time", "cook_time", "servings", "chef_pro_tip")
    @classmethod
    def reject_blank_text(cls, value):
        if not value.strip():
            raise ValueError("Recipe field cannot be blank")
        return value.strip()

    @field_validator("ingredients", "instructions")
    @classmethod
    def reject_blank_steps(cls, values):
        if any(not value.strip() or len(value) > 1000 for value in values):
            raise ValueError("Recipe list contains blank or oversized entries")
        return [value.strip() for value in values]


class AgentState(BaseModel):
    cuisine: str = Field(default="", description="The cuisine category selected by the user (e.g., 'Italian').")
    dietary_preferences: List[str] = Field(default_factory=list, description="Optional restrictions like Vegan, Gluten-Free, Keto, etc.")
    menu_options: List[dict] = Field(default_factory=list, description="The cached 5 dish options returned by Phase 1 of the Chef Agent.")
    selected_dish: Optional[str] = Field(default=None, description="The specific dish chosen by the user from the menu_options.")
    recipe_details: Optional[dict] = Field(default=None, description="Structured dictionary holding the verified ingredients and instructions.")
    media_links: Optional[dict] = Field(default=None, description="Aggregated media links containing 'image_url' and 'youtube_embed_url'.")
    errors: List[str] = Field(default_factory=list, description="Logs any failed validation checks or API execution timeouts for recovery routing.")
