from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from transformers import pipeline
import time
import os
import sqlite3
import hashlib
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Secret key for sessions

# Store session analysis history for speed chart
session_analyses = {}  # {user_id: [{'vader_ms': 12, 'hf_ms': 45, 'timestamp': ...}]}


# Database setup
def init_db():
    conn = sqlite3.connect('sentiment.db')
    c = conn.cursor()

    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    # Analysis history table
    c.execute('''CREATE TABLE IF NOT EXISTS analyses
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER NOT NULL,
                  text
                  TEXT NOT NULL,
                  vader_sentiment TEXT NOT NULL,
                  vader_positive REAL,
                  vader_negative REAL,
                  vader_neutral REAL,
                  vader_compound REAL,
                  hf_sentiment TEXT NOT NULL,
                  hf_confidence REAL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (user_id) REFERENCES users (id))''')

    conn.commit()
    conn.close()


init_db()

# Initialize sentiment analyzers
vader_analyzer = SentimentIntensityAnalyzer()
print("Loading Hugging Face model...")
hf_analyzer = pipeline("sentiment-analysis",
                       model="distilbert-base-uncased-finetuned-sst-2-english")
print("Hugging Face model loaded!")


def analyze_with_vader(text):
    """Fast, rule-based sentiment analysis"""
    start_time = time.time()
    scores = vader_analyzer.polarity_scores(text)
    elapsed_ms = (time.time() - start_time) * 1000

    if scores['compound'] >= 0.05:
        sentiment = "POSITIVE"
    elif scores['compound'] <= -0.05:
        sentiment = "NEGATIVE"
    else:
        sentiment = "NEUTRAL"

    return {
        "sentiment": sentiment,
        "positive": round(scores['pos'], 3),
        "negative": round(scores['neg'], 3),
        "neutral": round(scores['neu'], 3),
        "compound": round(scores['compound'], 3),
        "speed_ms": round(elapsed_ms, 1)
    }


def analyze_with_huggingface(text):
    """Transformer-based sentiment analysis"""
    start_time = time.time()
    result = hf_analyzer(text)[0]
    elapsed_ms = (time.time() - start_time) * 1000

    return {
        "sentiment": result['label'],
        "confidence": round(result['score'], 4),
        "speed_ms": round(elapsed_ms, 1)
    }


def save_analysis(user_id, text, vader_result, hf_result):
    """Save analysis to database"""
    conn = sqlite3.connect('sentiment.db')
    c = conn.cursor()
    c.execute('''INSERT INTO analyses
                 (user_id, text, vader_sentiment, vader_positive, vader_negative,
                  vader_neutral, vader_compound, hf_sentiment, hf_confidence)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (user_id, text, vader_result['sentiment'], vader_result['positive'],
               vader_result['negative'], vader_result['neutral'], vader_result['compound'],
               hf_result['sentiment'], hf_result['confidence']))
    conn.commit()
    conn.close()


def get_user_stats(user_id):
    """Get statistics for a user with all metrics"""
    conn = sqlite3.connect('sentiment.db')
    c = conn.cursor()

    # Total analyses
    c.execute("SELECT COUNT(*) FROM analyses WHERE user_id = ?", (user_id,))
    total = c.fetchone()[0]

    # Sentiment breakdown
    c.execute("SELECT vader_sentiment, COUNT(*) FROM analyses WHERE user_id = ? GROUP BY vader_sentiment", (user_id,))
    breakdown = {row[0]: row[1] for row in c.fetchall()}

    # Recent analyses (last 10) with ALL metrics
    c.execute(
        "SELECT text, vader_sentiment, vader_positive, vader_negative, vader_neutral, vader_compound, hf_sentiment, hf_confidence, created_at FROM analyses WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
        (user_id,))
    recent = [{"text": row[0], "vader": row[1], "vader_positive": row[2], "vader_negative": row[3], "vader_neutral": row[4], "vader_compound": row[5], "hf": row[6], "hf_confidence": row[7], "date": row[8]} for row in c.fetchall()]

    conn.close()
    return {"total": total, "breakdown": breakdown, "recent": recent}


@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', username=session.get('username'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()

        conn = sqlite3.connect('sentiment.db')
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE username = ? AND password = ?", (username, password))
        user = c.fetchone()
        conn.close()

        if user:
            session['user_id'] = user[0]
            session['username'] = username
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="Invalid credentials")

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()

        conn = sqlite3.connect('sentiment.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            conn.close()
            return render_template('register.html', error="Username already exists")

    return render_template('register.html')


@app.route('/logout')
def logout():
    # Clear session history for this user
    if 'user_id' in session:
        session_analyses.pop(session['user_id'], None)
    session.clear()
    return redirect(url_for('login'))


@app.route('/analyze', methods=['POST'])
def analyze():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.get_json()
    text = data.get('text', '')

    if not text:
        return jsonify({'error': 'No text provided'}), 400

    vader_result = analyze_with_vader(text)
    hf_result = analyze_with_huggingface(text)

    # Save to database
    save_analysis(session['user_id'], text, vader_result, hf_result)

    # Track session history for speed chart
    user_id = session['user_id']
    if user_id not in session_analyses:
        session_analyses[user_id] = []
    session_analyses[user_id].append({
        'vader_ms': vader_result['speed_ms'],
        'hf_ms': hf_result['speed_ms'],
        'timestamp': datetime.now().strftime('%H:%M:%S')
    })
    # Keep only last 10 for chart
    if len(session_analyses[user_id]) > 10:
        session_analyses[user_id] = session_analyses[user_id][-10:]

    results = {
        'text': text,
        'vader': vader_result,
        'huggingface': hf_result
    }

    return jsonify(results)


@app.route('/history')
def history():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    stats = get_user_stats(session['user_id'])
    return render_template('history.html', stats=stats, username=session['username'])


@app.route('/session-history')
def session_history():
    """Get current session's analysis history for speed chart"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    user_id = session['user_id']
    history = session_analyses.get(user_id, [])
    return jsonify(history)


if __name__ == '__main__':
    print("=" * 60)
    print("Sentiment Analysis Dashboard Starting...")
    print("=" * 60)
    print("\nhttp://127.0.0.1:5000")
    print("\nModels loaded:")
    print("VADER (rule-based)")
    print("Hugging Face (transformer)")
    print("\nFeatures:")
    print("User accounts with SQLite database")
    print("Session-based speed tracking (last 10 analyses)")
    print("Full metrics in history page")
    print("\nPress Ctrl+C to stop\n")
    app.run(debug=True, port=5000)