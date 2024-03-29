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
        x = data.get('x')
        y = data.get('y')
        card_info['x'] = x
        card_info['y'] = y
        await broadcast({'type': 'update', 'cardId': card_id, 'x': x, 'y': y})

async def handle_drop(data, websocket):
    card_id = data.get('cardId')
    if card_id in game_state['cards']:
        card_info = game_state['cards'][card_id]
        if card_info['heldBy'] == websocket:
            card_info['heldBy'] = None
            card_info['x'] = data.get('x', card_info['x'])
            card_info['y'] = data.get('y', card_info['y'])
            await broadcast({'type': 'update', 'cardId': card_id, 'x': card_info['x'], 'y': card_info['y']})


async def handle_draw(data, websocket):
    new_cards = {}
    base_x, base_y = 0, 600  # Base position for the drawn cards in the client's view
    spacing = 100  # Spacing between cards

    prompt_text = data.get('prompt', '')  # Get the prompt from the client

    # Generate a batch of images using the prompt
    request_dict = {
        'WorkflowFileName': 'generate.json',
        'PositiveText': prompt_text,
        'Lora': 'delta'
    }
    prompt_id = await generate_image(request_dict)
    
    # Monitor the generation progress
    await monitor_generation_progress(prompt_id, websocket)

    # Fetch the image data after the generation is complete
    image_data_list = await fetch_image_data(prompt_id)

    for i, image_data in enumerate(image_data_list):
        new_card_id = str(uuid.uuid4())
        # Space cards out horizontally and center them on the screen
        x = base_x + (i * spacing) - (1.5 * spacing)  # Adjust X to center, assuming 4 cards
        y = base_y  # Keep Y constant for all cards in hand

        # Save the image data with the card ID
        save_card_image(new_card_id, image_data)

        new_cards[new_card_id] = {'x': x, 'y': y, 'isVisible': False}
    
    # Send the new cards directly to the requesting client
    await websocket.send(json.dumps({'type': 'drawCards', 'cards': new_cards}))

import os

def save_card_image(card_id, image_data):
    # Create a folder to store card images if it doesn't exist
    if not os.path.exists('card_images'):
        os.makedirs('card_images')

    # Save the image data to a file with the card ID as the filename
    image_path = os.path.join('card_images', f'{card_id}.png')
    with open(image_path, 'wb') as file:
        file.write(base64.b64decode(image_data))

async def handle_get_card_image(data, websocket):
    card_id = data.get('cardId')
    image_path = os.path.join('card_images', f'{card_id}.png')
    if os.path.exists(image_path):
        with open(image_path, 'rb') as file:
            image_data = base64.b64encode(file.read()).decode('utf-8')
            await websocket.send(json.dumps({'type': 'cardImage', 'cardId': card_id, 'imageData': image_data}))
    else:
        await websocket.send(json.dumps({'type': 'cardImage', 'cardId': card_id, 'imageData': None}))

async def fetch_image_data(prompt_id):
    response = requests.get(f"http://{server_address}/history/{prompt_id}")
    if response.ok:
        data = response.json()
        outputs = data[prompt_id]['outputs']
        images_output = outputs["92"]["images"]
        image_data_list = []
        for img in images_output:
            image_response = requests.get(f"http://{server_address}/view?filename={img['filename']}&subfolder={img['subfolder']}&type={img['type']}")
            if image_response.ok:
                image_data = base64.b64encode(image_response.content).decode('utf-8')
                image_data_list.append(image_data)
        return image_data_list
    return []

async def handle_place_card_from_hand(data, websocket):
    card_id = data.get('cardId')
    x = data.get('x', 0)
    y = data.get('y', 0)
    # Add the card to the global game state with its initial position
    game_state['cards'][card_id] = {'x': x, 'y': y, 'heldBy': None, 'isVisible': True}
    
    # Retrieve the card image data
    image_data = await get_card_image_data(card_id)
    
    # Broadcast the new card, its image data, and position to all clients
    await broadcast({'type': 'newCard', 'cardId': card_id, 'x': x, 'y': y, 'imageData': image_data})

server_address = "127.0.0.1:8188"  # Replace with the actual server address


async def handle_generate_image(data, websocket):
    prompt_text = data.get('prompt')
    # Construct the request dictionary expected by generate_image
    request_dict = {
        'WorkflowFileName': 'generate.json',
        'PositiveText': prompt_text,  # Assuming you want to use the prompt for this field
        'Lora': 'delta'
        # Add other necessary parameters here
    }
    prompt_id = await generate_image(request_dict)
    response_message = {'message': 'Image generation initiated'}
    await websocket.send(json.dumps(response_message))
    await monitor_generation_progress(prompt_id, websocket)

async def generate_image(request):
    # Log request
    logger.info(request)
    # Load the workflow (prompt structure) from a file
    with open(request['WorkflowFileName'], 'r') as file:
        prompt = json.load(file)

    logger.info(prompt)  # For debugging
    prompt["30"]["inputs"]["text_g"] = prompt["30"]["inputs"]["text_g"].replace("prompt", request.get("PositiveText", ""))
    prompt["30"]["inputs"]["text_l"] = prompt["30"]["inputs"]["text_l"].replace("prompt", request.get("PositiveText", ""))
    # prompt["33"]["inputs"]["text_g"] = request.get("NegativeText", "")
    # prompt["33"]["inputs"]["text_l"] = request.get("NegativeText", "")
    prompt["43"]["inputs"]["width"] = 512  # request.get("Width", 512)
    prompt["43"]["inputs"]["height"] = 768  # request.get("Height", 768)
    prompt["43"]["inputs"]["batch_size"] = 4  # request.get("BatchSize", 1)
    prompt["57"]["inputs"]["strength_model"] = 0.7  # request.get("Strength", 0.7)
    prompt["57"]["inputs"]["lora_name"] = request.get("Lora", "") + ".ckpt"

    # Serialize the modified prompt
    payload_json = json.dumps({"prompt": prompt})

    logger.info(payload_json)  # For debugging

    # Send the modified prompt to the image generation API
    response = requests.post(f"http://{server_address}/prompt", data=payload_json, headers={"Content-Type": "application/json"})

    if response.status_code == 200:
        response_body = response.json()
        prompt_id = response_body["prompt_id"]
        return prompt_id  # Or handle the response as needed
    else:
        raise Exception("Failed to queue prompt")


async def monitor_generation_progress(prompt_id, websocket):
    while True:
        # Fetch the generation status from the API
        logger.info(f"Fetching generation status for prompt {prompt_id}")
        status_response = requests.get(f"http://{server_address}/history/{prompt_id}")
        if status_response.ok:
            status_data = status_response.json()
            logger.info(f"Received response: {status_data}")

            # Check if the generation is complete
            if status_data.get(prompt_id, {}).get('status', {}).get('completed', False):
                logger.info("Generation complete")
                return
            else:
                logger.info("Generation not yet complete")
        else:
            logger.error(f"Failed to fetch generation status for prompt {prompt_id}")

        # Wait for a short period before checking the status again
        logger.info("Waiting before checking status again")
        await asyncio.sleep(1)

import base64

async def fetch_and_send_images(prompt_id, websocket):
    response = requests.get(f"http://{server_address}/history/{prompt_id}")
    if response.ok:
        data = response.json()
        outputs = data[prompt_id]['outputs']
        images_output = outputs["92"]["images"]

        for img in images_output:
            image_response = requests.get(f"http://{server_address}/view?filename={img['filename']}&subfolder={img['subfolder']}&type={img['type']}")
            if image_response.ok:
                image_data = image_response.content  # Get the raw bytes directly
                image_message = {
                    'type': 'image',
                    'data': base64.b64encode(image_data).decode('utf-8')  # Encode the bytes as base64
                }
                await websocket.send(json.dumps(image_message))
            else:
                logger.error(f"Failed to fetch image {img['filename']}")
    else:
        logger.error(f"Failed to fetch history for prompt {prompt_id}")

async def fetch_image(img):
    response = requests.get(f"http://{server_address}/view?filename={img['filename']}&subfolder={img['subfolder']}&type={img['type']}")
    if response.ok:
        return response
    else:
        logger.error(f"Failed to fetch image URL for {img['filename']}")
        return None



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
    elif action == 'getCardImage':
        await handle_get_card_image(data, websocket)
        

    else:
        logger.error(f"Unknown action: {action}")

import traceback

async def get_card_image_data(card_id):
    image_path = os.path.join('card_images', f'{card_id}.png')
    if os.path.exists(image_path):
        with open(image_path, 'rb') as file:
            image_data = base64.b64encode(file.read()).decode('utf-8')
            return image_data
    return None

async def handler(websocket, path):
    connected_clients.add(websocket)
    logger.info(f"New client connected: {websocket.remote_address}")
    if websocket.open:
        try:
            await websocket.send(json.dumps({'type': 'init', 'state': game_state}))

             # Send the card images for all cards on the field
            for card_id in game_state['cards']:
                image_data = await get_card_image_data(card_id)
                if image_data:
                    await websocket.send(json.dumps({'type': 'cardImage', 'cardId': card_id, 'imageData': image_data}))
        except Exception as e:
            logger.error(f"Error sending initial state to client: {e}")
            logger.error(traceback.format_exc())
    else:
        logger.warning("WebSocket connection is closed. Unable to send initial state.")

    try:
        async for message in websocket:
            data = json.loads(message)
            logger.info(f"Received message: {data}")
            if websocket.open:
                try:
                    await route_message(data, websocket)
                except Exception as e:
                    logger.error(f"Error routing message: {e}")
                    logger.error(traceback.format_exc())
            else:
                logger.warning("WebSocket connection is closed. Unable to route message.")
    except Exception as e:
        logger.error(f"Error: {e}")
        logger.error(traceback.format_exc())
    finally:
        connected_clients.remove(websocket)
        logger.info(f"Client disconnected: {websocket.remote_address}")

async def main():
    async with websockets.serve(handler, "0.0.0.0", 6789):
        logger.info("Server started on ws://0.0.0.0:6789")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
