"""Parallel recipe graph with isolated Chef and Media failures."""
import asyncio
import logging
import time

from langgraph.graph import END, START, StateGraph

from schemas import AgentState, RecipeSchema
from ollama_fallback import generate_ollama_recipe, ollama_config

logger = logging.getLogger(__name__)

CHEF_TIMEOUT_SECONDS = 90
MEDIA_TIMEOUT_SECONDS = 12


async def run_media_safely(state, media_agent, timeout=MEDIA_TIMEOUT_SECONDS):
    """Media is optional: its failure must not discard an otherwise valid recipe."""
    start = time.monotonic()
    try:
        result = await asyncio.wait_for(media_agent(state), timeout=timeout)
        if not isinstance(result, dict):
            raise ValueError("Media agent returned a non-object result")
        logger.info("recipe.media status=ok duration_ms=%.0f", (time.monotonic() - start) * 1000)
        return {"media_links": result.get("media_links")}
    except Exception as exc:
        logger.warning(
            "recipe.media status=unavailable kind=%s duration_ms=%.0f",
            type(exc).__name__, (time.monotonic() - start) * 1000,
        )
        return {"media_links": None}


def build_recipe_graph(chef_agent, media_agent, *, chef_timeout=CHEF_TIMEOUT_SECONDS,
                       media_timeout=MEDIA_TIMEOUT_SECONDS):
    """Run Chef and Media once in parallel; update distinct state keys."""
    async def chef_node(state: AgentState):
        start = time.monotonic()
        try:
            # Gemini's two configured models are tried inside chef_agent.
            # The synchronous SDK runs in a worker thread.
            result = await asyncio.wait_for(
                asyncio.to_thread(chef_agent, state), timeout=chef_timeout
            )
            if not isinstance(result, dict) or not result.get("recipe_details"):
                raise ValueError("Chef agent returned no recipe details")
            recipe = RecipeSchema.model_validate(result["recipe_details"]).model_dump()
            logger.info("recipe.chef provider=gemini status=ok duration_ms=%.0f",
                        (time.monotonic() - start) * 1000)
            return {"recipe_details": recipe}
        except Exception as exc:
            logger.warning(
                "recipe.chef provider=gemini status=failed kind=%s duration_ms=%.0f",
                type(exc).__name__, (time.monotonic() - start) * 1000,
            )
            if ollama_config() is None:
                # Disabled means cloud-only: preserve the existing controlled
                # 502 response from the API; do not fabricate a recipe.
                raise
            try:
                recipe = await generate_ollama_recipe(state)
                logger.info("recipe.chef provider=ollama status=ok")
                return {"recipe_details": recipe}
            except Exception as fallback_exc:
                logger.warning(
                    "recipe.chef provider=ollama status=failed kind=%s",
                    type(fallback_exc).__name__,
                )
                raise RuntimeError("All configured recipe providers failed") from fallback_exc

    async def media_node(state: AgentState):
        return await run_media_safely(state, media_agent, timeout=media_timeout)

    workflow = StateGraph(AgentState)
    workflow.add_node("chef", chef_node)
    workflow.add_node("media", media_node)
    workflow.add_edge(START, "chef")
    workflow.add_edge(START, "media")
    workflow.add_edge("chef", END)
    workflow.add_edge("media", END)
    return workflow.compile()
