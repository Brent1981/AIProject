# /addons/central_ai_addon/run.py
print("-- ADDON SCRIPT STARTED --")
import os
import json
import requests
import time
import traceback
import pytz
import difflib
import re
from datetime import datetime

from flask import Flask, request, jsonify
from threading import Thread
import chromadb
from ddgs import DDGS
import numexpr
print("-- IMPORTS COMPLETE --")

# --- Flask App Initialization ---
app = Flask(__name__)

from dotenv import load_dotenv
load_dotenv() # Load environment variables from .env file

# --- Configuration ---
OLLAMA_URL = os.environ.get("OLLAMA_URL")
DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "llama3")
CUSTOM_MODEL = os.environ.get("CUSTOM_MODEL", "")
CHROMADB_URL = os.environ.get("CHROMADB_URL")
HA_API_TOKEN = os.environ.get("HA_API_TOKEN")
HA_API_URL = os.environ.get("HA_API_URL", "http://homeassistant.local:8123/api")
DOMAIN_MAPPINGS = json.loads(os.environ.get("DOMAIN_MAPPINGS", "[]"))
print("-- CONFIG LOADED --")
CONVERSATION_HISTORY = []
MAX_HISTORY = 10
AREA_CACHE = {}
AREA_CACHE_EXPIRATION = 300  # 5 minutes
LAST_CACHE_UPDATE = 0
LAST_ENTITY_CONTEXT = {}

# --- ChromaDB Client Initialization ---
chroma_client = None
memory_collection = None
if CHROMADB_URL:
    try:
        print(f"Connecting to ChromaDB at {CHROMADB_URL}...")
        # The host and port are extracted from the URL for the client.
        host, port = CHROMADB_URL.replace('http://', '').split(':')
        chroma_client = chromadb.HttpClient(host=host, port=port)
        # Using a default embedding model. This will be downloaded on first use.
        memory_collection = chroma_client.get_or_create_collection(
            name="long_term_memory",
            metadata={"hnsw:space": "cosine"} # Using cosine distance for similarity
        )
        print("Successfully connected to ChromaDB and got/created collection.")
    except Exception as e:
        print(f"-- FAILED TO CONNECT TO CHROMADB: {e} --")
        print("-- Long-term memory will be disabled. --")
else:
    print("-- No chromadb_url configured. Long-term memory will be disabled. --")

print("-- GLOBAL VARS SET --")

# --- Dynamic Prompt Template ---
PROMPT_TEMPLATE = (
    "You are AXIOM, a highly intelligent AI assistant designed to manage a smart home. Your demeanor is formal, yet you possess a sharp wit and a subtle sarcastic edge. Your primary function is to precisely translate a user's request into one or more JSON commands. Your ONLY output should be the correct JSON for the action(s) the user intends. If a request necessitates multiple actions, return a JSON array of commands.\n\n"
    "## CONTEXT ##\n"
    "1.  **Relevant Memories:**\n{memories}\n"
    "2.  **Available Devices:**\n{entities}\n"
    "3.  **Available Areas:**\n{areas}\n\n"
    "## AVAILABLE ACTIONS ##\n"
    "You can choose between three actions: `execute_task` for controlling home devices, `web_search` for finding information on the internet, or `calculator` for solving math problems.\n\n"
    "## EXAMPLES ##\n"
    "User's Request: \"Turn on the living room floor lamp\"\n"
    "JSON Output:\n"
    "```json\n"
    "{{\n"
    "  \"action\": \"execute_task\",\n"
    "  \"service\": \"light.turn_on\",\n"
    "  \"entity_id\": \"light.house_living_room_floor_left\"\n"
    "}}\n"
    "```\n\n"
    "User's Request: \"Set the bedroom light to 50% and turn on the fan.\"\n"
    "JSON Output:\n"
    "```json\n"
    "[\n"
    "  {{\n"
    "    \"action\": \"execute_task\",\n"
    "    \"service\": \"light.turn_on\",\n"
    "    \"entity_id\": \"light.house_master_bedroom_ceiling\",\n"
    "    \"parameters\": {{\n"
    "      \"brightness_pct\": 50\n"
    "    }}\n"
    "  }},\n"
    "  {{\n"
    "    \"action\": \"execute_task\",\n"
    "    \"service\": \"fan.turn_on\",\n"
    "    \"entity_id\": \"fan.house_master_bedroom_ceiling\"\n"
    "  }}\n"
    "]\n"
    "```\n\n"
    "User's Request: \"Who was the first president of the United States?\"\n"
    "JSON Output:\n"
    "```json\n"
    "{{\n"
    "  \"action\": \"web_search\",\n"
    "  \"query\": \"first president of the United States\"\n"
    "}}\n"
    "```\n\n"
    "User's Request: \"What is 27 * 14?\"\n"
    "JSON Output:\n"
    "```json\n"
    "{{\n"
    "  \"action\": \"calculator\",\n"
    "  \"expression\": \"27 * 14\"\n"
    "}}\n"
    "```\n\n"
    "## YOUR TASK ##\n"
    "User's Request: \"{prompt}\"\n"
    "JSON Output:\n"
)

# --- Answer Prompt Template ---
ANSWER_PROMPT_TEMPLATE = (
    "You are a helpful AI assistant for a smart home.\n"
    "Here is the recent conversation history:\n{history}\n"
    "Here is some relevant long-term memory that might help:\n{memories}\n\n"
    "Your task is to answer a user's question based on the data provided.\n"
    "- The user's original question was: \"{prompt}\"\n"
    "- The current data for the relevant device(s) is: {state}\n\n"
    "Please provide a concise, natural language answer to the user's question. Where possible, use the 'friendly_name' of the devices in your answer.\n"
    "ASSISTANT:\n"
)

# --- Web Search Answer Prompt Template ---
WEB_SEARCH_ANSWER_PROMPT_TEMPLATE = (
    "You are a helpful AI assistant. Your task is to answer a user's question based on the provided web search results.\n"
    "- The user's original question was: \"{prompt}\"\n"
    "- Here are the relevant search results:\n{search_results}\n\n"
    "Please synthesize the information from the search results into a concise, natural language answer.\n"
    "ASSISTANT:\n"
)

# --- Calculator Answer Prompt Template ---
CALCULATOR_ANSWER_PROMPT_TEMPLATE = (
    "You are a helpful AI assistant. Your task is to answer a user's question based on a calculation.\n"
    "- The user's original question was: \"{prompt}\"\n"
    "- The result of the calculation is: {result}\n\n"
    "Please provide the answer in a concise, natural language format.\n"
    "ASSISTANT:\n"
)


# --- Confirmation Prompt Template ---
CONFIRMATION_PROMPT_TEMPLATE = (
    "You are a helpful AI assistant for a smart home.\n"
    "Here is the recent conversation history:\n{history}\n"
    "Your task is to confirm that an action was successfully completed.\n"
    "- The user's original request was: \"{prompt}\"\n"
    "- The action taken was: `{service}` on `{entity_id}`\n"
    "- The current state of the device is now: {state}\n\n"
    "Please provide a concise, natural language confirmation message.\n"
    "ASSISTANT:\n"
)

# --- Answer Temp Prompt Template ---
ANSWER_TEMP_PROMPT_TEMPLATE = (
    "You are a helpful AI assistant for a smart home.\n"
    "Your task is to answer a user's question about the average temperature.\n"
    "- The user's original question was: \"{prompt}\"\n"
    "- The calculated average temperature of the house is: {avg_temp}°\n\n"
    "Please provide a concise, natural language answer to the user's question.\n"
    "ASSISTANT:\n"
)




def store_memory(text):
    """Stores a piece of text in the ChromaDB long-term memory."""
    if not memory_collection:
        print("Cannot store memory, ChromaDB client not available.")
        return "Memory is not available."
    try:
        # We use the text itself as the document and a timestamped ID.
        doc_id = f"memory_{int(time.time())}"
        memory_collection.add(
            documents=[text],
            ids=[doc_id]
        )
        print(f"Successfully stored memory: '{text}'")
        return f"Okay, I've remembered that: {text}"
    except Exception as e:
        print(f"Error storing memory in ChromaDB: {e}")
        return "I had trouble remembering that."

def retrieve_memories(text, n_results=3):
    """Retrieves the most relevant memories from ChromaDB."""
    if not memory_collection:
        print("Cannot retrieve memories, ChromaDB client not available.")
        return "No memories found."
    try:
        results = memory_collection.query(
            query_texts=[text],
            n_results=n_results
        )
        documents = results.get('documents')
        if documents and documents[0]:
            # Return a formatted string of the top results.
            retrieved = "\n".join([f"- {doc}" for doc in documents[0]])
            print(f"Retrieved memories for prompt '{text}':\n{retrieved}")
            return retrieved
        else:
            return "No relevant memories found."
    except Exception as e:
        print(f"Error retrieving memories from ChromaDB: {e}")
        return "I had trouble accessing my memory."


def call_ollama(prompt, model):
    """Sends a prompt to the Ollama API and returns the response."""
    print(f"Querying Ollama with model '{model}'...")
    print(f"-- OLLAMA PROMPT --\n{prompt}\n-- END OLLAMA PROMPT --")
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=60,
        )
        response.raise_for_status()
        print("Successfully received response from Ollama.")
        return response.json().get("response", "No response field found in Ollama reply.")
    except requests.exceptions.RequestException as e:
        print(f"Error calling Ollama API: {e}")
        return f"Error: Could not connect to Ollama at {OLLAMA_URL}."

def expand_ha_groups(entity_ids, all_states):
    """Expands any group entities to their member entities."""
    expanded_entities = set()
    entities_to_check = entity_ids if isinstance(entity_ids, list) else [entity_ids]

    for entity_id in entities_to_check:
        if entity_id.startswith("group."):
            group_state = next(
                (s for s in all_states if s["entity_id"] == entity_id), None
            )
            if group_state and "entity_id" in group_state.get("attributes", {}):
                # Recursively expand if a group contains other groups
                member_entities = group_state["attributes"]["entity_id"]
                expanded_entities.update(expand_ha_groups(member_entities, all_states))
            else:
                expanded_entities.add(entity_id)  # Keep group if not expandable
        else:
            expanded_entities.add(entity_id)

    return list(expanded_entities)

def call_homeassistant_api(service, entity_id, parameters=None):
    """Calls a Home Assistant service."""
    if not HA_API_TOKEN:
        print("SUPERVISOR_TOKEN not found. Cannot call Home Assistant API.")
        return "Error: Addon is not configured with API access."
    
    if not service or '.' not in service:
        return f"Error: Invalid service format '{service}'. Expected 'domain.action'."

    headers = {
        "Authorization": f"Bearer {HA_API_TOKEN}",
        "Content-Type": "application/json",
    }
    domain, action = service.split(".")
    payload = {"entity_id": entity_id}
    if parameters:
        payload.update(parameters)
    url = f"{HA_API_URL}/services/{domain}/{action}"
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        print("Successfully called Home Assistant service.")
        return f"Successfully executed {service} on {entity_id}."
    except requests.exceptions.RequestException as e:
        print(f"Error calling Home Assistant API: {e}")
        return f"Error: Could not call service {service}. Details: {e}"

def get_ha_states():
    """Fetches all states from Home Assistant in a single API call."""
    if not HA_API_TOKEN:
        print("SUPERVISOR_TOKEN not found. Cannot fetch entities.")
        return []
    headers = {"Authorization": f"Bearer {HA_API_TOKEN}"}
    try:
        print("Fetching all states from Home Assistant...")
        response = requests.get(f"{HA_API_URL}/states", headers=headers, timeout=10)
        response.raise_for_status()
        print("Successfully fetched all states.")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching states from Home Assistant: {e}")
        return []

def get_ha_area_data():
    """Fetches a mapping of areas to their entities from Home Assistant."""
    if not HA_API_TOKEN:
        print("SUPERVISOR_TOKEN not found. Cannot fetch area data.")
        return {}

    headers = {
        "Authorization": f"Bearer {HA_API_TOKEN}",
        "Content-Type": "application/json",
    }
    
    template = """
    {% set ns = namespace(areas={}) %}
    {% for entity in states %}
      {% set area = area_name(entity.entity_id) %}
      {% if area %}
        {% if area not in ns.areas %}
          {% set ns.areas = ns.areas | combine({area: []}) %}
        {% endif %}
        {% set entity_info = {'entity_id': entity.entity_id, 'friendly_name': entity.attributes.friendly_name} %}
        {% set ns.areas = ns.areas | combine({area: ns.areas[area] + [entity_info]}) %}
      {% endif %}
    {% endfor %}
    {{ ns.areas | tojson }}
    """
    
    payload = {"template": template}
    url = f"{HA_API_URL}/template"
    
    try:
        print("Fetching area data from Home Assistant...")
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        # The response from the template is a string, so we need to parse it as JSON
        area_data_str = response.text
        print("Successfully fetched area data.")
        return json.loads(area_data_str)
    except requests.exceptions.RequestException as e:
        print(f"Error fetching area data from Home Assistant: {e}")
        return {}
    except json.JSONDecodeError as e:
        print(f"Error parsing area data JSON from Home Assistant: {e}")
        return {}

def get_average_temperature(all_states):
    """
    Finds all temperature sensors, calculates the average, and returns it.
    """
    temp_sensors = []
    for entity in all_states:
        if entity['entity_id'].startswith('sensor.'):
            attributes = entity.get('attributes', {})
            if attributes.get('device_class') == 'temperature':
                try:
                    temp = float(entity['state'])
                    temp_sensors.append(temp)
                except (ValueError, TypeError):
                    # State is not a valid number (e.g., 'unknown'), so we skip it
                    print(f"Could not parse temperature for {entity['entity_id']}: state is '{entity['state']}'")
                    pass
    
    if not temp_sensors:
        return None

    average_temp = sum(temp_sensors) / len(temp_sensors)
    return round(average_temp, 1)

def get_ha_timezone():
    """Fetches the timezone from Home Assistant configuration."""
    if not HA_API_TOKEN:
        print("SUPERVISOR_TOKEN not found. Cannot fetch timezone.")
        return "UTC"  # Default to UTC if token is missing
    headers = {"Authorization": f"Bearer {HA_API_TOKEN}"}
    try:
        print("Fetching timezone from Home Assistant...")
        response = requests.get(f"{HA_API_URL}/config", headers=headers, timeout=10)
        response.raise_for_status()
        config_data = response.json()
        tz = config_data.get("time_zone", "UTC")
        print(f"Successfully fetched timezone: {tz}")
        return tz
    except requests.exceptions.RequestException as e:
        print(f"Error fetching timezone from Home Assistant: {e}. Defaulting to UTC.")
        return "UTC"

def get_entity_history(entity_id):
    """Fetches the history of a specific entity for the last 24 hours."""
    if not HA_API_TOKEN:
        print("SUPERVISOR_TOKEN not found. Cannot fetch history.")
        return "Error: Addon is not configured with API access."

    headers = {
        "Authorization": f"Bearer {HA_API_TOKEN}",
        "Content-Type": "application/json",
    }
    # Get timestamp for 24 hours ago
    start_time = time.time() - 24 * 3600
    start_time_iso = datetime.fromtimestamp(start_time).isoformat()

    url = f"{HA_API_URL}/history/period/{start_time_iso}?filter_entity_id={entity_id}"
    print(f"Fetching history for {entity_id}...")

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        history_data = response.json()
        if not history_data or not history_data[0]:
            return f"No history found for {entity_id} in the last 24 hours."

        return history_data[0]  # Return the list of events

    except requests.exceptions.RequestException as e:
        print(f"Error fetching history from Home Assistant: {e}")
        return f"Error: Could not fetch history for {entity_id}. Details: {e}"


# --- History Answer Prompt Template ---
HISTORY_ANSWER_PROMPT_TEMPLATE = (
    "You are a helpful AI assistant for a smart home.\n"
    "Your task is to answer a user's question based on the historical data provided.\n"
    "- The user's original question was: \"{prompt}\"\n"
    "- Here is the recent history for the relevant device(s): {history}\n\n"
    "Please analyze the history and provide a concise, natural language answer to the user's question. Refer to specific times if possible.\n"
    "ASSISTANT:\n"
)


def prettify_history(history_data, entity_id, all_states, local_tz_str):
    """Formats raw history data into a human-readable string with correct timezone and semantics."""
    if isinstance(history_data, str):
        return history_data  # Return error messages as is

    try:
        local_tz = pytz.timezone(local_tz_str)
    except pytz.UnknownTimeZoneError:
        print(f"Unknown timezone '{local_tz_str}'. Defaulting to UTC.")
        local_tz = pytz.utc

    # Get the entity's attributes for semantic context
    entity_state = next((s for s in all_states if s["entity_id"] == entity_id), None)
    attributes = entity_state.get("attributes", {}) if entity_state else {}
    device_class = attributes.get("device_class")
    domain = entity_id.split('.')[0]

    pretty_string = ""
    for event in history_data:
        try:
            state = event.get("state")
            last_changed_str = event.get("last_changed")
            if not last_changed_str:
                continue

            utc_dt = datetime.fromisoformat(last_changed_str)
            local_dt = utc_dt.astimezone(local_tz)
            timestamp = local_dt.strftime("%I:%M %p on %B %d")

            # Generate semantic description
            description = f"changed to '{state}'" # Default
            if domain in ['light', 'switch', 'fan', 'input_boolean']:
                description = f"was turned {state}"
            elif domain == 'binary_sensor':
                if device_class in ['door', 'window', 'garage_door']:
                    description = f"was {'opened' if state == 'on' else 'closed'}"
                elif device_class in ['motion', 'occupancy']:
                    description = f"{ 'motion was detected' if state == 'on' else 'motion cleared' }"
                elif device_class == 'lock':
                    description = f"was {'unlocked' if state == 'on' else 'locked'}"
                else:
                    description = f"turned {state}"
            elif domain == 'lock':
                 description = f"was {'unlocked' if state == 'unlocked' else 'locked'}"
            elif domain == 'cover':
                 description = f"was {state}"


            pretty_string += f"- At {timestamp}, it {description}.\n"
        except (ValueError, TypeError):
            continue

    return pretty_string if pretty_string else "No valid history events to display."

def prettify_states(states):
    """Cleans up HA state objects for better AI comprehension."""
    if not isinstance(states, list):
        states = [states]

    pretty_states = []
    for state_obj in states:
        if not state_obj:
            continue

        pretty_attributes = {}
        attributes = state_obj.get("attributes", {})

        if "brightness" in attributes:
            try:
                brightness_val = int(attributes["brightness"])
                percent = round((brightness_val / 255) * 100)
                pretty_attributes["brightness"] = f"{percent}%"
            except (ValueError, TypeError):
                pass

        if "temperature" in attributes:
            pretty_attributes["temperature"] = f"{attributes['temperature']}°"
        if "current_temperature" in attributes:
            pretty_attributes["current_temperature"] = (
                f"{attributes['current_temperature']}°"
            )

        if "friendly_name" in attributes:
            pretty_attributes["friendly_name"] = attributes["friendly_name"]

        pretty_states.append(
            {
                "entity_id": state_obj.get("entity_id"),
                "state": state_obj.get("state"),
                "attributes": pretty_attributes,
            }
        )

    if not pretty_states:
        return None
    return pretty_states if len(pretty_states) > 1 else pretty_states[0]

def find_best_matching_entity(prompt_text, all_entities, target_text=None):
    """
    Finds the best entity match.
    - If target_text is provided, it uses fuzzy string matching for self-correction.
    - Otherwise, it uses a keyword scoring algorithm to extract an entity from a prompt.
    Returns a tuple of (best_match_entity_id, score).
    """
    # --- Self-Correction Mode ---
    if target_text:
        text_to_match = target_text
        search_candidates = list(all_entities.keys()) + list(all_entities.values())
        close_matches = difflib.get_close_matches(text_to_match, search_candidates, n=1, cutoff=0.6)
        
        if close_matches:
            match = close_matches[0]
            # If the match is a friendly name, find its corresponding entity_id
            if match in all_entities.values():
                for entity_id, friendly_name in all_entities.items():
                    if friendly_name == match:
                        # In self-correction, we are confident, so return a high score.
                        return entity_id, 10
            else: # The match is an entity_id
                return match, 10
        # Fallback for self-correction: try the original prompt with keyword search
        return find_best_matching_entity(prompt_text, all_entities, target_text=None)

    # --- Entity Extraction Mode ---
    else:
        # Clean up the prompt to get relevant keywords
        stop_words = {"what", "is", "the", "tell", "me", "about", "when", "was", "how", "long", "history", "of", "a", "an", "last", "on", "off", "open", "closed", "set", "to", "in", "were", "status", "current"}
        prompt_words = set(
            [word for word in prompt_text.lower().replace("?", "").split() if word not in stop_words]
        )

        if not prompt_words:
            return None, 0

        best_match = None
        highest_score = 0

        # --- Domain Keyword Bonus ---
        domain_keywords = {"light": "light", "lights": "light", "switch": "switch", "fan": "fan", "sensor": "sensor", "lock": "lock", "cover": "cover", "climate": "climate"}
        detected_domain = None
        for keyword, domain in domain_keywords.items():
            if keyword in prompt_words:
                detected_domain = domain
                break

        for entity_id, friendly_name in all_entities.items():
            friendly_name_lower = friendly_name.lower()
            entity_id_lower = entity_id.lower()
            
            score = 0
            
            # Score based on matching words from the prompt
            fn_words = set(friendly_name_lower.split())
            eid_words = set(entity_id_lower.replace('.', ' ').replace('_', ' ').split())

            score += len(prompt_words.intersection(fn_words)) * 3
            score += len(prompt_words.intersection(eid_words)) * 1

            # Bonus for matching all words of the friendly name
            if fn_words.issubset(prompt_words):
                score += 10

            # Apply domain bonus
            if detected_domain and entity_id.startswith(detected_domain + "."):
                score += 15

            if score > highest_score:
                highest_score = score
                best_match = entity_id
        
        # Only return a match if the score is above a certain threshold
        if highest_score > 5: # Increased threshold because of domain bonus
             return best_match, highest_score
        else:
             return None, 0

def extract_json_commands(text):
    """Extracts the first valid JSON object or array from a string."""
    # Regex to find JSON in a markdown code block, non-greedy
    match = re.search(r"```(json)?\s*([\s\S]*?)\s*```", text)
    if match:
        code_block = match.group(2)
        try:
            parsed_json = json.loads(code_block)
            if isinstance(parsed_json, list):
                return parsed_json
            elif isinstance(parsed_json, dict):
                return [parsed_json]
        except json.JSONDecodeError:
            # If parsing the first block fails, don't proceed to other fallbacks
            # as the AI's intent was likely in this block.
            return []

    # Fallback for text that is just a JSON object/array without markdown
    try:
        parsed_json = json.loads(text)
        if isinstance(parsed_json, list):
            return parsed_json
        elif isinstance(parsed_json, dict):
            return [parsed_json]
    except json.JSONDecodeError:
        pass

    # Fallback to find the first { or [ and its matching } or ]
    # This is a last resort and can be unreliable.
    try:
        first_brace = text.find('{')
        first_bracket = text.find('[')

        start_index = -1
        if first_brace != -1 and first_bracket != -1:
            start_index = min(first_brace, first_bracket)
        elif first_brace != -1:
            start_index = first_brace
        else:
            start_index = first_bracket

        if start_index == -1:
            return []

        json_str = text[start_index:]
        parsed_json = json.loads(json_str)
        if isinstance(parsed_json, list):
            return parsed_json
        elif isinstance(parsed_json, dict):
            return [parsed_json]
    except (json.JSONDecodeError, IndexError):
        pass

    return []

def find_best_matching_area(prompt_text, area_data):
    """Finds the best matching area from the prompt."""
    prompt_words = set(prompt_text.lower().split())
    best_match = None
    highest_score = 0

    for area_name in area_data.keys():
        area_name_words = set(area_name.lower().split())
        score = len(prompt_words.intersection(area_name_words))
        if score > highest_score:
            highest_score = score
            best_match = area_name
    
    return best_match

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

def process_prompt(prompt_text, model_override=None):
    """Handles the core logic of processing a prompt and returning a response."""
    global CONVERSATION_HISTORY, AREA_CACHE, LAST_CACHE_UPDATE, LAST_ENTITY_CONTEXT
    try:
        # --- Contextual Pronoun Replacement ---
        # (This logic can be simplified or removed if the LLM handles context well)
        # ...

        if not prompt_text or not prompt_text.strip():
            return "Error: Prompt cannot be empty."

        CONVERSATION_HISTORY.append({"role": "user", "content": prompt_text})
        if len(CONVERSATION_HISTORY) > MAX_HISTORY:
            CONVERSATION_HISTORY = CONVERSATION_HISTORY[-MAX_HISTORY:]

        # --- Single entry point for all actions ---
        model_to_use = model_override or CUSTOM_MODEL or DEFAULT_MODEL
        
        # --- Get Context for the LLM ---
        retrieved_memories = retrieve_memories(prompt_text)
        all_states = get_ha_states()
        if not all_states:
            return "Error: Could not get device list."
        all_entities = {s["entity_id"]: s["attributes"].get("friendly_name", s["entity_id"]) for s in all_states}
        
        current_time = time.time()
        if not AREA_CACHE or (current_time - LAST_CACHE_UPDATE > AREA_CACHE_EXPIRATION):
            AREA_CACHE = get_ha_area_data()
            LAST_CACHE_UPDATE = current_time
        
        entities_str = json.dumps(all_entities, indent=2)
        areas_str = json.dumps(AREA_CACHE, indent=2)

        # --- Let the LLM decide the action ---
        tool_prompt = PROMPT_TEMPLATE.format(
            prompt=prompt_text, 
            entities=entities_str, 
            areas=areas_str,
            memories=retrieved_memories
        )
        ollama_response = call_ollama(tool_prompt, model_to_use)
        print(f"-- OLLAMA RAW RESPONSE --\n{ollama_response}\n-- END OLLAMA RAW RESPONSE --")
        generated_commands = extract_json_commands(ollama_response)

        if not generated_commands:
            # If the LLM fails to generate a command, try to answer directly
            print("LLM failed to generate a command. Attempting to answer directly.")
            return call_ollama(f"You are a helpful assistant. Answer the following question: {prompt_text}", model_to_use)

        # --- Execute Generated Commands ---
        successful_actions = []
        failed_actions = []
        acted_upon_entities = []

        for command_data in generated_commands:
            try:
                action = command_data.get("action")
                if not action:
                    raise ValueError("Action not found in command.")

                if action == "web_search":
                    query = command_data.get("query")
                    if not query: raise ValueError("Web search action requires a query.")
                    search_result = handle_web_search(query, model_to_use)
                    successful_actions.append(search_result)
                
                elif action == "calculator":
                    expression = command_data.get("expression")
                    if not expression: raise ValueError("Calculator action requires an expression.")
                    calc_result = perform_calculation(expression)
                    
                    answer_prompt = CALCULATOR_ANSWER_PROMPT_TEMPLATE.format(prompt=prompt_text, result=calc_result)
                    final_answer = call_ollama(answer_prompt, model_to_use)
                    successful_actions.append(final_answer.strip())

                elif action == "execute_task":
                    entity_id = command_data.get("entity_id")
                    service = command_data.get("service")
                    if not service: raise ValueError("Service not found in command.")

                    if entity_id:
                        acted_upon_entities.append(entity_id)

                    if entity_id not in all_entities:
                        print(f"AI returned an invalid entity_id: '{entity_id}'. Attempting to self-correct.")
                        corrected_entity_id, _ = find_best_matching_entity(prompt_text, all_entities, target_text=entity_id)
                        if corrected_entity_id:
                            print(f"Self-correction successful. Found matching entity: '{corrected_entity_id}'")
                            # (Self-correction logic for service can be added here if needed)
                            entity_id = corrected_entity_id
                        else:
                            print(f"Self-correction failed for '{entity_id}'.")
                            failed_actions.append(f"could not find a matching device for '{entity_id}'")
                            continue
                    
                    expanded_entity_ids = expand_ha_groups(entity_id, all_states)
                    call_homeassistant_api(service, expanded_entity_ids, command_data.get("parameters"))

                    entity_friendly_name = all_entities.get(entity_id, entity_id)
                    service_action_friendly = service.split('.')[-1].replace('_', ' ')
                    successful_actions.append(f"executed {service_action_friendly} on the {entity_friendly_name}")

                else:
                    raise ValueError(f"Unknown action '{action}' in command.")

            except Exception as e:
                print(f"Error processing command: {e}")
                failed_actions.append(f"failed to execute a command due to: {e}")
                continue
        
        if acted_upon_entities:
            LAST_ENTITY_CONTEXT = {"entity_id": acted_upon_entities, "timestamp": time.time()}

        # --- Summarize Results ---
        if len(successful_actions) == 1 and action in ["web_search", "calculator"]:
             # For tool use that generates its own answer, just return that answer.
             final_summary_message = successful_actions[0]
        else:
            # For HA tasks or multiple actions, create a summary.
            final_summary_message = ""
            if successful_actions:
                final_summary_message = "Okay, I've " + ", and ".join(successful_actions) + "."
            if failed_actions:
                final_summary_message += " However, I " + ", and ".join(failed_actions) + "."
        
        if not final_summary_message:
            final_summary_message = "I wasn't able to complete that request."

        CONVERSATION_HISTORY.append({"role": "assistant", "content": final_summary_message})
        return final_summary_message

    except Exception as e:
        print(f"-- !!! UNCAUGHT EXCEPTION IN process_prompt !!! --")
        print(f"ERROR TYPE: {type(e)}")
        print(f"ERROR: {e}")
        traceback.print_exc()
        return f"An unexpected error occurred: {e}"



@app.route('/api/prompt', methods=['POST'])
def api_prompt():
    """API endpoint to receive prompts."""
    print("Received request on /api/prompt endpoint.")
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    prompt_text = data.get("prompt")
    model_override = data.get("model")

    if not prompt_text:
        return jsonify({"error": "Missing 'prompt' in request body"}), 400

    response_message = process_prompt(prompt_text, model_override)
    
    return jsonify({"response": response_message})

@app.route('/healthz', methods=['GET'])
def healthz():
    """Health check endpoint."""
    return "OK", 200

def run_flask_app():
    """Runs the Flask web server."""
    # Note: The port is hardcoded to 8099, which is the default for addons.
    # The port mapping will be configured in config.yaml.
    print("Starting Flask web server on port 8099...")
    app.run(host='0.0.0.0', port=8099)

def main():
    """Main function to run the Flask app."""
    run_flask_app()

if __name__ == "__main__":
    print("--", "SCRIPT INITIALIZATION COMPLETE", "--")
    main()
