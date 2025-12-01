# ai_engine/lib/utils.py
import json
import re
import difflib

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
