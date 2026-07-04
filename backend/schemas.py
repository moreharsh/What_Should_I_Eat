from pydantic import BaseModel, Field
from typing import List, Optional, TypedDict

class DishOption(BaseModel):
    dish_name: str
    teaser: str
    primary_protein: str

class MenuSchema(BaseModel):
    options: List[DishOption]

class RecipeSchema(BaseModel):
    dish_name: str
    prep_time: str
    cook_time: str
    servings: str
    ingredients: List[str]
    instructions: List[str]
    chef_pro_tip: str


class AgentState(BaseModel):
    cuisine: str = Field(default="", description="The cuisine category selected by the user (e.g., 'Italian').")
    dietary_preferences: List[str] = Field(default_factory=list, description="Optional restrictions like Vegan, Gluten-Free, Keto, etc.")
    menu_options: List[dict] = Field(default_factory=list, description="The cached 5 dish options returned by Phase 1 of the Chef Agent.")
    selected_dish: Optional[str] = Field(default=None, description="The specific dish chosen by the user from the menu_options.")
    recipe_details: Optional[dict] = Field(default=None, description="Structured dictionary holding the verified ingredients and instructions.")
    media_links: Optional[dict] = Field(default=None, description="Aggregated media links containing 'image_url' and 'youtube_embed_url'.")
    errors: List[str] = Field(default_factory=list, description="Logs any failed validation checks or API execution timeouts for recovery routing.")
