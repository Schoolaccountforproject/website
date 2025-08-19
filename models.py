from datetime import datetime
from extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


# --- Association Tables ---
user_features = db.Table(
    'user_features',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('feature_id', db.Integer, db.ForeignKey('feature.id'), primary_key=True)
)

task_tags = db.Table(
    'task_tags',
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id', name='fk_task_tags_tag_id'), primary_key=True),
    db.Column('task_id', db.Integer, db.ForeignKey('task.id', name='fk_task_tags_tag_id'), primary_key=True)
)


# --- Models ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(25), unique=True, nullable=False)
    password_hash = db.Column(db.String(250), nullable=True)
    points = db.Column(db.Integer, default=0)
    email = db.Column(db.String(250), unique=True, nullable=True)

    tasks = db.relationship('Task', backref='user', lazy=True)
    purchased_features = db.relationship("Feature", secondary=user_features, backref='users')
    trivia_history = db.relationship('TriviaHistory', backref='user', lazy=True)
    trivia_streak = db.relationship('TriviaStreak', backref='user', uselist=False)
    trivia_freezers = db.Column(db.Integer, default=0)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task = db.Column(db.String(200), nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.now)
    due_date = db.Column(db.DateTime, nullable=True)
    completed = db.Column(db.Boolean, default=False)
    date_completed = db.Column(db.DateTime, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tags = db.relationship('Tag', secondary=task_tags, backref='tasks')
    reminder_sent_7 = db.Column(db.Boolean, default=False)
    reminder_sent_3 = db.Column(db.Boolean, default=False)
    reminder_sent_1 = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<Task {self.task}>'


class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f'<Tag {self.name}>'


class Feature(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(200), nullable=False)
    cost = db.Column(db.Integer, nullable=False)
    key = db.Column(db.String(50), unique=True, nullable=False)


class Messages(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref='messages')


class BlogComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('messages.id'), nullable=False)
    author = db.relationship('User', backref='blog_comments')
    post = db.relationship('Messages', backref='comments')


class TriviaHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    question = db.Column(db.Text, nullable=False)
    user_answer = db.Column(db.Text, nullable=False)
    correct_answer = db.Column(db.Text, nullable=False)
    was_correct = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.now)


class TriviaStreak(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True)
    current_streak = db.Column(db.Integer, default=0)
    max_streak = db.Column(db.Integer, default=0)
    daily_count = db.Column(db.Integer, default=0)
    last_played = db.Column(db.DateTime, default=datetime.now)


class UserConverterUnlock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    converter_type = db.Column(db.String(50), nullable=False)

    __table_args__ = (db.UniqueConstraint('user_id', 'converter_type', name='_user_converter_uc'),)
