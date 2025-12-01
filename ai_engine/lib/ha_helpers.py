# ai_engine/lib/ha_helpers.py
import os
import json
import requests
import time
from datetime import datetime
import pytz

HA_API_TOKEN = os.environ.get("HA_API_TOKEN")
HA_API_URL = os.environ.get("HA_API_URL", "http://homeassistant.local:8123/api")

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
