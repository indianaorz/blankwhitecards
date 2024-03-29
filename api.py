import asyncio
import websockets
import json
import logging
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

connected_clients = set()

game_state = {
    'cards': {}  # Starting with no cards initially
}

import requests



# Action Handlers
async def handle_create_card(data, websocket):
    new_card_id = str(uuid.uuid4())
    x, y = data.get('x', 0), data.get('y', 0)
    game_state['cards'][new_card_id] = {'x': x, 'y': y, 'heldBy': None}
    await broadcast({'type': 'newCard', 'cardId': new_card_id, 'x': x, 'y': y})

async def handle_pickup(data, websocket):
    card_id = data.get('cardId')
    if card_id in game_state['cards']:
        game_state['cards'][card_id]['heldBy'] = websocket

async def handle_move(data, websocket):
    card_id = data.get('cardId')
    if card_id in game_state['cards']:
        card_info = game_state['cards'][card_id]
        card_info['x'] = data.get('x', card_info['x'])
        card_info['y'] = data.get('y', card_info['y'])
        await broadcast({'type': 'update', 'cardId': card_id, 'x': card_info['x'], 'y': card_info['y']})

async def handle_drop(data, websocket):
    card_id = data.get('cardId')
    if card_id in game_state['cards']:
        game_state['cards'][card_id]['heldBy'] = None


async def handle_draw(data, websocket):
    new_cards = {}
    base_x, base_y = 0, 600  # Base position for the drawn cards in the client's view
    spacing = 100  # Spacing between cards

    for i in range(4):  # Draw 4 cards
        new_card_id = str(uuid.uuid4())
        # Space cards out horizontally and center them on the screen
        x = base_x + (i * spacing) - (1.5 * spacing)  # Adjust X to center, assuming 4 cards
        y = base_y  # Keep Y constant for all cards in hand
        # Note: Not adding these to game_state['cards'] as they're client-specific
        new_cards[new_card_id] = {'x': x, 'y': y, 'isVisible': False}
    
    # Send the new cards directly to the requesting client
    await websocket.send(json.dumps({'type': 'drawCards', 'cards': new_cards}))

async def handle_place_card_from_hand(data, websocket):
    card_id = data.get('cardId')
    x = data.get('x', 0)
    y = data.get('y', 0)
    # Add the card to the global game state with its initial position
    game_state['cards'][card_id] = {'x': x, 'y': y, 'heldBy': None, 'isVisible': True}
    # Broadcast the new card to all clients so it becomes part of the shared game state
    await broadcast({'type': 'newCard', 'cardId': card_id, 'x': x, 'y': y})



async def handle_generate_image(data, websocket):
    prompt_text = data.get('prompt')
    # Construct the request dictionary expected by generate_image
    request_dict = {
        'WorkflowFileName': 'generate.json',
        'PositiveText': prompt_text,  # Assuming you want to use the prompt for this field
        'Lora': 'delta'
        # Add other necessary parameters here
    }
    await generate_image(request_dict)
    response_message = {'message': 'Image generation initiated'}
    await websocket.send(json.dumps(response_message))


async def generate_image(request):
    #log request
    print(request)
    # Load the workflow (prompt structure) from a file
    with open(request['WorkflowFileName'], 'r') as file:
        prompt = json.load(file)

    print (prompt)  # For debugging
    prompt["30"]["inputs"]["text_g"] = prompt["30"]["inputs"]["text_g"].replace("prompt", request.get("PositiveText", ""))
    prompt["30"]["inputs"]["text_l"] = prompt["30"]["inputs"]["text_l"].replace("prompt", request.get("PositiveText", ""))
    # prompt["33"]["inputs"]["text_g"] = request.get("NegativeText", "")
    # prompt["33"]["inputs"]["text_l"] = request.get("NegativeText", "")
    prompt["43"]["inputs"]["width"] = 512  # request.get("Width", 512)
    prompt["43"]["inputs"]["height"] = 768  # request.get("Height", 768)
    prompt["43"]["inputs"]["batch_size"] = 1  # request.get("BatchSize", 1)
    prompt["57"]["inputs"]["strength_model"] = 0.7  # request.get("Strength", 0.7)
    prompt["57"]["inputs"]["lora_name"] = request.get("Lora", "") + ".ckpt"

    # Serialize the modified prompt
    payload_json = json.dumps({"prompt": prompt})

    print(payload_json)  # For debugging

    # Send the modified prompt to the image generation API
    response = requests.post("http://127.0.0.1:8188/prompt", data=payload_json, headers={"Content-Type": "application/json"})

    if response.status_code == 200:
        response_body = response.json()
        prompt_id = response_body["prompt_id"]
        return prompt_id  # Or handle the response as needed
    else:
        raise Exception("Failed to queue prompt")

async def broadcast(message):
    for client in connected_clients:
        if client.open:
            await client.send(json.dumps(message))

# Message Router
async def route_message(data, websocket):
    action = data.get('action')
    if action == 'createCard':
        await handle_create_card(data, websocket)
    elif action == 'pickup':
        await handle_pickup(data, websocket)
    elif action == 'move':
        await handle_move(data, websocket)
    elif action == 'drop':
        await handle_drop(data, websocket)
    elif action == 'draw':
        await handle_draw(data, websocket)
    elif action == 'placeCardFromHand':
        await handle_place_card_from_hand(data, websocket)
    elif action == 'generateImage':
        await handle_generate_image(data, websocket)

    else:
        logger.error(f"Unknown action: {action}")

async def handler(websocket, path):
    connected_clients.add(websocket)
    logger.info(f"New client connected: {websocket.remote_address}")
    await websocket.send(json.dumps({'type': 'init', 'state': game_state}))
    try:
        async for message in websocket:
            data = json.loads(message)
            logger.info(f"Received message: {data}")
            await route_message(data, websocket)
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        connected_clients.remove(websocket)
        logger.info(f"Client disconnected: {websocket.remote_address}")

async def main():
    async with websockets.serve(handler, "0.0.0.0", 6789):
        logger.info("Server started on ws://0.0.0.0:6789")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
