from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

from app import db
from app.models import User, Role
from app.forms import LoginForm
from app.models import LoginAttempt


auth_bp = Blueprint('auth', __name__, template_folder='../templates/auth')

# Страница, маршрут логина
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('my_letters.outgoing_list'))

    form = LoginForm()
    ip = request.remote_addr
    session['login_attempts'] = session.get('login_attempts', 0)
    current_attempts = session['login_attempts']

    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        attempt = LoginAttempt(
            username=form.username.data,
            ip_address=ip,
            user_id=user.id if user else None,
            successful=False
        )
        db.session.add(attempt)

        if not user:
            session['login_attempts'] = current_attempts + 1
            current_app.logger.warning(
                f'👻 Попытка {current_attempts+1} - Несуществующий пользователь: {form.username.data}, IP: {ip}'
            )
            flash('❌ Неверное имя пользователя или пароль.', 'danger')
            db.session.commit()
        else:
            # Проверка блокировки с использованием нового статуса
            if user.login_block_status == 'permanent':
                flash('⛔ Ваш аккаунт заблокирован. Обратитесь к администратору.', 'danger')
                db.session.commit()
                return render_template('auth/login.html', form=form)

            if user.login_block_status == 'temporary':
                remaining = max(1, user.remaining_block_time)
                flash(f'🕒 Слишком много попыток. Повторите через {remaining} мин.', 'warning')
                db.session.commit()
                return render_template('auth/login.html', form=form)

            if user.check_password(form.password.data):
                attempt.successful = True
                login_user(user, remember=form.remember.data)
                session['login_attempts'] = 0
                
                # Сброс счетчика неудачных попыток при успешном входе
                user.last_failed_attempt = None
                
                current_app.logger.info(
                    f'🔑 Успех после {current_attempts+1} попыток | {user.username} | IP: {ip}'
                )
                flash(f'{user.get_greeting()} {user.role_emoji} {user.display_name}!', 'success')
                db.session.commit()
                return redirect(url_for('my_letters.outgoing_list'))

            # Обработка неудачной попытки входа
            session['login_attempts'] = current_attempts + 1
            current_attempts += 1
            
            current_app.logger.warning(
                f'⚠️ Попытка {current_attempts} - Неверный пароль | {user.username} | IP: {ip}'
            )
            
            # Применение расширенной политики безопасности
            user.apply_login_security_policy(current_attempts)
            db.session.commit()

            # Дополнительное предупреждение при критических попытках
            if current_attempts >= 5:
                current_app.logger.error(
                    f'🕵️ Превышение лимита: {current_attempts} попыток | {user.username} | IP: {ip}'
                )
                flash('📛 Превышен лимит попыток. Доступ временно ограничен.', 'danger')

    return render_template('auth/login.html', form=form)

# Страница, маршрут выхода
@auth_bp.route('/logout')
@login_required
def logout():
    ip = request.remote_addr  # 🛜 Получаем IP пользователя
    current_app.logger.info(f'🔑 Пользователь {current_user.username}, IP: {ip} вышел из системы')
    logout_user()
    flash('Вы вышли из системы.', 'info')
    
    return redirect(url_for('auth.login'))


# @auth_bp.route('/register', methods=['GET', 'POST'])
# def register():
#     form = RegisterForm()
#     if form.validate_on_submit():
#         # Найти роль по умолчанию (editor)
#         role = Role.query.filter_by(name='editor').first()
#         user = User(
#             username=form.username.data,
#             email=form.email.data,
#             password_hash=generate_password_hash(form.password.data),
#             role=role
#         )
#         db.session.add(user)
#         db.session.commit()
#         flash('Регистрация прошла успешно. Войдите в систему.', 'success')
#         return redirect(url_for('auth.login'))
#     return render_template('auth/register.html', form=form)

# Страница, маршрут управления пользователями
