from aiogram.types import Message
from quart import Quart, request, jsonify
from main import get_web

app = Quart(__name__)

@app.route('/', methods=['POST'])
async def receive_data():
    try:
        # Check if the Content-Type is application/json
        if not request.is_json:
            return jsonify({"status": "error", "message": "Content-Type must be application/json"}), 415

        # Get the JSON data from the request
        payload = await request.json

        # Extract 'data' and 'user_id' from the payload
        data = payload.get('data')
        user_id = payload.get('user_id')
        message_id = payload.get('message_id')

        # Validate that 'data' and 'user_id' are present
        if data is None or user_id is None:
            return jsonify({"status": "error", "message": "Missing 'data' or 'user_id' in payload"}), 400

        # Call the asynchronous function
        await get_web(data=data, user_id=user_id,message_id=message_id)

        return jsonify({"status": "success"}), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == '__main__':
    app.run()