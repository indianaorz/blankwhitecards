import asyncio
import websockets
import json
import logging
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

connected_clients = set()

game_state = {
    'cards': {
        'card1': {'x': 100, 'y': 100, 'heldBy': None},
        'card2': {'x': 200, 'y': 200, 'heldBy': None},
    }
}


async def broadcast(message):
    for client in connected_clients:
        if client.open:
            await client.send(json.dumps(message))

async def handler(websocket, path):
    connected_clients.add(websocket)
    logger.info(f"New client connected: {websocket.remote_address}")
    await websocket.send(json.dumps({'type': 'init', 'state': game_state}))
    try:
        async for message in websocket:
            data = json.loads(message)
            logger.info(f"Received message: {data}")
            action = data.get('action')

            if action == 'createCard':
                # Generate a new card with a unique ID
                new_card_id = str(uuid.uuid4())
                x = data.get('x', 0)
                y = data.get('y', 0)
                game_state['cards'][new_card_id] = {'x': x, 'y': y, 'heldBy': None}
                await broadcast({'type': 'newCard', 'cardId': new_card_id, 'x': x, 'y': y})
            elif action in ['pickup', 'move', 'drop']:
                card_id = data.get('cardId')
                if card_id in game_state['cards']:
                    card_info = game_state['cards'][card_id]
                    card_info['x'] = data.get('x', card_info['x'])
                    card_info['y'] = data.get('y', card_info['y'])
                    if action == 'pickup':
                        card_info['heldBy'] = websocket
                    elif action == 'drop':
                        card_info['heldBy'] = None
                    await broadcast({'type': 'update', 'cardId': card_id, 'x': card_info['x'], 'y': card_info['y']})
            else:
                logger.error(f"Unknown action: {action}")
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