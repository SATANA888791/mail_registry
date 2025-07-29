import logging
from logging.handlers import RotatingFileHandler
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_principal import Principal
from werkzeug.exceptions import RequestEntityTooLarge



db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
principals = Principal()

def handle_large_file(e):
    from flask import request, flash, redirect
    flash('Файл слишком большой. Максимум 50 МБ.', 'danger')
    return redirect(request.url)

def create_app():
    app = Flask(__name__)
    app.config.from_object('app.config.Config')

    # 🔐 Проверка блокировки
    from flask_login import current_user, logout_user
    from flask import redirect, url_for, flash
    from datetime import datetime

    def is_user_blocked(user):
        now = datetime.utcnow()
        return (
            user.is_permanently_blocked or
            (user.blocked_until and user.blocked_until > now)
        )

    @app.before_request
    def check_user_block():
        if current_user.is_authenticated and is_user_blocked(current_user):
            logout_user()
            flash("🚫 Ваш аккаунт заблокирован.", "danger")
            return redirect(url_for("auth.login"))

    @app.before_request
    def update_last_active():
        if current_user.is_authenticated:
            from app import db  # импорт внутри функции, чтобы не было циклических зависимостей
            now = datetime.utcnow()
            if (
                not current_user.last_active_at or
                (now - current_user.last_active_at).total_seconds() > 1  # обновляем раз в минуту
            ):
                current_user.last_active_at = now
                db.session.commit()

    app.register_error_handler(RequestEntityTooLarge, handle_large_file)

    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)
    login.login_view = 'auth.login'  # 👈 маршрут, куда перенаправлять
    login.login_message = '⛔ Вы не авторизованы. Пожалуйста, войдите в систему.'
    login.login_message_category = 'warning'  # Bootstrap alert-warning

    principals.init_app(app)
    
    if not os.path.exists('logs'):
        os.mkdir('logs')

    file_handler = RotatingFileHandler('logs/app.log', maxBytes=500000, backupCount=3)
    file_handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s in %(module)s: %(message)s'))
    file_handler.setLevel(logging.INFO)

    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('📦 Приложение запущено')

    @app.template_filter('file_icon')
    def file_icon(filename):
        ext = filename.rsplit('.', 1)[-1].lower()
        icons = {
            'pdf': '📄',
            'doc': '📝', 'docx': '📝',
            'xls': '📊', 'xlsx': '📊',
            'jpg': '🖼️', 'jpeg': '🖼️', 'png': '🖼️', 'gif': '🖼️',
            'zip': '🗜️', 'rar': '🗜️',
            'txt': '📑',
        }
        return icons.get(ext, '📁')
    
    @app.template_filter('prepend_dot')
    def prepend_dot(values):
        return ','.join(f'.{ext}' for ext in values)


    # Регистрация блюпринтов
    from app.routes.auth import auth_bp
    from app.routes.outgoing import outgoing_bp
    from app.routes.incoming import incoming_bp
    from app.routes.my_letters import my_letters_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(auth_bp,    url_prefix='/auth')
    app.register_blueprint(outgoing_bp, url_prefix='/outgoing')
    app.register_blueprint(incoming_bp, url_prefix='/incoming')
    app.register_blueprint(my_letters_bp, url_prefix='/letters')
    app.register_blueprint(admin_bp,    url_prefix='/admin')

    return app


