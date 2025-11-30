# Central AI Addon for Home Assistant

This addon provides a central AI service for Home Assistant using Ollama. It allows you to control your smart home devices using natural language commands.

## Features

- **Natural Language Commands:** Control your Home Assistant devices using plain English.
- **Ollama Integration:** Uses the Ollama platform to understand and process your commands.
- **MQTT Communication:** Communicates with Home Assistant via MQTT for real-time control.
- **Device & Entity Awareness:** The AI is aware of your Home Assistant devices and entities, including their friendly names.
- **Self-Correction:** The AI can correct its own mistakes when it tries to use the wrong service or entity.
- **Group Support:** The AI can control and query groups of entities.
- **Friendly Name Support:** The AI uses the friendly names of your devices in its responses, making them more natural and easier to understand.

## Getting Started

1.  **Install the Addon:** Follow the instructions in the Home Assistant documentation to install this addon.
2.  **Configure the Addon:**
    -   Set the `ollama_url` to the URL of your Ollama instance.
    -   Set the `ha_token` to a long-lived access token for Home Assistant.
    -   Configure the MQTT settings to match your MQTT broker.
3.  **Start the Addon:** Start the addon and check the logs to make sure it connects to Ollama and your MQTT broker.

## Usage

Once the addon is running, you can send commands to the AI by publishing a message to the `central_ai/prompt/request` MQTT topic. The message should be a JSON object with a `prompt` key.

**Example:**

```json
{
  "prompt": "Turn on the kitchen lights"
}
```

The AI will process the command and publish a response to the `central_ai/prompt/response` MQTT topic.

### Using Groups

You can use Home Assistant groups to control multiple devices at once. For example, if you have a group named `group.living_room_lights`, you can say:

> "Turn on the living room lights"

The AI will understand that you want to turn on all the lights in the living room.

You can also ask for the status of a group:

> "Are the living room lights on?"

The AI will check the status of all the lights in the group and give you a summary.

### Friendly Names

The AI is aware of the friendly names of your devices. This means you can use the friendly names in your commands, and the AI will use them in its responses.

For example, if you have a light with the entity ID `light.kitchen` and the friendly name "Kitchen Light", you can say:

> "Turn on the Kitchen Light"

The AI will understand which light you mean, and it will respond with:

> "The Kitchen Light is now on."