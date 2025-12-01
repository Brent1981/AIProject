# ai_engine/app.py
import os
import json
import time
import traceback

from flask import Flask, request, jsonify
from dotenv import load_dotenv

import chromadb

from lib.ha_helpers import *
from lib.prompts import *
from lib.chroma_helpers import *
from lib.ollama_helpers import *
from lib.tool_helpers import *
from lib.utils import *

print("-- IMPORTS COMPLETE --")

# --- Flask App Initialization ---
app = Flask(__name__)

class AIEngine:
    def __init__(self):
        load_dotenv()
        self.ollama_url = os.environ.get("OLLAMA_URL")
        self.default_model = os.environ.get("DEFAULT_MODEL", "llama3")
        self.custom_model = os.environ.get("CUSTOM_MODEL", "")
        self.chromadb_url = os.environ.get("CHROMADB_URL")
        self.ha_api_token = os.environ.get("HA_API_TOKEN")
        self.ha_api_url = os.environ.get("HA_API_URL", "http://homeassistant.local:8123/api")
        self.domain_mappings = json.loads(os.environ.get("DOMAIN_MAPPINGS", "[]"))
        print("-- CONFIG LOADED --")

        self.conversation_history = []
        self.max_history = 10
        self.area_cache = {}
        self.area_cache_expiration = 300  # 5 minutes
        self.last_cache_update = 0
        self.last_entity_context = {}

        self.chroma_client = None
        self.memory_collection = None
        if self.chromadb_url:
            try:
                print(f"Connecting to ChromaDB at {self.chromadb_url}...")
                host, port = self.chromadb_url.replace('http://', '').split(':')
                self.chroma_client = chromadb.HttpClient(host=host, port=port)
                self.memory_collection = self.chroma_client.get_or_create_collection(
                    name="long_term_memory",
                    metadata={"hnsw:space": "cosine"}
                )
                print("Successfully connected to ChromaDB and got/created collection.")
            except Exception as e:
                print(f"-- FAILED TO CONNECT TO CHROMADB: {e} --")
                print("-- Long-term memory will be disabled. --")
        else:
            print("-- No chromadb_url configured. Long-term memory will be disabled. --")

        print("-- AI ENGINE INITIALIZED --")

    def process_prompt(self, prompt_text, model_override=None):
        """Handles the core logic of processing a prompt and returning a response."""
        try:
            if not prompt_text or not prompt_text.strip():
                return "Error: Prompt cannot be empty."

            self.conversation_history.append({"role": "user", "content": prompt_text})
            if len(self.conversation_history) > self.max_history:
                self.conversation_history = self.conversation_history[-self.max_history:]

            model_to_use = model_override or self.custom_model or self.default_model

            retrieved_memories = retrieve_memories(self.memory_collection, prompt_text)
            all_states = get_ha_states()
            if not all_states:
                return "Error: Could not get device list."
            all_entities = {s["entity_id"]: s["attributes"].get("friendly_name", s["entity_id"]) for s in all_states}
            
            current_time = time.time()
            if not self.area_cache or (current_time - self.last_cache_update > self.area_cache_expiration):
                self.area_cache = get_ha_area_data()
                self.last_cache_update = current_time
            
            entities_str = json.dumps(all_entities, indent=2)
            areas_str = json.dumps(self.area_cache, indent=2)

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
                print("LLM failed to generate a command. Attempting to answer directly.")
                return call_ollama(f"You are a helpful assistant. Answer the following question: {prompt_text}", model_to_use)

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
                self.last_entity_context = {"entity_id": acted_upon_entities, "timestamp": time.time()}

            if len(successful_actions) == 1 and action in ["web_search", "calculator"]:
                 final_summary_message = successful_actions[0]
            else:
                final_summary_message = ""
                if successful_actions:
                    final_summary_message = "Okay, I've " + ", and ".join(successful_actions) + "."
                if failed_actions:
                    final_summary_message += " However, I " + ", and ".join(failed_actions) + "."
            
            if not final_summary_message:
                final_summary_message = "I wasn't able to complete that request."

            self.conversation_history.append({"role": "assistant", "content": final_summary_message})
            return final_summary_message

        except Exception as e:
            print(f"-- !!! UNCAUGHT EXCEPTION IN process_prompt !!! --")
            print(f"ERROR TYPE: {type(e)}")
            print(f"ERROR: {e}")
            traceback.print_exc()
            return f"An unexpected error occurred: {e}"

# --- Create a single AIEngine instance ---
ai_engine = AIEngine()

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

    response_message = ai_engine.process_prompt(prompt_text, model_override)
    
    return jsonify({"response": response_message})

@app.route('/healthz', methods=['GET'])
def healthz():
    """Health check endpoint."""
    return "OK", 200

def main():
    """Main function to run the Flask app."""
    # The default Flask server is not suitable for production.
    # Use a production-ready WSGI server like Gunicorn or uWSGI.
    # The Dockerfile uses Gunicorn.
    print("Starting Flask web server for development...")
    app.run(host='0.0.0.0', port=5000)

if __name__ == "__main__":
    main()
