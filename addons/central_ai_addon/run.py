# /addons/central_ai_addon/run.py
print("--- ADDON SCRIPT STARTED ---")
import os
import json
import requests
import traceback
from paho.mqtt import client as mqtt_client

print("--- IMPORTS COMPLETE ---")

# --- Configuration ---
with open("/data/options.json", "r") as f:
    options = json.load(f)
print("--- CONFIG LOADED ---")

AI_ENGINE_URL = options.get("ai_engine_url", "http://localhost:8099/api/prompt")

# --- MQTT Configuration ---
MQTT_BROKER = options.get("mqtt_host")
MQTT_PORT = options.get("mqtt_port")
MQTT_USERNAME = options.get("mqtt_user")
MQTT_PASSWORD = options.get("mqtt_password")
MQTT_CLIENT_ID = f'central_ai_addon_{os.environ.get("HOSTNAME")}'

# --- MQTT Topics ---
DISCOVERY_PREFIX = "homeassistant"
COMPONENT = "sensor"
NODE_ID = "central_ai"
OBJECT_ID = "response"
DISCOVERY_TOPIC = f"{DISCOVERY_PREFIX}/{COMPONENT}/{NODE_ID}/{OBJECT_ID}/config"
STATE_TOPIC = f"{NODE_ID}/prompt/response"
COMMAND_TOPIC = f"{NODE_ID}/prompt/request"
AVAILABILITY_TOPIC = f"{NODE_ID}/availability"

print("--- GLOBAL VARS SET ---")

def on_connect(client, userdata, flags, rc, properties):
    """Callback for when the MQTT client connects."""
    if rc == 0:
        print("Successfully connected to MQTT Broker!")
        client.publish(AVAILABILITY_TOPIC, "online", retain=True)
        client.subscribe(COMMAND_TOPIC)
        print(f"Subscribed to command topic: {COMMAND_TOPIC}")
        
        # Enhanced Discovery Payload
        discovery_payload = {
            "name": "Central AI Response",
            "unique_id": "central_ai_response_sensor",
            "state_topic": STATE_TOPIC,
            "availability_topic": AVAILABILITY_TOPIC,
            "json_attributes_topic": STATE_TOPIC, # Use the same topic for attributes
            "value_template": "{{ value_json.state }}", # Extract short state
            "icon": "mdi:brain",
            "device": {
                "identifiers": ["central_ai_addon"],
                "name": "Central AI Brain",
                "model": "Ollama Integration",
                "manufacturer": "AI Project",
            },
        }
        client.publish(DISCOVERY_TOPIC, json.dumps(discovery_payload), retain=True)
        print("Published MQTT discovery message for sensor.central_ai_response")
    else:
        print(f"Failed to connect to MQTT, return code {rc}\n")

def on_message(client, userdata, msg):
    """Callback for when a message is received on the command topic."""
    print(f"Received message on topic: {msg.topic}")
    try:
        payload = json.loads(msg.payload.decode())
        prompt_text = payload.get("text")
        model_override = payload.get("model")

        # Forward the prompt to the AI Engine
        print(f"Forwarding prompt to AI Engine at {AI_ENGINE_URL}...")
        response = requests.post(
            AI_ENGINE_URL,
            json={"prompt": prompt_text, "model": model_override},
            timeout=120,  # Increased timeout for potentially long AI responses
        )
        response.raise_for_status()
        
        ai_response = response.json().get("response", "No response from AI Engine.")
        print(f"Received response from AI Engine (Length: {len(ai_response)})")

        # Construct JSON Payload to bypass 255 char limit
        # The 'state' will be short, the 'full_response' attribute will hold the text
        mqtt_payload = {
            "state": ai_response[:200] + "..." if len(ai_response) > 255 else ai_response,
            "full_response": ai_response
        }

        # Publish the JSON object
        client.publish(STATE_TOPIC, json.dumps(mqtt_payload), retain=False)

    except requests.exceptions.RequestException as e:
        print(f"Error calling AI Engine: {e}")
        error_payload = {
            "state": "Error",
            "full_response": f"Error connecting to AI Engine: {e}"
        }
        client.publish(STATE_TOPIC, json.dumps(error_payload), retain=False)
    except Exception as e:
        print(f"--- UNCAUGHT EXCEPTION IN on_message ---")
        print(f"ERROR TYPE: {type(e)}")
        print(f"ERROR: {e}")
        traceback.print_exc()
        error_payload = {
            "state": "Error",
            "full_response": "An unexpected error occurred in the AI addon."
        }
        client.publish(STATE_TOPIC, json.dumps(error_payload), retain=False)

def main():
    """Main function to set up and run the MQTT client."""
    client = mqtt_client.Client(
        mqtt_client.CallbackAPIVersion.VERSION2, client_id=MQTT_CLIENT_ID
    )
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message
    client.will_set(AVAILABILITY_TOPIC, "offline", retain=True)

    try:
        print(f"Connecting to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}...")
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_forever()
    except Exception as e:
        print(f"--- CRITICAL ERROR IN MAIN LOOP ---")
        print(f"ERROR: {e}")
        traceback.print_exc()
    finally:
        print("--- ", "SCRIPT SHUTTING DOWN", " ---")
        client.publish(AVAILABILITY_TOPIC, "offline", retain=True)
        client.disconnect()

if __name__ == "__main__":
    print("--- ", "SCRIPT INITIALIZATION COMPLETE", " ---")
    main()
