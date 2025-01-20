from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List, Optional, Set
import os
import random
import json
from urllib.parse import unquote
from threading import Thread

app = Flask(__name__)
CORS(app)
load_dotenv()

api_key = os.getenv('OPENAI_API_KEY')
client = OpenAI(api_key=api_key)

# Pydantic models
class QuizQuestion(BaseModel):
    question: str
    options: List[str]
    answer: str
    explanation: str

class QuizResponse(BaseModel):
    questions: List[QuizQuestion]
    should_fetch: bool

# Global question cache and used questions tracking
question_cache: List[QuizQuestion] = []
used_questions: Set[str] = set()  # Store used question texts
current_topic: str = ""

def generate_quiz_questions(topic: str, num_questions: int = 5) -> Optional[List[QuizQuestion]]:
    system_prompt = f"""
    You must respond with a valid JSON object. Generate {num_questions} multiple-choice questions about {topic}.
    The response should be a JSON object with the following structure:
    {{
        "questions": [
            {{
                "question": "Question text",
                "options": ["Option 1", "Option 2", "Option 3", "Option 4"],
                "answer": "Correct option text",
                "explanation": "Brief explanation"
            }}
        ]
    }}
    """

    user_prompt = f"""
    Please generate {num_questions} multiple choice questions about {topic} in JSON format.
    Each question must have exactly 4 options, and the answer must exactly match one of the options.
    Make sure each question is unique and not previously asked.
    """

    try:
        completion = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=1.0,
            response_format={"type": "json_object"}
        )

        response_text = completion.choices[0].message.content
        
        try:
            response_data = json.loads(response_text)
            if "questions" not in response_data:
                return None

            processed_questions = []
            for q in response_data["questions"]:
                if not all(k in q for k in ["question", "options", "answer", "explanation"]):
                    continue
                
                if len(q["options"]) != 4:
                    continue

                # Check if question is repeated
                if q["question"] in used_questions:
                    print(f"Duplicate question detected: {q['question']}")
                    continue

                question = QuizQuestion(
                    question=q["question"],
                    options=q["options"].copy(),
                    answer=q["answer"],
                    explanation=q["explanation"]
                )

                if question.answer not in question.options:
                    continue

                # Print question for monitoring
                print(f"Generated question: {question.question}")
                
                random.shuffle(question.options)
                used_questions.add(question.question)  # Add to used questions set
                processed_questions.append(question)

            return processed_questions

        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            return None

    except Exception as e:
        print(f"Error in generate_quiz_questions: {str(e)}")
        return None

def preload_questions(topic: str):
    """Generate questions in background and store in cache"""
    global question_cache, current_topic, used_questions
    if topic != current_topic:
        question_cache.clear()
        used_questions.clear()  # Clear used questions when topic changes
        current_topic = topic
    
    questions = generate_quiz_questions(topic, 5)
    if questions:
        question_cache.extend(questions)

@app.route('/quiz/next', methods=['GET'])
def get_next_questions():
    try:
        topic = unquote(request.args.get('topic', ''))
        current_index = int(request.args.get('current_index', 0))
        
        if not topic:
            return jsonify({"error": "Missing topic parameter"}), 400

        topic = topic.strip()
        
        # If we're at index 2 or cache is low, preload next set
        if current_index % 5 == 2 or len(question_cache) < 5:
            Thread(target=preload_questions, args=(topic,)).start()

        # If cache is empty, generate initial questions
        if len(question_cache) < 5:
            questions = generate_quiz_questions(topic, 5)
            if questions is None:
                return jsonify({"error": "Failed to generate questions"}), 500
        else:
            questions = question_cache[:5]
            del question_cache[:5]

        return jsonify({
            "questions": [q.model_dump() for q in questions],  # Updated from dict() to model_dump()
            "should_fetch": True
        })

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    CORS(app, resources={r"/*": {"origins": "*"}})
    app.run(debug=True, port=5000, host='0.0.0.0')
