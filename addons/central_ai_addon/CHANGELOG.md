# Changelog

## Version 0.10.0
- ✨ **Feature:** Added internet-connected knowledge. The AI can now search the web to answer general knowledge questions that are not related to Home Assistant entities.
- ✨ **Feature:** Implemented a new `web_search` action, allowing the AI to decide between controlling a device and searching the internet.
- ♻️ **Refactor:** The core logic now intelligently determines if a question is about a known device or if it requires a web search.
- 📝 **Dependencies:** Added the `duckduckgo-search` library to `requirements.txt` to power the web search functionality.

## Version 0.9.0
- ✨ **Feature:** Added long-term memory. The AI can now store and retrieve information, enabling it to learn and recall facts from previous conversations.
- ✨ **Feature:** Implemented `remember:` command to explicitly store information in the AI's long-term memory.
- ✨ **Infrastructure:** Created a new `chromadb_addon` to run a standalone ChromaDB vector database server, providing a scalable memory backend.
- ♻️ **Refactor:** Integrated the `chromadb-client` into the `central_ai_addon` to communicate with the new memory server.
- ♻️ **Refactor:** Updated all prompts to include a "Relevant Memories" section, allowing the AI to use retrieved memories as context.
- 🐛 **Fix:** Resolved a critical bug where asking a general question would cause a `local variable 'all_entities' referenced before assignment` error.

## Version 0.8.0
- ✨ **Feature:** Added a Flask-based web API to the addon.
- ✨ **Feature:** The addon now exposes a `/api/prompt` endpoint to receive prompts via HTTP POST requests.
- ♻️ **Refactor:** The core prompt processing logic has been refactored into a `process_prompt` function, which is now used by both the MQTT message handler and the new Flask API. This ensures consistent behavior across both interfaces.
- 📝 **Configuration:** The addon now exposes port `8099` for the web API. `host_network: true` has been removed in favor of explicit port mapping.

## Version 0.7.0
- ✨ **Feature:** Added parameter support for area commands. The add-on can now parse and apply `brightness`, `color`, `transition`, and `flash` parameters to area-based commands (e.g., "Set the living room lights to blue over 5 seconds at 50% brightness").
- ✨ **Feature:** Refined confirmation messages for multi-command scenarios (including area commands). Responses are now consolidated into a single, user-friendly message that summarizes all actions taken and parameters set.
- ✨ **Feature:** Implemented average temperature calculation. The add-on can now understand questions like "What is the average temperature in the house?", find all temperature sensors, gracefully handle unavailable sensors, and calculate the average.
- ✨ **Feature:** Improved history query functionality.
    - Fixed entity detection for history queries using a robust hybrid keyword/fuzzy matching approach.
    - Enhanced `prettify_history` to generate semantic descriptions of historical events (e.g., "door was opened", "light was turned on"), leading to more natural AI responses.
- ✨ **Feature:** Implemented "Smart Command Generation" for area-based requests. The add-on reliably detects area commands, directly identifies all matching entities within the specified area, and generates the necessary commands itself, bypassing the LLM for this critical step.
- ✨ **Performance:** Eliminated the second LLM call for confirmation messages, replacing it with a fast, template-based response.
- ✨ **Performance:** Implemented a 5-minute cache for Home Assistant Area data, reducing redundant API calls.
- ✨ **Performance:** Removed the `time.sleep(1)` delay after service calls.
- ♻️ **Refactor:** Replaced the entity matching logic with a more robust fuzzy string matching algorithm (`difflib`), significantly improving the accuracy of the self-correction mechanism.
- 🐛 **Fix:** Improved area command detection by stripping punctuation from prompts for more reliable keyword matching.

## Version 0.3.4
- 🐛 **Bug Fix:** Reverted changes related to `target_entity_id_hint` in `find_best_matching_entity` and its call in `on_message`. This ensures that when the AI hallucinates an `entity_id`, the self-correction mechanism relies solely on the original `prompt_text` to find the correct entity, preventing incorrect matches.

## Version 0.3.3
- ✨ **Feature:** Enhanced `entity_id` self-correction. The `find_best_matching_entity` function now uses the AI's suggested (but potentially invalid) `entity_id` as a hint, significantly improving the accuracy of self-correction.

## Version 0.3.2
- ✨ **Feature:** Implemented self-correction for `entity_id`. The addon now validates the `entity_id` from the AI and attempts to find a correct match if it's invalid, making it more resilient to hallucinations.

## Version 0.3.1
- 📝 **PROMPT:** Replaced the main prompt with a much stricter version to force the AI to return only JSON and prevent conversational responses. This improves reliability.

## Version 0.3.0
- ✨ **Feature:** Implemented short-term conversational memory.
- 📝 **PROMPT:** Updated all prompts to include conversation history.
- ♻️ **Refactor:** Modified `on_message` to manage and inject conversation history.

## Version 0.2.2
- 🐛 **Bug Fix:** Fixed a bug where timestamps in history queries were not converted to the user's local timezone.
- ✨ **Feature:** Added a function to get the timezone from Home Assistant's configuration.
- ♻️ **Refactor:** Updated `prettify_history` to use the fetched timezone.
- 📝 **Dependencies:** Added `pytz` to `requirements.txt`.

## Version 0.2.1
- 🐛 **Bug Fix:** Improved the "Intelligent Action Dispatcher" to correctly identify history-related questions.
- 📝 **Keywords:** Added more keywords to the dispatcher to make it more robust.

## Version 0.2.0
- ✨ **Feature:** Added support for history queries.
- 📝 **PROMPT:** Updated prompt to include get_history action.
- ♻️ **Refactor:** Modified on_message to handle history queries.

## Version 0.1.9
- Fixed a critical bug where the addon was not executing service calls after the intelligent action dispatcher was implemented.
- The `client.publish(STATE_TOPIC, result, retain=False)` line was moved to the correct place after the `call_homeassistant_api` function.

## Version 0.1.8
- Fixed a bug where the addon was not calling the Home Assistant API to execute service calls.
- The "intelligent action dispatcher" now correctly calls the `call_homeassistant_api` function.

## Version 0.1.7
- Implemented an "intelligent action dispatcher" to reliably determine whether to call a service or get a state.
- Simplified the prompt to have only one action: `execute_task`.
- This change makes the addon more reliable by taking the burden of choosing the right action off of the AI.

## Version 0.1.6
- Added a confirmation message feature. The AI will now confirm when a task has been successfully completed.
- The AI will first acknowledge the command, then execute it, and finally confirm the new state of the device.

## Version 0.1.5
- Simplified the prompt to only use the `service` and `get_state` actions.
- Removed the `query_states` action to prevent the AI from generating complex and unsupported commands.

## Version 0.1.4
- Improved the prompt to be more explicit about the difference between the `query_states` and `service` actions.
- Added more examples to the prompt to help the AI generate the correct JSON command.

## Version 0.1.3
- The AI now uses friendly names in its responses, making them more natural and easier to understand.
- The AI is now aware of the friendly names of the devices, which helps it better understand the user's intent.
- Updated the prompt to include a mapping of `entity_id` to `friendly_name`.

## Version 0.1.2
- Added support for Home Assistant groups, allowing the AI to control and query groups of entities.
- The AI can now expand `group` entities to get the state of individual devices within them.
- Updated prompt to include examples of how to use groups in commands.

## Version 0.1.1
- Added support for controlling multiple entities in a single command (e.g., "turn on all living room lights").
- Implemented more robust validation for multi-entity commands.
- Updated prompt to teach the AI how to format requests for multiple entities.

## Version 0.1.0
- Initial release.
- Connects to Ollama and MQTT broker.
- Creates a sensor in Home Assistant for AI responses.
- Basic single-entity command and control.
