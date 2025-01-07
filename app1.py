from flask import Flask, request, jsonify
from flask_cors import CORS
import openai
import os
from datetime import datetime
import uuid
import json
from openai import OpenAI

app = Flask(__name__)
CORS(app)

# Configure OpenAI client
client = OpenAI(
    api_key='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'
)

# In-memory storage for chat histories
chat_histories = {}

class ChatHistory:
    def __init__(self, id, messages, timestamp):
        self.id = id
        self.messages = messages
        self.timestamp = timestamp

    def to_dict(self):
        return {
            'id': self.id,
            'messages': self.messages,
            'timestamp': self.timestamp.isoformat()
        }

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data received'}), 400
            
        message = data.get('message')
        chat_id = data.get('chat_id', str(uuid.uuid4()))

        if not message:
            return jsonify({'error': 'Message is required'}), 400

        # Get chat history or create new one
        if chat_id not in chat_histories:
            chat_histories[chat_id] = ChatHistory(
                id=chat_id,
                messages=[],
                timestamp=datetime.now()
            )

        # Add user message to history
        chat_histories[chat_id].messages.append({
            'role': 'user',
            'content': message
        })

        # Prepare messages for OpenAI API
        messages = [
            {'role': 'system', 'content': 'You are a helpful tutor assistant.'}
        ] + chat_histories[chat_id].messages

        try:
            # Get response from OpenAI using the new client
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=1000,
                temperature=0.7
            )

            # Extract assistant's response
            assistant_message = response.choices[0].message.content

            # Add assistant's response to history
            chat_histories[chat_id].messages.append({
                'role': 'assistant',
                'content': assistant_message
            })

            return jsonify({
                'response': assistant_message,
                'chat_id': chat_id
            })

        except Exception as api_error:
            print(f"OpenAI API Error: {str(api_error)}")
            return jsonify({
                'error': f"OpenAI API Error: {str(api_error)}"
            }), 500

    except Exception as e:
        print(f"Server Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/history', methods=['GET'])
def get_history():
    try:
        histories = [history.to_dict() for history in chat_histories.values()]
        return jsonify(histories)
    except Exception as e:
        print(f"Error getting history: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/new-chat', methods=['POST'])
def new_chat():
    try:
        chat_id = str(uuid.uuid4())
        chat_histories[chat_id] = ChatHistory(
            id=chat_id,
            messages=[],
            timestamp=datetime.now()
        )
        return jsonify({'chat_id': chat_id})
    except Exception as e:
        print(f"Error creating new chat: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400

        # Create uploads directory if it doesn't exist
        upload_dir = os.path.join(os.path.dirname(__file__), 'uploads')
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)

        # Save file
        filename = str(uuid.uuid4()) + '_' + file.filename
        file_path = os.path.join(upload_dir, filename)
        file.save(file_path)

        return jsonify({
            'success': True,
            'file_path': file_path,
            'filename': filename
        })

    except Exception as e:
        print(f"Error uploading file: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
