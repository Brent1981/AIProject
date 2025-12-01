# ai_engine/lib/tool_helpers.py
import numexpr
from ddgs import DDGS
from lib.ollama_helpers import call_ollama
from lib.prompts import WEB_SEARCH_ANSWER_PROMPT_TEMPLATE, CALCULATOR_ANSWER_PROMPT_TEMPLATE

def handle_web_search(prompt_text, model_to_use):
    """Handles the web search action."""
    print(f"Performing web search for: '{prompt_text}'")
    try:
        with DDGS() as ddgs:
            search_results = list(ddgs.text(prompt_text, max_results=5))

        print(f"Raw search results: {search_results}") # Debug print

        if not search_results:
            return "I couldn't find any information on that topic."

        # Format results for the LLM
        formatted_results = "\n\n".join(
            [f"Title: {r['title']}\nSnippet: {r['body']}" for r in search_results]
        )

        # Create a new prompt to generate an answer
        answer_prompt = WEB_SEARCH_ANSWER_PROMPT_TEMPLATE.format(
            prompt=prompt_text, search_results=formatted_results
        )

        final_answer = call_ollama(answer_prompt, model_to_use)
        return final_answer.strip()

    except Exception as e:
        print(f"Error during web search: {e}")
        return "I had a problem searching the web."

def perform_calculation(expression):
    """Safely evaluates a mathematical expression."""
    print(f"Performing calculation for: '{expression}'")
    try:
        # numexpr is generally safe, but we can add a layer of sanitization
        # This is a simple check; more complex validation could be added.
        allowed_chars = "0123456789.+-*/() "
        sanitized_expression = ''.join([c for c in expression if c in allowed_chars])
        
        if not sanitized_expression:
            raise ValueError("Expression is empty after sanitization.")

        # Using numexpr's evaluate function
        result = numexpr.evaluate(sanitized_expression).item()
        return str(result)
    except Exception as e:
        print(f"Error during calculation: {e}")
        return f"I had a problem calculating that. The error was: {e}"
