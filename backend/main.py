import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

from langgraph.graph import StateGraph, END
from schemas import AgentState
from agents import chef_agent, media_agent

app = FastAPI(title="What Should I Eat?")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


menu_workflow = StateGraph(AgentState)
menu_workflow.add_node("chef", chef_agent)
menu_workflow.set_entry_point("chef")
menu_workflow.add_edge("chef", END)
menu_graph = menu_workflow.compile()

recipe_workflow = StateGraph(AgentState)
recipe_workflow.add_node("chef", chef_agent)
recipe_workflow.add_node("media", media_agent)

# Set both as entry points to enforce simultaneous processing!
recipe_workflow.set_entry_point("chef")
recipe_workflow.set_entry_point("media")
recipe_workflow.add_edge("chef", END)
recipe_workflow.add_edge("media", END)
recipe_graph = recipe_workflow.compile()


class MenuRequest(BaseModel):
    cuisine: str
    dietary_restrictions: Optional[List[str]] = []

class RecipeRequest(BaseModel):
    selected_dish: str
    dietary_restrictions: Optional[List[str]] = []


@app.post("/api/menu")
async def get_menu_options(request: MenuRequest):
    try:
        initial_state = AgentState(
            cuisine=request.cuisine,
            dietary_preferences=request.dietary_restrictions
        )

        result = menu_graph.invoke(initial_state)
        return {"menu_options": result.get("menu_options", [])}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/recipe")
async def get_recipe_details(request: RecipeRequest):
    try:
        recipe_state = AgentState(
            selected_dish=request.selected_dish,
            dietary_preferences=request.dietary_restrictions
        )

        result = await recipe_graph.ainvoke(recipe_state)

        return {
            "recipe_details": result.get("recipe_details"),
            "media_links": result.get("media_links")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)