import os
import logging
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET")

# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin_login'
login_manager.login_message = 'Будь ласка, увійдіть для доступу до цієї сторінки.'

# Configure Database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Schedule(db.Model):
    __tablename__ = 'schedules'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    lesson_number = db.Column(db.Integer, nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)

    group = db.relationship('Group', backref='schedules')
    subject = db.relationship('Subject', backref='schedules')

class Group(db.Model):
    __tablename__ = 'groups'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)

class Subject(db.Model):
    __tablename__ = 'subjects'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    schedules = Schedule.query.order_by(Schedule.date, Schedule.lesson_number).all()
    return render_template('index.html', schedules=schedules)

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Будь ласка, введіть логін та пароль')
            return redirect(url_for('admin_login'))

        logger.debug(f"Спроба входу користувача: {username}")

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            logger.debug(f"Успішний вхід користувача: {username}")
            return redirect(url_for('admin_dashboard'))

        logger.debug(f"Невдалий вхід користувача: {username}")
        flash('Неправильний логін або пароль')

    return render_template('admin/login.html')

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    groups = Group.query.all()
    subjects = Subject.query.all()
    schedules = Schedule.query.all()
    return render_template('admin/dashboard.html', 
                         groups=groups,
                         subjects=subjects,
                         schedules=schedules)

@app.route('/admin/logout')
@login_required
def admin_logout():
    logout_user()
    flash('Ви успішно вийшли з системи')
    return redirect(url_for('index'))

def init_db():
    with app.app_context():
        db.create_all()

        # Create admin user if not exists
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin')
            admin.set_password('root')
            db.session.add(admin)
            db.session.commit()
            logger.debug("Created admin user")

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)