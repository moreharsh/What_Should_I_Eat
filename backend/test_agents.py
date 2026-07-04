import asyncio
from schemas import AgentState
from agents import chef_agent, media_agent
import json


async def run_diagnostic():
    print("🚀 Running Phase 1 Diagnostic (Generating Options)...")
    initial_state = AgentState(cuisine="Indian", dietary_preferences=["Vegetarian"])

    phase1_output = chef_agent(initial_state)
    print("\n[Chef Agent Options Response]:")
    print(json.dumps(phase1_output, indent=2))

    selected = phase1_output["menu_options"][0]["dish_name"]
    print(f"\n👉 Simulating user selected dish: '{selected}'")
    print("\n🚀 Running Phase 2 Diagnostic (Generating Details & Media)...")
    phase2_state = AgentState(cuisine="Indian", selected_dish=selected)

    recipe_output = chef_agent(phase2_state)
    media_output = await media_agent(phase2_state)
    
    print("\n[Chef Agent Detailed Recipe]:")
    print(json.dumps(recipe_output, indent=2))
    print("\n[Media Broker Results]:")
    print(json.dumps(media_output, indent=2))

if __name__ == "__main__":
    asyncio.run(run_diagnostic())