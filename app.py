import hmac
import hashlib
import base64
import os
import uuid
import time
from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///highscores.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'f498ewf49we84f9a8we4f'
db = SQLAlchemy(app)

games = {}

class HighScore(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    score = db.Column(db.Integer, nullable=False)

def generate_secret_key():
    return base64.urlsafe_b64encode(os.urandom(32)).decode('utf-8')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start_game', methods=['GET'])
def start_game():
    secret_key = generate_secret_key()
    nonce = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    session['secret_key'] = secret_key
    session['nonce'] = nonce
    session['session_id'] = session_id
    games[session_id] = {
        'events': [],
        'score': 0,
        'snake': [(0, 0)],  # Initial snake position
        'food': None
    }
    return jsonify({'secret_key': secret_key, 'nonce': nonce, 'session_id': session_id})

@app.route('/log_event', methods=['POST'])
def log_event():
    session_id = session.get('session_id')
    if not session_id or session_id not in games:
        return jsonify({'error': 'Invalid session'}), 400

    event = request.json
    games[session_id]['events'].append(event)
    update_game_state(session_id, event)
    return jsonify({'message': 'Event logged'})

def update_game_state(session_id, event):
    game = games[session_id]
    if event['type'] == 'move':
        # Update the snake's position based on the direction
        direction = event['direction']
        snake = game['snake']
        head = snake[0]
        if direction == 'UP':
            new_head = (head[0], head[1] - 20)
        elif direction == 'DOWN':
            new_head = (head[0], head[1] + 20)
        elif direction == 'LEFT':
            new_head = (head[0] - 20, head[1])
        elif direction == 'RIGHT':
            new_head = (head[0] + 20, head[1])
        snake.insert(0, new_head)
        snake.pop()
        game['snake'] = snake

        # Check if the snake eats the food
        if game['food'] and new_head == game['food']:
            game['score'] += 10
    elif event['type'] == 'food':
        game['food'] = tuple(event['position'])


@app.route('/game')
def game():
    scores = HighScore.query.order_by(HighScore.score.desc()).limit(10).all()
    return render_template('game.html', scores=scores)

@app.route('/highscores', methods=['POST'])
def submit_score():
    name = request.form['name']
    score = int(request.form['score'])
    nonce = request.form['nonce']
    timestamp = int(request.form['timestamp'])

    secret_key = session.get('secret_key')
    session_nonce = session.get('nonce')

    if not secret_key or not session_nonce:
        return jsonify({'error': 'No secret key or nonce found'}), 400

    current_time = int(time.time())
    if abs(current_time - timestamp) > 60:  # Check if the timestamp is within the last 60 seconds
        return jsonify({'error': 'Timestamp is too old or too far in the future'}), 400

    message = f"{score}{session_nonce}{timestamp}"
    expected_hmac = hmac.new(secret_key.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected_hmac, nonce):
        return jsonify({'error': 'Invalid HMAC'}), 400

    new_score = HighScore(name=name, score=score)
    db.session.add(new_score)
    db.session.commit()

    return redirect(url_for('game'))

@app.route('/highscores', methods=['GET'])
def highscores():
    if request.method == 'POST':
        name = request.form['name']
        score = request.form['score']
        new_score = HighScore(name=name, score=score)
        db.session.add(new_score)
        db.session.commit()
        return redirect(url_for('game'))
    else:
        scores = HighScore.query.order_by(HighScore.score.desc()).limit(10).all()
        return render_template('highscores.html', scores=scores)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
