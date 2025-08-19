# --- Imports ---
from flask import Flask, render_template, request, redirect, session, url_for, flash
from flask_migrate import Migrate
from flask_mail import Mail, Message
from flask_apscheduler import APScheduler
from authlib.integrations.flask_client import OAuth
from authlib.integrations.base_client import OAuthError
from flask_cors import CORS
import requests
from pint import UnitRegistry
import pycountry
import random
import os

from config import *
from tools.routes import json_bp
from models import *
from config import SQLALCHEMY_DATABASE_URI as default_db_uri


# --- Flask App Setup ---
app = Flask(__name__)
app.secret_key = SECRET_KEY
CORS(app)

# Register Blueprints
app.register_blueprint(json_bp)

# --- Extensions Initialization ---
ureg = UnitRegistry()

# OAuth setup
oauth = OAuth(app)
google = oauth.register(
    name="google",
    client_id=google_client_id,
    client_secret=google_client_secret,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid profile email"},
)


# Mail setup
mail = Mail(app)
app.config["MAIL_SERVER"] = MAIL_SERVER
app.config["MAIL_PORT"] = MAIL_PORT
app.config["MAIL_USERNAME"] = MAIL_USERNAME
app.config["MAIL_PASSWORD"] = MAIL_PASSWORD
app.config["MAIL_USE_SSL"] = MAIL_USE_SSL

# Database setup
db_url = os.getenv("DATABASE_URL", default_db_uri)
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = SQLALCHEMY_TRACK_MODIFICATIONS
db.init_app(app)
migrate = Migrate(app, db)

# APScheduler configuration
class Config:
    SCHEDULER_API_ENABLED = True

app.config.from_object(Config())
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()


# --- Helper Functions ---

def check():
    current_user = User.query.filter_by(username=session['username']).first()
    return current_user.points > 0




# --- Converter Questions ---
Converter_Questions = {
    "distance": {"question": "What is 1.2 kilometer in meters?", "answer": "1200"},
    "temperature": {"question": "What is 100 degrees Celsius in Fahrenheit?", "answer": "212"},
    "weight": {"question": "What is 500 grams in kilograms?", "answer": "0.5"},
    "volume": {"question": "What is 2 liters in milliliters?", "answer": "2000"},
    "time": {"question": "What is 7200 seconds in hours?", "answer": "2"},
    "speed": {"question": "What is 90 kilometers per hour in meters per second?", "answer": "25"},
    "area": {"question": "What is 100 square meters in square feet?", "answer": "1076.39"},
    "pressure": {"question": "What is 101325 pascals in atmospheres?", "answer": "1"},
    "energy": {"question": "What is 1000 joules in kilojoules?", "answer": "1"},
    "power": {"question": "What is 1000 watts in kilowatts?", "answer": "1"},
}


# --- API Integration: Unit Conversion ---
def convert_units_api_ninjas(amount, from_unit, to_unit):
    from_unit = from_unit.strip().lower().replace(" ", "_")
    to_unit = to_unit.strip().lower().replace(" ", "_")
    url = f"https://api.api-ninjas.com/v1/unitconversion?amount={amount}&unit={from_unit}"
    headers = {"X-Api-Key": API_NINJAS}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        conversions = data.get("conversions", {})
        if to_unit in conversions:
            return conversions[to_unit]
        else:
            print(f"Target unit '{to_unit}' not found in available conversions: {list(conversions.keys())}")
            return None
    else:
        print(f"API error {response.status_code}: {response.text}")
        return None


#Routes
@app.route('/')
def home():
    if "username" in session:
        return redirect(url_for('main'))
    return render_template('main structures/index.html')

#Login
@app.route("/login", methods=["POST"])
def login():
    #collect info from the forms
    username = request.form['username'] #this requests the username from the form attribute from the html
    password = request.form['password'] #samething here
    user = User.query.filter_by(username=username).first()
    #This line queries the db to find the user and filters by finding the username and .first() retrieves the first finding result
    if user and user.check_password(password): #if there is user and the password matches it returns True
        session['username'] = username
        flash("You've been successfully logged in")
        # stores the username inside session if it is authenticated
        return redirect(url_for('main'))
    else:
        flash("No account found")
        return render_template('main structures/index.html')

#Register
@app.route("/register", methods=["POST"])
def register():
    username = request.form['username'] #this requests the username from the form attribute from the html
    password = request.form['password']
    email = request.form.get('email', '').strip()  # Get email, empty string if not provided
    user = User.query.filter_by(username=username).first()
    #This line queries the db to find the user and filters by finding the username and .first() retrieves the first finding result
    if user: #If user is registered inside the db it returns true
        flash("Username already registered")
        return render_template("main structures/index.html")
    else:
        new_user = User(username=username) #This sets the username as the user using the class
        new_user.set_password(password) #Sets the password as the password
        if email:  # Only set email if provided
            new_user.email = email
        db.session.add(new_user) #This adds the user inside the db
        db.session.commit() #this commits the information
        session['username'] = username #Create a new session for this user, like using a dictionary
        return redirect(url_for('main'))# Returns the user to the main page

#Login for google
@app.route("/login/google")
def login_google():
    try:
        redirect_uri = url_for('authorize_google', _external=True)
        return google.authorize_redirect(redirect_uri)
    except Exception as e:
        app.logger.error(f"Error during login:{str(e)}")
        return "Error occurred during login", 500

@app.route("/authorize/google")
def authorize_google():
    try:
        token = google.authorize_access_token()
    except OAuthError as e:
        app.logger.warning(f"OAuthError: {e.error} - {e.description}")
        flash("Google login was cancelled or failed.")
        return redirect(url_for('home'))

    userinfo_endpoint = google.server_metadata['userinfo_endpoint']
    resp = google.get(userinfo_endpoint)
    user_info = resp.json()
    email = user_info['email']

    user = User.query.filter_by(email=email).first()
    if not user:
        username_base = email.split("@")[0][:20]
        unique_username = username_base
        counter = 1
        while User.query.filter_by(username=unique_username).first():
            unique_username = f"{username_base}{counter}"
            counter += 1
        user = User(username=unique_username, email=email)
        db.session.add(user)
        db.session.commit()

    session['username'] = user.username
    session['oauth_token'] = token

    return redirect(url_for('main'))


#Main page
@app.route('/main')
def main():
    if "username" in session:
        current_user = User.query.filter_by(username=session['username']).first()
        city, country_code, country_name, articles = "Unknown", "", "Unknown", []
        try:
            ip_response = requests.get(IP_API_URL)
            ip_data = ip_response.json()
            user_ip = ip_data.get("ip", "")
            print(f"User IP: {user_ip}")  # Debug log

            geo_response = requests.get(f"{GEO_API_URL}{user_ip}")
            geo_data = geo_response.json()
            print(f"Geolocation Data: {geo_data}")  # Debug log

            country_code = geo_data.get("countryCode", "")

            if country_code:
                country_obj = pycountry.countries.get(alpha_2=country_code)
                country_name = country_obj.name if country_obj else "Unknown"

                #Fetch local news based on country
                news_response = requests.get(NEWS_API_URL, params={
                    "country": country_code.lower(),
                    "token": NEWS_API_KEY,
                    "max": 3
                })
                news_data = news_response.json()
                print(f"News API Response: {news_data}")
                articles = news_data.get("articles", [])[:3]

        except requests.exceptions.RequestException as e:
            print(f"Error here with: {e}")
        return render_template("main structures/main.html", username=session['username'], user=current_user, country=country_name, articles=articles)
    return redirect(url_for('home'))

@app.route('/update-email', methods=["POST"])
def update_email():
    if "username" not in session:
        return redirect(url_for('home'))
    
    current_user = User.query.filter_by(username=session['username']).first()
    email = request.form.get('email', '').strip()
    
    if not email:
        flash("Please provide a valid email address")
        return redirect(url_for('main'))
    
    # Check if email is already taken by another user
    existing_user = User.query.filter_by(email=email).first()
    if existing_user and existing_user.id != current_user.id:
        flash("This email is already registered by another user")
        return redirect(url_for('main'))
    
    current_user.email = email
    db.session.commit()
    flash("Email updated successfully!")
    return redirect(url_for('main'))

@app.route('/logout', methods=["POST"])
def logout():
    #Just use the python function pop the user to get rid of the user from the session
    session.pop('username', None)
    flash("You have been logged out")
    return redirect(url_for('home'))



#Task Manager
@app.route('/task-manager', methods=["POST", "GET"])
def task_manager():
    # Handle POST requests (when the user submits a new task).
    if 'username' not in session:
        return redirect(url_for('home'))

    current_user = User.query.filter_by(username=session['username']).first()
    tags = Tag.query.filter_by(user_id=current_user.id).all()
    filtered_tasks = None
    searched_tasks = None

    if request.method == 'POST':

        if 'search_tags' in request.form:
            # Handle search by tags
            selected_tag_ids = request.form.getlist('search_tags') #getlist because search tags can have multiple values
            if selected_tag_ids:
                tasks = Task.query.filter_by(user=current_user, completed=False).all()
                filtered_tasks = [
                    task for task in tasks
                    if all(
                        any(tag.id == int(tag_id) for tag in task.tags)  # Check if the tag exists in the task's tags
                        for tag_id in selected_tag_ids  # Iterate over all selected tag IDs
                    )
                ]
            else:
                filtered_tasks = []
            tasks = Task.query.filter_by(user=current_user, completed=False).order_by(Task.date_created).all()
            return render_template("task manager/task_manager.html", user=current_user, tasks=tasks, tags=tags, datetime=datetime, filtered_tasks=filtered_tasks, searched_tasks=searched_tasks)

        elif 'task_name' in request.form:
            search_query = request.form.get('task_name', '').strip()
            if search_query:
                searched_tasks = Task.query.filter(
                    Task.user == current_user,
                    Task.task.ilike(f'%{search_query}%') # case insensitive search inside task column in Task class for search_query
                ).all()
            return render_template("task manager/task_manager.html", user=current_user, tasks=searched_tasks, tags=tags, datetime=datetime, filtered_tasks=filtered_tasks, searched_tasks=searched_tasks)

        elif 'task' in request.form:
            # Get the task content from the form submission.
            task_content = request.form['task']
            # Get the due date input from the form
            due_date_str = request.form.get('due_date')
            due_date = None

            if due_date_str:
                try:
                    # Convert string to datetime using the expected format
                    due_date = datetime.strptime(due_date_str, "%Y-%m-%dT%H:%M")
                except ValueError:
                    print("Invalid something going on here")

            # Create a new Task object with the submitted task content.
            new_task = Task(task=task_content, due_date=due_date, user=current_user)
            db.session.add(new_task)
            # Commit the changes to save the task in the database.
            db.session.commit()
            # Redirect the user back to the task manager page to see the updated task list.
            return redirect('/task-manager')

        elif 'task_reminder' in request.form:
            pass
        # If no valid form data is provided, return the task manager page.
        tasks = Task.query.filter_by(user=current_user, completed=False).order_by(Task.date_created).all()
        return render_template("task manager/task_manager.html", user=current_user, tasks=tasks, tags=tags, datetime=datetime)

    else:
        # Handle GET requests (when the user visits the task manager page).
        # Query all tasks from the database, ordered by the date they were created.
        tasks = Task.query.filter_by(user=current_user, completed=False).order_by(Task.date_created).all() #Grabs by oldest to newest
        tags = Tag.query.filter_by(user_id=current_user.id).all()
        # Render the task manager HTML template and pass the list of tasks to it.
        return render_template("task manager/task_manager.html", user=current_user, tasks=tasks, tags=tags, datetime=datetime)

@app.route('/delete/<int:id>')
def delete(id):
    # Attempt to retrieve the task from the database by its ID.
    # If the task does not exist, return a 404 error.
    current_user = User.query.filter_by(username=session['username']).first()
    task_to_delete = Task.query.get_or_404(id)
    if task_to_delete.user != current_user:
        return "Unauthorized", 403

    try:
        # Delete the retrieved task from the database session.
        db.session.delete(task_to_delete)
        # Commit the changes to remove the task from the database.
        db.session.commit()
        # Redirect the user back to the task manager page to see the updated task list.
        return redirect('/task-manager')
    except Exception as e:
        # If there is an issue with deleting the task, return an error message.
        return 'You did something wrong, correct it'

@app.route('/update/<int:id>', methods=["GET", "POST"])
#The route accepts a task id as a url parameter
def update(id):
    if "username" not in session:
        return redirect(url_for('home'))

    current_user = User.query.filter_by(username=session['username']).first()
    task = Task.query.get_or_404(id)

    if task.user != current_user:
        return "Unauthorized", 403

    if request.method == 'POST':
        # Update the task's content with the new value submitted in the form.
        task.task = request.form['task']
        try:
            db.session.commit()
            return redirect('/task-manager')
        except:
            return "Issue here"
    else:
        return render_template('task manager/update.html', task=task)

@app.route('/complete/<int:id>')
def complete(id):
    if "username" not in session:
        return redirect(url_for('home'))

    current_user = User.query.filter_by(username=session['username']).first()
    task = Task.query.get_or_404(id)

    if task.user != current_user:
        return "Unauthorized", 403

    try:
        task.completed = True
        task.date_completed = datetime.now()
        #This marks the task as completed and sets the date completed to now

        elapsed_time = task.date_completed - task.date_created
        elapsed_hours = elapsed_time.total_seconds() // 3600

        #Calculates the points based on the time spent

        if elapsed_hours >= 4:
            points_earned = int(elapsed_hours // 2)
        else:
            points_earned = 0

        current_user.points += points_earned

        db.session.commit()
        return redirect('/task-manager')
    except Exception as e:
        print(f"Error: {e}")
        return "There was an issue marking the task as complete."

@app.route('/archived-tasks')
def archived_tasks():
    if "username" not in session:
        return redirect(url_for('home'))

    current_user = User.query.filter_by(username=session['username']).first()
    tasks = Task.query.filter_by(user=current_user, completed=True).order_by(Task.date_completed).all()

    return render_template('task manager/archive.html', tasks=tasks)

@app.route('/create-tag', methods=['POST', 'GET'])
def create_tag():
    if 'username' not in session:
        return redirect(url_for('home'))

    current_user = User.query.filter_by(username=session['username']).first()
    add_tag_feature = Feature.query.filter_by(key="add_tags").first()

    # Checks if the add tag feature is in the purchased feature or not, if not it flashes
    if add_tag_feature not in current_user.purchased_features:
        flash("Purhcase the feature first you poor ahh dumb bum", "feature-add_tag")
        return redirect(url_for('shop'))

    if request.method == 'POST':
        tag_name = request.form.get('tag_name').strip()

        #If the user has enough points or not
        if current_user.points < 1:
            flash("Not enough points u poor ahh soul", "feature-add_tag")
            return redirect(url_for('task_manager'))

        #This code checks if the new tag has already been added inside the Tag database
        exist_or_not = Tag.query.filter_by(name=tag_name, user_id=current_user.id).first()

        if exist_or_not:
            flash("You already have this tag, I don't even know what to say, ur just dumb", "feature-add_tag")
            return redirect(url_for('task_manager'))

        current_user.points -= 1
        new_tag = Tag(name=tag_name, user_id = current_user.id)

        db.session.add(new_tag)
        db.session.commit()
        print("Tag created")

        flash(f"Tag '{tag_name}' has been added", "tag_added")

    return redirect(url_for('task_manager'))

@app.route('/delete-tag/', methods=['POST'])
def delete_tag():
    if 'username' not in session:
        return redirect(url_for('home'))
    current_user = User.query.filter_by(username=session['username']).first()
    tag_id = int(request.form['tag_id'])
    tag = Tag.query.get_or_404(tag_id)
    if tag.user_id != current_user.id:
        return "Unauthorized", 403

    db.session.delete(tag)
    db.session.commit()
    flash(f"Tag '{tag.name}' has been deleted", "tag_deleted")
    return redirect(url_for('task_manager'))

@app.route('/add-tag-to-task/<int:task_id>', methods=['POST'])
def add_tag_to_task(task_id):
    if 'username' not in session:
        return redirect(url_for('home'))
    current_user = User.query.filter_by(username=session['username']).first()
    task = Task.query.get_or_404(task_id)
    if task.user != current_user:
        return "Unauthorized", 403

    tag_id = int(request.form['tag_id'])
    tag = Tag.query.get_or_404(tag_id)
    if tag not in task.tags:
        task.tags.append(tag)
        db.session.commit()
    return redirect(url_for('task_manager'))

@app.route('/remove-tag-from-task/<int:task_id>/<int:tag_id>', methods=['POST'])
def remove_tag_from_task(task_id, tag_id):
    if 'username' not in session:
        return redirect(url_for('home'))
    current_user = User.query.filter_by(username=session['username']).first()
    task = Task.query.get_or_404(task_id)
    if task.user != current_user:
        return "Unauthorized", 403

    tag = Tag.query.get_or_404(tag_id)
    if tag in task.tags:
        task.tags.remove(tag)
        db.session.commit()
    return redirect(url_for('update', id=task_id))

#Scheduler for reminders
@scheduler.task('interval', id='send_reminders', hours=24)#Sets the interval to 24 hours to run the function
def send_reminders():
    #Makes sure flask has access to the db to use it
    with app.app_context(): #Makes sure the app context is available for db access
        now = datetime.now()
        all_tasks = Task.query.filter_by(completed=False).all()
        
        # Get the task reminders feature once
        task_reminders = Feature.query.filter_by(key="task_reminders").first()
        
        for task in all_tasks:
            # Check if this task's user has the reminder feature
            if task_reminders not in task.user.purchased_features:
                continue
                
            if not task.due_date or not task.user.email:
                #Skips tasks with no due date or no email
                continue

            days_until_due = (task.due_date - now).days
            hours_until_due = (task.due_date - now).total_seconds() // 3600

            #User that owns the task
            user = task.user
            #Email of the user
            recipient = user.email

            #If the task is due in 7 days and you haven't sent this reminder yet
            if days_until_due == 7 and not task.reminder_sent_7:
                try:
                    send_reminder_email(user.username, recipient, task.task, task.due_date, 7)
                    task.reminder_sent_7 = True
                except Exception as e:
                    print(f"Failed to send 7-day reminder for task {task.id}: {e}")

            elif days_until_due == 3 and not task.reminder_sent_3:
                try:
                    send_reminder_email(user.username, recipient, task.task, task.due_date, 3)
                    task.reminder_sent_3 = True
                except Exception as e:
                    print(f"Failed to send 3-day reminder for task {task.id}: {e}")

            elif hours_until_due <= 24 and not task.reminder_sent_1:
                try:
                    send_reminder_email(user.username, recipient, task.task, task.due_date, 1)
                    task.reminder_sent_1 = True
                except Exception as e:
                    print(f"Failed to send 1-day reminder for task {task.id}: {e}")

        db.session.commit()

def send_reminder_email(username, to_email, task_name, due_date, days_left):
    subject = f"Reminder: '{task_name}' is due in {days_left} day(s)"
    body = f"""
    Hey {username},

    This is a reminder that your task '{task_name}' is due on {due_date.strftime('%Y-%m-%d %H:%M')}.

    Keep using my website! 

    - Task Manager Bot
    """
    msg = Message(
        subject=subject,
        sender=app.config['MAIL_USERNAME'],
        recipients=[to_email],
        body=body
    )
    mail.send(msg)

#Unit Converter
@app.route('/unit-converter', methods=['GET', 'POST'])
def unit_converter():
    if "username" not in session:
        return redirect(url_for('home'))
    current_user = User.query.filter_by(username=session['username']).first()
    converter_types = ["distance", "temperature", "weight", "volume", "time", "speed", "area", "pressure", "energy", "power"]
    unlocked = {c.converter_type for c in UserConverterUnlock.query.filter_by(user_id=current_user.id).all()}
    selected_type = request.form.get('selected_type') or request.args.get('type')
    result = error = None #By default result and error are None so it does not show any errors or results

    if request.method == 'POST':
        if not check():
            flash("You do not have enough points to enter this feature", "point_error")
            return redirect(url_for('main'))
        if 'unlock_type' in request.form:
            unlock_type = request.form['unlock_type']
            user_answer = request.form.get('answer', '').strip()
            correct_answer = Converter_Questions[unlock_type]['answer']
            if user_answer == correct_answer:
                db.session.add(UserConverterUnlock(user_id=current_user.id, converter_type=unlock_type))
                db.session.commit()
                flash(f"{unlock_type.capitalize()} converter unlocked!")
                unlocked.add(unlock_type)
                current_user.points -= 1
                db.session.commit()
            else:
                flash("Incorrect answer. Try again. Also, it deducts one point when you answer it incorrectly hehe. Also, I didn't add JS so that's why it reloads everytime.", "error")
                current_user.points -= 1
                db.session.commit()
        elif 'converter_type' in request.form:
            converter_type = request.form['converter_type']
            if converter_type in unlocked:
                try:
                    value = float(request.form['value'])
                    from_unit = request.form['from_unit']
                    to_unit = request.form['to_unit']
                    converted = convert_units_api_ninjas(value, from_unit, to_unit)
                    if converted is not None:
                        result = f"{value} {from_unit} is equal to {converted} {to_unit}"
                    else:
                        error = "Conversion failed. Please check the units and try again."
                except ValueError:
                    error = "Invalid input. Please enter a number."
            else:
                error = "You need to unlock this converter first by answering the question!"
    return render_template('tools/unit_converter.html', user=current_user, converter_types=converter_types, selected_type=selected_type, questions=Converter_Questions, result=result, error=error, unlocked=unlocked)

#Blog
@app.route('/blog', methods=['GET', 'POST'])
def blog():
    if "username" not in session:
        return redirect(url_for('home'))

    current_user = User.query.filter_by(username=session['username']).first()

    if request.method == 'POST':
        content = request.form.get('content')
        if 'comment_content' in request.form:
            comment_content = request.form.get('comment_content')
            post_id = request.form.get('post_id')
            if comment_content and post_id:
                new_comment = BlogComment(
                    content=comment_content.strip(),
                    author=current_user,
                    post_id=int(post_id)
                )
                db.session.add(new_comment)
                db.session.commit()
                return redirect(url_for('blog'))

        elif 'content' in request.form:
            if content:
                new_msg = Messages(content=content.strip(), user=current_user)
                if check():
                    current_user.points -= 1
                    db.session.add(new_msg)
                    db.session.commit()
                    return redirect(url_for('blog'))
                else:
                    flash("You do not have enough points to post a message", "purchase_error")
                    return redirect(url_for('blog'))


    messages = Messages.query.order_by(Messages.timestamp.desc()).all() #Descending order first
    return render_template("blog.html", user=current_user, messages=messages)


#Random stuff
@app.route('/cat', methods=['GET', 'POST'])
def cat():
    cat_fact = "Click the button to learn something about cats!"
    if request.method == 'POST':
        cat_facts_url = "https://catfact.ninja/fact"
        response = requests.get(cat_facts_url)
        if response.status_code == 200: #if the request was successful
            cat_fact = response.json()["fact"] #This gets the json data from the request and gets the fact key
        else:
            cat_fact = "Could not fetch cat facts at the moment. Please try again later."
    return render_template('cat.html', cat_fact=cat_fact)

#Add the feature that users are allowed to add their own cat facts

#Currency Exchange
@app.route('/currency', methods=['GET', 'POST'])
def currency_rate():
    exchange_data = None
    error = None

    if request.method == 'POST':
        base_currency = request.form['base_currency']
        target_currency = request.form['target_currency']
        amount = float(request.form['amount'])  # Amount of base currency
        url = f"https://v6.exchangerate-api.com/v6/134c221bed30d8402bb59b76/latest/{base_currency}"

        try:
            response = requests.get(url)
            if response.status_code == 200:
                rates = response.json()
                if target_currency in rates["conversion_rates"]:
                    target_rate = rates["conversion_rates"][target_currency]
                    calculated_amount = round(amount * target_rate, 2)  # Calculate the exchanged amount
                    exchange_data = {
                        "base": base_currency,
                        "target": target_currency,
                        "rate": target_rate,
                        "amount": amount,
                        "calculated_amount": calculated_amount
                    }
                else:
                    error = f"Currency '{target_currency}' not found in exchange rates!"
            else:
                error = "Failed to grab the information, check ur API."
        except requests.exceptions.RequestException as e:
            error = "Currency exchange service is unavailable"
    return render_template('currency.html', exchange_data=exchange_data, error=error)


@app.route('/zhongyan')
def zhongyan():
    if "username" in session:
        current_user = User.query.filter_by(username=session['username']).first()
    return render_template('zhongyan.html', user=current_user)


@app.route('/shop')
def shop():
    if "username" not in session:
        return redirect(url_for('home'))

    current_user = User.query.filter_by(username=session['username']).first()
    features = Feature.query.all()
    return render_template('shop.html', username=session['username'], user=current_user, features = features)

@app.route('/purchase-feature/<int:feature_id>', methods=["POST"])
def purchase_feature(feature_id):
    if "username" not in session:
        return redirect(url_for('home'))

    current_user = User.query.filter_by(username=session['username']).first()
    feature = Feature.query.get_or_404(feature_id)

    if feature.key == "trivia_freezer":
        if current_user.points >= feature.cost:
            current_user.points -= feature.cost
            current_user.trivia_freezers += 1
            db.session.commit()
            flash(f"You bought a Trivia Freezer! You now have {current_user.trivia_freezers}.", f"feature-{feature.id}")
        else:
            flash("Not enough points to buy a Trivia Freezer!", f"feature-{feature.id}")
        return redirect(url_for('shop'))

    # Check if user is trying to purchase Task Reminder without email
    if feature.key == "task_reminder" and not current_user.email:
        flash("You need to add an email address to your account before purchasing Task Reminder. Please add your email in the main dashboard.", f"feature-{feature.id}")
        return redirect(url_for('shop'))

    if feature in current_user.purchased_features:
        flash("You already have this feature")
        return redirect(url_for('shop'))

    if current_user.points >= feature.cost:
        current_user.points -= feature.cost
        current_user.purchased_features.append(feature)
        db.session.commit()
        flash(f"You successfully purchased the feature: {feature.name}", f"feature-{feature.id}")
    else:
        flash(f"You dummy ahh don't have enough points to purchase the feature: {feature.name}", f"feature-{feature.id}")

    return redirect(url_for('shop'))

def reward_random_feature():
    user = User.query.filter_by(username=session['username']).first()
    owned_ids = {f.id for f in user.purchased_features}
    all_features = Feature.query.all()
    available = [f for f in all_features if f.id not in owned_ids]
    if available:
        selected = random.choice(available)
        user.purchased_features.append(selected)
        flash(f"Congrats! You unlocked a free feature: {selected.name}")
        db.session.commit()

def reward_points(streak):
    if streak == 3:
        return 3
    elif streak == 10:
        return 15
    elif streak == 20:
        return 30
    elif streak == 100:
        reward_random_feature()
        return 0
    return 1

@app.route('/trivia', methods=['GET', 'POST'])
def trivia():
    if "username" not in session:
        return redirect(url_for('home'))

    user = User.query.filter_by(username=session['username']).first()
    streak = TriviaStreak.query.filter_by(user_id=user.id).first()
    if not streak:
        streak = TriviaStreak(user_id=user.id)
        db.session.add(streak)
        db.session.commit()

    now = datetime.now()
    if streak.last_played.date() != now.date():
        streak.daily_count = 0
        streak.last_played = now
        db.session.commit()

    if streak.daily_count >= 10:
        redirect(url_for('main'))

    if request.method == 'POST':
        user_answer = request.form.get('answer', '').strip()
        correct_answer = session.get('correct_answer')
        question = session.get('question')

        was_correct = user_answer.lower() == correct_answer.lower()
        history = TriviaHistory(
            user_id=user.id,
            question=question,
            user_answer=user_answer,
            correct_answer=correct_answer,
            was_correct=was_correct
        )
        db.session.add(history)
        streak.daily_count += 1
        streak.last_played = now

        if was_correct:
            streak.current_streak += 1
            user.points += reward_points(streak.current_streak)
            streak.max_streak = max(streak.max_streak, streak.current_streak)
            feedback = f"Correct! +1 point"
        else:
            user.points = max(user.points - 1, 0)
            if user.trivia_freezers > 0:
                user.trivia_freezers -= 1
                feedback = f"Wrong! But your Trivia Freezer saved your streak. ({user.trivia_freezers} left)"
            else:
                streak.current_streak = 0
                feedback = f"Wrong. The correct answer was: {correct_answer}. -1 point"
        db.session.commit()



        return render_template(
            "trivia/trivia.html",
            feedback=feedback,
            question_data=None,
            user=user,
            streak=streak
        )

    MAX_TRIES = 3
    question_data = None

    for _ in range(MAX_TRIES):
        trivia_response = requests.get("https://opentdb.com/api.php?amount=1&type=multiple")
        data = trivia_response.json()
        print("TRIVIA API RESPONSE:", data)

        if data.get("response_code") == 0 and data.get("results"):
            q = data["results"][0]
            question = q["question"]
            correct_answer = q["correct_answer"]
            choices = q["incorrect_answers"] + [correct_answer]
            random.shuffle(choices)

            session['correct_answer'] = correct_answer
            session['question'] = question

            question_data = {
                "question": question,
                "choices": choices,
                "correct_answer": correct_answer
            }
            break

    if not question_data:
        flash("Trivia question not available. Try again later.", "error")
        return redirect(url_for('main'))

    return render_template("trivia/trivia.html", question_data=question_data, user=user, streak=streak)


@app.route('/trivia-leaderboard')
def trivia_leaderboard():
    top_users = (
        db.session.query(User.username, TriviaStreak.max_streak)
        .join(TriviaStreak)
        .order_by(TriviaStreak.max_streak.desc())
        .limit(10)
        .all()
    )
    return render_template("trivia/trivia_leaderboard.html", top_users=top_users)

@app.route('/trivia-history')
def trivia_history():
    user = User.query.filter_by(username=session['username']).first()
    history = TriviaHistory.query.filter_by(user_id=user.id).order_by(TriviaHistory.timestamp.desc()).all()
    return render_template('trivia/trivia_history.html', history=history)


with app.app_context():
    features = [
        Feature(name="Update Task", description="Unlock the ability to update task names.", cost=100, key="update_task"),
        Feature(name="Tags", description="You can add tags to your tasks.", cost=250, key="add_tags"),
        Feature(name="Task Reminder", description="Sends you emails to remind you of tasks.", cost=500, key="task_reminder"),
        Feature(name="Blog", description="You can now talk to people!", cost=100, key="blog"),
        Feature(name="Dark Mode", description="You can now use Dark Mode in dashboard!", cost=50, key="dark_mode"),
        Feature(name="Trivia Freezer", description="Protects your trivia streak from breaking once.", cost=100, key="trivia_freezer")
    ]

    for feat in features:
        if not Feature.query.filter_by(key=feat.key).first():
            db.session.add(feat)

    for user in User.query.all():
        if user.trivia_streak is None:
            new_streak = TriviaStreak(
                user_id=user.id,
                current_streak=0,
                max_streak=0,
                daily_count=0,
                last_played=datetime.now()
            )
            db.session.add(new_streak)
            user.trivia_streak = new_streak  # associate it with the user
        else:
            user.trivia_streak.current_streak = 0
            user.trivia_streak.max_streak = 0
            user.trivia_streak.daily_count = 0
            user.trivia_streak.last_played = datetime.now()

    db.session.commit()
    print("Database updated with features!")

if __name__ in '__main__':
    with app.app_context():
        db.create_all()
    app.run(port=5001)
