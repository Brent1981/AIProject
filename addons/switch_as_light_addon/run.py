import json
import logging
import os
import time

import paho.mqtt.client as mqtt
import requests

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=log_level, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Load configuration from Home Assistant
with open("/data/options.json") as f:
    config = json.load(f)

HA_URL = config["ha_url"]
HA_TOKEN = config["ha_token"]
MQTT_HOST = config["mqtt_host"]
MQTT_PORT = config["mqtt_port"]
MQTT_USER = config["mqtt_user"]
MQTT_PASSWORD = config["mqtt_password"]

HEADERS = {
    "Authorization": f"Bearer {HA_TOKEN}",
    "content-type": "application/json",
}

def get_ha_entities():
    """Get all entities from Home Assistant."""
    try:
        response = requests.get(f"{HA_URL}/api/states", headers=HEADERS)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error getting entities from Home Assistant: {e}")
        return None

def on_connect(client, userdata, flags, rc):
    """Callback for when the client connects to the MQTT broker."""
    if rc == 0:
        logging.info("Connected to MQTT broker")
        client.subscribe("homeassistant/light/+/+/set")
    else:
        logging.error(f"Failed to connect to MQTT broker with result code {rc}")

def on_message(client, userdata, msg):
    """Callback for when a message is received from the MQTT broker."""
    try:
        topic_parts = msg.topic.split("/")
        entity_id = topic_parts[2]
        payload = msg.payload.decode()

        logging.info(f"Received message on topic {msg.topic}: {payload}")

        # Call the appropriate Home Assistant service
        domain = "switch"
        service = "turn_on" if payload == "ON" else "turn_off"
        service_url = f"{HA_URL}/api/services/{domain}/{service}"
        service_data = {"entity_id": f"{domain}.{entity_id}"}

        response = requests.post(service_url, headers=HEADERS, json=service_data)
        response.raise_for_status()

        # Immediately update the light's state
        new_state = "on" if payload == "ON" else "off"
        client.publish(f"homeassistant/light/{entity_id}/state", new_state.upper(), retain=True)

    except Exception as e:
        logging.error(f"Error processing MQTT message: {e}")


def main():
    """Main function to run the add-on."""
    # Set up MQTT client
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_start()

    # Discover switches and create lights
    entities = get_ha_entities()
    if entities:
        for entity in entities:
            if entity["entity_id"].startswith("switch."):
                entity_id = entity["entity_id"].split(".")[1]
                friendly_name = entity["attributes"].get("friendly_name", entity_id)

                # MQTT discovery payload
                discovery_topic = f"homeassistant/light/{entity_id}/config"
                discovery_payload = {
                    "name": friendly_name,
                    "unique_id": f"switch_as_light_{entity_id}",
                    "command_topic": f"homeassistant/light/{entity_id}/set",
                    "state_topic": f"homeassistant/light/{entity_id}/state",
                    "schema": "basic",
                }

                # Publish discovery message
                client.publish(discovery_topic, json.dumps(discovery_payload), retain=True)
                logging.info(f"Published discovery message for {entity['entity_id']}")

                # Publish initial state
                initial_state = entity["state"].upper()
                client.publish(f"homeassistant/light/{entity_id}/state", initial_state, retain=True)


    # Keep the script running and listen for Home Assistant state changes
    while True:
        time.sleep(10)
        # Periodically re-sync states
        entities = get_ha_entities()
        if entities:
            for entity in entities:
                if entity["entity_id"].startswith("switch."):
                    entity_id = entity["entity_id"].split(".")[1]
                    state = entity["state"].upper()
                    client.publish(f"homeassistant/light/{entity_id}/state", state, retain=True)


if __name__ == "__main__":
    main()
