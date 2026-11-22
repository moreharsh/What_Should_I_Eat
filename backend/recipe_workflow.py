"""Parallel recipe graph with isolated Chef and Media failures."""
import asyncio
import logging
import time

from langgraph.graph import END, START, StateGraph

from schemas import AgentState

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
            # The Gemini client and its retry sleeps are synchronous, so use a
            # worker thread instead of blocking the FastAPI event loop.
            result = await asyncio.wait_for(
                asyncio.to_thread(chef_agent, state), timeout=chef_timeout
            )
            if not isinstance(result, dict) or not result.get("recipe_details"):
                raise ValueError("Chef agent returned no recipe details")
            logger.info("recipe.chef status=ok duration_ms=%.0f",
                        (time.monotonic() - start) * 1000)
            return {"recipe_details": result["recipe_details"]}
        except Exception as exc:
            logger.exception(
                "recipe.chef status=failed kind=%s duration_ms=%.0f",
                type(exc).__name__, (time.monotonic() - start) * 1000,
            )
            raise

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
