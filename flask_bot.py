from quart import Quart, request, jsonify
from main import get_web

app = Quart(__name__)


@app.route('/')
def home():
    return "I'm alive"

@app.route('/send', methods=['POST'])
async def receive_data():
    # try:
        payload = await request.form
        data = payload.get('data')
        print(data)
        user_id = payload.get('user_id')
        message_id = payload.get('message_id')

        # Validate that 'data' and 'user_id' are present
        if data is None or user_id is None:
            return jsonify({"status": "error", "message": "Missing 'data' or 'user_id' in payload"}), 400

        # Call the asynchronous function
        await get_web(data=data, user_id=user_id,message_id=message_id)

        return jsonify({"status": "success"}), 200
    #
    # except Exception as e:
    #     return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)