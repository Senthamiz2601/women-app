import multiprocessing
from multiprocessing.connection import Client
from flask import Flask, render_template, request, redirect, session, jsonify
from flask_mail import Mail, Message
import sqlite3
from geopy.distance import geodesic
import time
from transformers import GPT2LMHeadModel, GPT2Tokenizer


app = Flask(__name__)
app.secret_key = 'your_secret_key'

tokenizer = GPT2Tokenizer.from_pretrained("gpt2")
model = GPT2LMHeadModel.from_pretrained("gpt2")

# Flask-Mail Configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'daminmain@gmail.com'  # Update with your email
app.config['MAIL_PASSWORD'] = 'kpqtxqskedcykwjz'    # Use an app-specific password if necessary
mail = Mail(app)

# Database connection function
def get_db_connection():
    conn = sqlite3.connect('women_safety.db')
    conn.row_factory = sqlite3.Row
    return conn



# Initialize database
def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            password TEXT,
            mobile TEXT,
            additional_email1 TEXT,
            additional_email2 TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            latitude REAL,
            longitude REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    conn.commit()
    conn.close()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/safety_Measures')
def safety():
    return render_template('vedio.html')


def generate_response(prompt):
    """
    Function to get GPT-2 generated response for a given prompt.
    """
    # Encode input prompt
    inputs = tokenizer.encode(prompt, return_tensors="pt")

    # Generate output from the model
    outputs = model.generate(inputs, max_length=150, num_return_sequences=1, no_repeat_ngram_size=2, top_k=50, top_p=0.95)

    # Decode the output text
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    
    # Return the generated response, trimming the prompt part
    return response[len(prompt):].strip()

@app.route("/chat", methods=["POST"])
def chat():
    """
    Endpoint for chatbot interaction.
    """
    user_input = request.json.get("message", "")
    category = request.json.get("category", "general")

    # Generate prompts based on categories
    if category == "safety_tips":
        prompt = f"Provide practical women safety tips based on {user_input}."
    elif category == "laws":
        prompt = f"Explain women safety laws or legal rights in relation to: {user_input}."
    elif category == "motivation":
        prompt = f"Share an inspirational message or motivational content for women about: {user_input}."
    else:
        prompt = f"Provide useful information related to women safety, laws, or motivation based on: {user_input}."

    # Get GPT-2 generated response
    bot_response = generate_response(prompt)
    return jsonify({"response": bot_response})

@app.route("/chat1", methods=["GET", "POST"])
def index():
    """
    Index route to display the input form and handle user input.
    """
    if request.method == "POST":
        user_input = request.form.get("message", "")
        category = request.form.get("category", "general")

        # Generate prompts based on categories
        if category == "safety_tips":
            prompt = f"Provide practical women safety tips based on {user_input}."
        elif category == "laws":
            prompt = f"Explain women safety laws or legal rights in relation to: {user_input}."
        elif category == "motivation":
            prompt = f"Share an inspirational message or motivational content for women about: {user_input}."
        else:
            prompt = f"Provide useful information related to women safety, laws, or motivation based on: {user_input}."

        # Get GPT-2 generated response
        bot_response = generate_response(prompt)
        return render_template("chat.html", response=bot_response)

    return render_template("chat.html", response=None)



@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        mobile = request.form['mobile']
        additional_email1 = request.form['additional_email1']
        additional_email2 = request.form['additional_email2']

        conn = get_db_connection()
        try:
            conn.execute(
                'INSERT INTO users (name, email, password, mobile, additional_email1, additional_email2) VALUES (?, ?, ?, ?, ?, ?)',
                (name, email, password, mobile, additional_email1, additional_email2)
            )
            conn.commit()
            conn.close()
            return redirect('/login')
        except sqlite3.IntegrityError:
            conn.close()
            return 'Email already exists!'
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ? AND password = ?', (email, password)).fetchone()
        conn.close()

        if user:
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            return redirect('/dashboard')
        else:
            return 'Invalid credentials!'
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('dashboard.html', name=session['user_name'])

@app.route('/update_location', methods=['POST'])
def update_location():
    if 'user_id' in session:
        data = request.get_json()
        latitude = data['latitude']
        longitude = data['longitude']
        user_id = session['user_id']

        conn = get_db_connection()
        conn.execute(
            'INSERT INTO locations (user_id, latitude, longitude) VALUES (?, ?, ?)',
            (user_id, latitude, longitude)
        )
        conn.commit()
        conn.close()
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error'}), 401

@app.route('/help', methods=['POST'])
def help():
    if 'user_id' in session:
        user_id = session['user_id']
        conn = get_db_connection()

        # Get the latest location of the requesting user
        user_location = conn.execute(
            'SELECT latitude, longitude FROM locations WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1',
            (user_id,)
        ).fetchone()

        if user_location:
            latitude = user_location['latitude']
            longitude = user_location['longitude']
            users = conn.execute('SELECT * FROM locations').fetchall()
            nearby_users = []

            for user in users:
                if user['user_id'] != user_id:
                    distance = geodesic(
                        (latitude, longitude),
                        (user['latitude'], user['longitude'])
                    ).km
                    if distance <= 2:
                        nearby_users.append(user['user_id'])

            # Get emails of nearby users
            nearby_emails = []
            for uid in nearby_users:
                email_result = conn.execute('SELECT email FROM users WHERE id = ?', (uid,)).fetchone()
                if email_result:
                    nearby_emails.append(email_result['email'])

            # Get additional emails for the current user
            additional_emails = []
            additional_email1 = conn.execute('SELECT additional_email1 FROM users WHERE id = ?', (user_id,)).fetchone()
            additional_email2 = conn.execute('SELECT additional_email2 FROM users WHERE id = ?', (user_id,)).fetchone()
            if additional_email1 and additional_email1['additional_email1']:
                additional_emails.append(additional_email1['additional_email1'])
            if additional_email2 and additional_email2['additional_email2']:
                additional_emails.append(additional_email2['additional_email2'])

            # Admin email (hardcoded)
            admin_email = 'pro56work@gmail.com'

            # Construct the Google Maps URL
            google_maps_url = f"https://www.google.com/maps?q={latitude},{longitude}"

            # Email body with a clickable link to Google Maps
            message_body = (
                f'A user needs help! Location: ({latitude}, {longitude}).\n'
                f'Click here to view the location on Google Maps: {google_maps_url}'
            )

            # Send email to nearby users and additional emails
            all_emails = nearby_emails + additional_emails
            if all_emails:
                msg_to_nearby = Message(
                    'Help Alert',
                    sender='your_email@example.com',  # Replace with your email
                    recipients=all_emails
                )
                msg_to_nearby.body = message_body
                mail.send(msg_to_nearby)

            # Send email to admin
            msg_to_admin = Message(
                'Admin Alert: Help Request',
                sender='your_email@example.com',  # Replace with your email
                recipients=[admin_email]
            )
            msg_to_admin.body = f'User ID {user_id} requested help. {message_body}'
            mail.send(msg_to_admin)

        conn.close()
        return jsonify({'status': 'alert_sent'})
    return jsonify({'status': 'error'}), 401


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == 'admin' and password == '1234':
            conn = get_db_connection()
            locations = conn.execute('SELECT * FROM locations').fetchall()
            conn.close()
            return render_template('admin.html', locations=locations)
    return render_template('admin_login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
