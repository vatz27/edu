from flask import Flask, jsonify, request
import openai
import re
from threading import Thread, Event
import time
from queue import Queue

app = Flask(__name__)

# Set your OpenAI API key
openai.api_key = "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"  # Replace with your actual API key

# Cache to store previously generated questions to avoid repetition
question_cache = {}
question_queue = Queue()
stop_event = Event()

def generate_question_set(language, level, num_questions=10):
    question_set = []
    prompt = (
        f"Generate {num_questions} unique multiple-choice programming questions in {language} "
        f"at {level} level with 4 options each. Format each question as follows:\n"
        "Question: [question text]\n"
        "A. [option A]\n"
        "B. [option B]\n"
        "C. [option C]\n"
        "D. [option D]\n"
        "Correct Answer: [letter of correct option]\n"
        "Explanation: [explanation of the correct answer]\n\n"
    )

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that generates quiz questions according to the level chosen."},
                {"role": "user", "content": prompt}
            ]
        )

        content = response['choices'][0]['message']['content']
        questions = content.strip().split("\n\n")

        for question_text in questions:
            question_match = re.search(r'Question: (.+)', question_text)
            options_match = re.findall(r'([A-D])\. (.+)', question_text)
            answer_match = re.search(r'Correct Answer: ([A-D])', question_text)
            explanation_match = re.search(r'Explanation: (.+)', question_text, re.DOTALL)

            if question_match and len(options_match) == 4 and answer_match and explanation_match:
                question = {
                    "question": question_match.group(1),
                    "options": [option[1] for option in options_match],
                    "correct_answer": answer_match.group(1),
                    "explanation": explanation_match.group(1).strip()
                }

                # Check for duplication
                question_key = f"{language}_{level}_{question['question']}"
                if question_key not in question_cache:
                    question_cache[question_key] = True
                    question_set.append(question)

        print(f"\nGenerated {len(question_set)} questions for {language} at {level} level.")
    except Exception as e:
        print(f"Error generating questions: {e}")

    return question_set

def preload_question_set(language, level, num_questions=5):
    while not stop_event.is_set():
        question_set = generate_question_set(language, level, num_questions)
        if question_set:
            question_queue.put((language, level, question_set))
        else:
            print(f"No questions generated for {language} at {level} level. Deleting the set.")
            # If no questions are generated, we can choose to not add to the queue
        time.sleep(2)  # Generate a new set every 7 seconds

@app.route('/questions', methods=['GET'])
def get_questions():
    language = request.args.get('language')
    level = request.args.get('level')
    current_question_index = int(request.args.get('current_question_index', 0))

    if not language or not level:
        return jsonify({"error": "Please specify both language and level"}), 400

    question_set = []
    if not question_queue.empty():
        q_language, q_level, q_set = question_queue.get()
        if q_language == language and q_level == level:
            question_set = q_set

    if not question_set:
        question_set = generate_question_set(language, level)

    # Start a new thread to generate the next set of questions when the current set is finished
    if current_question_index == len(question_set) - 1:
        Thread(target=preload_question_set, args=(language, level)).start()

    return jsonify(question_set)

@app.route('/finish', methods=['POST'])
def finish():
    stop_event.set()
    return jsonify({"message": "Question generation stopped"}), 200

if __name__ == '__main__':
    # Run the Flask app
    app.run(debug=True, use_reloader=False, host='0.0.0.0')
