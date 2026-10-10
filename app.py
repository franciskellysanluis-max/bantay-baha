import os
import json
import re
import joblib
from flask import Flask, request, jsonify, render_template_string
from google import genai

app = Flask(__name__)

# Load FAQ and ML Model
with open('faq.json', 'r') as f:
    faqs = json.load(f)

clf = joblib.load('model.pkl')
vectorizer = joblib.load('vectorizer.pkl')

# Memory logs for admin stats
stats_db = {
    "ratings": [],  # list of True/False
    "categories": {}  # cat -> count
}

STOP_WORDS = set(["the", "a", "an", "is", "are", "ang", "ng", "sa", "mga", "na", "ano", "kailan", "paano", "ba"])

def retrieve_top3_faqs(user_query):
    words = re.findall(r'\w+', user_query.lower())
    filtered_words = set([w for w in words if w not in STOP_WORDS])
    
    scored_faqs = []
    for faq in faqs:
        faq_text = (faq['question'] + " " + faq['answer']).lower()
        faq_words = set(re.findall(r'\w+', faq_text))
        score = len(filtered_words.intersection(faq_words))
        scored_faqs.append((score, faq))
    
    scored_faqs.sort(key=lambda x: x[0], reverse=True)
    return [faq for score, faq in scored_faqs[:3]]

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json() or {}
    message = data.get("message", "").strip()
    
    if not message or len(message) > 500:
        return jsonify({"error": "Message must be between 1 and 500 characters."}), 400

    # ML Category Prediction
    X_vec = vectorizer.transform([message])
    predicted_cat = clf.predict(X_vec)[0]
    
    stats_db["categories"][predicted_cat] = stats_db["categories"].get(predicted_cat, 0) + 1

    # RAG Retrieval
    top_faqs = retrieve_top3_faqs(message)
    faq_ids = [f['id'] for f in top_faqs]
    context = "\n".join([f"ID {f['id']}: Q: {f['question']} A: {f['answer']}" for f in top_faqs])

    # Gemini Generation
    api_key = os.environ.get("GEMINI_API_KEY")
    answer = ""
    
    if api_key:
        try:
            client = genai.Client(api_key=api_key)
            prompt = f"""You are Bayanihan College's enrollment assistant. Answer the user's question accurately using ONLY the official FAQ knowledge base provided below.
If the information is not present in the FAQ, say: "I am sorry, but I do not have that information in my official enrollment records."
Answer in the language used by the user (English, Filipino, or Taglish). Keep it concise.

FAQ Context:
{context}

User Question: {message}"""

            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
            )
            answer = response.text
        except Exception:
            answer = f"According to official FAQ entries {faq_ids}: " + " ".join([f['answer'] for f in top_faqs])
    else:
        answer = f"According to official FAQ entries {faq_ids}: " + " ".join([f['answer'] for f in top_faqs])

    return jsonify({
        "answer": answer,
        "faq_ids": faq_ids,
        "predicted_category": predicted_cat
    })

@app.route('/api/rating', methods=['POST'])
def rate():
    data = request.get_json() or {}
    is_positive = data.get("rating") == "up"
    stats_db["ratings"].append(is_positive)
    return jsonify({"status": "ok"})

@app.route('/api/stats', methods=['GET'])
def get_stats():
    total_ratings = len(stats_db["ratings"])
    pos_ratings = sum(1 for r in stats_db["ratings"] if r)
    percentage_up = round((pos_ratings / total_ratings * 100), 1) if total_ratings > 0 else 0.0
    
    return jsonify({
        "questions_per_category": stats_db["categories"],
        "thumbs_up_percentage": percentage_up
    })

@app.route('/')
def home():
    return render_template_string(HTML_CHAT)

@app.route('/admin')
def admin():
    return render_template_string(HTML_ADMIN)

HTML_CHAT = """<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Enrollment Assistant</title>
    <style>
        body { font-family: sans-serif; margin: 0; padding: 10px; background: #f4f6f8; display: flex; flex-direction: column; height: 95vh; }
        #chatbox { flex: 1; overflow-y: auto; padding: 10px; background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .msg { margin: 10px 0; max-width: 80%; padding: 10px; border-radius: 8px; font-size: 14px; }
        .user { background: #007bff; color: white; margin-left: auto; }
        .bot { background: #e9ecef; color: #333; margin-right: auto; }
        .meta { font-size: 11px; color: #666; margin-top: 5px; }
        .actions { margin-top: 5px; }
        .btn-thumb { cursor: pointer; border: none; background: none; font-size: 14px; }
        #input-area { display: flex; gap: 5px; margin-top: 10px; }
        input { flex: 1; padding: 10px; font-size: 14px; border: 1px solid #ccc; border-radius: 4px; }
        button { padding: 10px 15px; font-size: 14px; background: #28a745; color: white; border: none; border-radius: 4px; cursor: pointer; }
    </style>
</head>
<body>
    <h2>Bayanihan College Helpdesk</h2>
    <div id="chatbox"></div>
    <div id="loading" style="display:none; font-size:12px; color:#888;">Assistant is typing...</div>
    <div id="input-area">
        <input type="text" id="query" placeholder="Ask about enrollment..." onkeydown="if(event.key==='Enter') send()">
        <button onclick="send()">Send</button>
    </div>
    <script>
        async function send() {
            let input = document.getElementById('query');
            let text = input.value.trim();
            if(!text) return;
            
            let chat = document.getElementById('chatbox');
            chat.innerHTML += `<div class="msg user">${text}</div>`;
            input.value = '';
            document.getElementById('loading').style.display = 'block';
            
            let res = await fetch('/api/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message: text})
            });
            let data = await res.json();
            document.getElementById('loading').style.display = 'none';
            
            if(res.ok) {
                chat.innerHTML += `
                    <div class="msg bot">
                        ${data.answer}
                        <div class="meta">Category: ${data.predicted_category} | FAQ IDs: [${data.faq_ids.join(', ')}]</div>
                        <div class="actions">
                            <button class="btn-thumb" onclick="rate('up')">👍</button>
                            <button class="btn-thumb" onclick="rate('down')">👎</button>
                        </div>
                    </div>`;
            } else {
                chat.innerHTML += `<div class="msg bot" style="color:red;">${data.error || 'Error connecting to server.'}</div>`;
            }
            chat.scrollTop = chat.scrollHeight;
        }

        async function rate(type) {
            await fetch('/api/rating', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({rating: type})
            });
            alert('Feedback submitted!');
        }
    </script>
</body>
</html>"""

HTML_ADMIN = """<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Stats</title>
    <style>
        body { font-family: sans-serif; padding: 20px; background: #f8f9fa; }
        .card { background: white; padding: 15px; border-radius: 8px; margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    </style>
</head>
<body>
    <h1>Helpdesk Admin Dashboard</h1>
    <div class="card">
        <h3>Thumbs Up Satisfaction Rate</h3>
        <p id="satisfaction">Loading...</p>
    </div>
    <div class="card">
        <h3>Questions Per Category</h3>
        <pre id="categories">Loading...</pre>
    </div>
    <script>
        async function loadStats() {
            let res = await fetch('/api/stats');
            let data = await res.json();
            document.getElementById('satisfaction').innerText = data.thumbs_up_percentage + '% Positive Feedback';
            document.getElementById('categories').innerText = JSON.stringify(data.questions_per_category, null, 2);
        }
        loadStats();
    </script>
</body>
</html>"""

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)