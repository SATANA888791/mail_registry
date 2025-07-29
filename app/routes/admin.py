from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user, logout_user
from werkzeug.security import generate_password_hash
from app import db
from app.models import User, Role, LetterOutgoing, LetterIncoming, UserBlockHistory
from app.forms import AdminUserForm
from datetime import datetime, timedelta
from sqlalchemy import or_, and_, func, extract
from sqlalchemy.sql import text
from app.decorators import admin_required


admin_bp = Blueprint(
    'admin', __name__,
    template_folder='../templates/admin'
)


def is_user_online(user, minutes=5):
    if not user.last_active_at:
        return False
    return user.last_active_at > datetime.utcnow() - timedelta(minutes=minutes)

def get_dashboard_stats():
    now = datetime.utcnow()
    current_year = now.year % 100  # 25 для 2025 года

    try:
        # Для исходящих писем
        # Получаем максимальный номер из поля number
        max_outgoing_num = db.session.execute(
            text("""
                SELECT MAX(CAST(SUBSTRING(number FROM 3 FOR POSITION('/' IN number)-3) AS INTEGER))
                FROM letter_outgoing 
                WHERE number LIKE 'H-%/%' AND SUBSTRING(number FROM POSITION('/' IN number)+1) = :year
            """), {'year': str(current_year)}
        ).scalar() or 0
        
        # Устанавливаем последовательность
        db.session.execute(
            text("SELECT setval('outgoing_number_seq', :val, true)"),
            {'val': max_outgoing_num + 1}
        )
        
        # Получаем следующий номер
        next_outgoing = db.session.execute(
            text("SELECT nextval('outgoing_number_seq')")
        ).scalar()
        
        outgoing_number = f"H-{next_outgoing}/{current_year}"

        # Для входящих писем
        max_incoming_num = db.session.execute(
            text("""
                SELECT MAX(sequence_num)
                FROM letter_incoming
                WHERE year = :year
         """), {'year': current_year}
        ).scalar() or 0

        db.session.execute(
            text("SELECT setval('incoming_number_seq', :val, true)"),
            {'val': max_incoming_num + 1}
        )
        
        next_incoming = db.session.execute(
            text("SELECT nextval('incoming_number_seq')")
        ).scalar()
        incoming_number = f"ВХ-{next_incoming}/{current_year}"
        
        stats = {
            'next_outgoing': outgoing_number,
            'next_incoming': incoming_number,
            # ... остальная статистика ...
        }
        
        return stats

    except Exception as e:
        current_app.logger.error(f"Ошибка при получении статистики: {str(e)}")
        return {
            'next_outgoing': f'H-0/{current_year}',
            'next_incoming': f'ВХ-0/{current_year}',
            # ... значения по умолчанию ...
        }

def get_recent_logs(limit=20):
    logs = (
        UserBlockHistory.query
        .order_by(UserBlockHistory.timestamp.desc())
        .limit(limit)
        .all()
    )


    result = []
    for log in logs:
        time_str = log.timestamp.strftime('%H:%M %d.%m.%Y')
        actor = log.admin.username if log.admin else '—'
        target = log.user.username if log.user else '—'

        if log.action == 'unblock':
            action_text = f'разблокировал(а) {target}'
        elif log.action is None or log.action == 'block':
            duration = 'навсегда' if log.is_permanent else f'до {log.blocked_until.strftime("%H:%M %d.%m.%Y")}'
            action_text = f'заблокировал(а) {target} ({duration})'
        else:
            action_text = f'выполнил(а) действие: {log.action}'

        result.append({
            'timestamp': time_str,
            'user': actor,
            'action': action_text
        })

    return result


@admin_bp.route('/admin/')
@login_required
@admin_required
def index():
    stats = get_dashboard_stats()
    return render_template('dashboard.html', **stats)

@admin_bp.route('/admin/reset_outgoing', methods=['POST'])
@login_required
@admin_required
def reset_outgoing():
    try:
        current_year = datetime.now().year % 100
        exists = LetterOutgoing.query.filter_by(year=current_year).first()
        
        if exists:
            # Синхронизируем с максимальным номером
            max_num = db.session.execute(
                text("SELECT MAX(sequence_num) FROM letter_outgoing WHERE year = :year"),
                {'year': current_year}
            ).scalar()
            db.session.execute(
                text("SELECT setval('outgoing_number_seq', :val, true)"),
                {'val': max_num + 1}
            )
            flash('Нумерация синхронизирована с существующими письмами', 'info')
        else:
            # Полный сброс
            db.session.execute(text("ALTER SEQUENCE outgoing_number_seq RESTART WITH 1"))
            flash('Нумерация исходящих писем сброшена', 'success')
        
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Ошибка сброса нумерации: {str(e)}")
        flash('Ошибка при сбросе нумерации', 'danger')
    return redirect(url_for('admin.index'))

@admin_bp.route('/admin/release_outgoing', methods=['POST'])
@login_required
@admin_required
def release_outgoing():
    try:
        db.session.execute(text("SELECT setval('outgoing_number_seq', nextval('outgoing_number_seq') - 1)"))
        db.session.commit()
        flash('Последний номер исходящих освобожден', 'info')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Ошибка освобождения номера: {str(e)}")
        flash('Ошибка при освобождении номера', 'danger')
    return redirect(url_for('admin.index'))

@admin_bp.route('/admin/reset_incoming', methods=['POST'])
@login_required
@admin_required
def reset_incoming():
    try:
        current_year = datetime.now().year
        exists = LetterIncoming.query.filter(
            extract('year', LetterIncoming.date_received) == current_year
        ).first()
        
        if exists:
            flash('Нельзя сбросить нумерацию - уже есть письма за этот год', 'danger')
        else:
            db.session.execute(text("ALTER SEQUENCE incoming_number_seq RESTART WITH 1"))
            db.session.commit()
            flash('Нумерация входящих писем сброшена', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Ошибка при сбросе нумерации', 'danger')
    return redirect(url_for('admin.index'))

@admin_bp.route('/admin/release_incoming', methods=['POST'])
@login_required
@admin_required
def release_incoming():
    try:
        db.session.execute(text("SELECT setval('incoming_number_seq', nextval('incoming_number_seq') - 1)"))
        db.session.commit()
        flash('Последний номер входящих освобожден', 'info')
    except Exception as e:
        db.session.rollback()
        flash('Ошибка при освобождении номера', 'danger')
    return redirect(url_for('admin.index'))



@admin_bp.route('/admin/users')
@login_required
@admin_required
def user_list():
    filter_type = request.args.get('only')
    now = datetime.utcnow()

    # 🔍 Фильтрация по блокировке
    if filter_type == 'blocked':
        users = User.query.filter(
            or_(
                User.is_permanently_blocked == True,
                and_(User.blocked_until != None, User.blocked_until > now)
            )
        ).order_by(User.username).all()
    else:
        users = User.query.order_by(User.username).all()

    # 🟢 Подготовка списка с онлайн-статусом и активностью
    users_with_status = []
    for u in users:
        users_with_status.append({
            'user': u,
            'online': is_user_online(u),
            'last_seen': u.last_active_at.strftime('%H:%M %d.%m.%Y') if u.last_active_at else '—'
        })

    return render_template(
        'users_list.html',
        users=users_with_status,
        filter_type=filter_type
    )



@admin_bp.route('/admin/users/new', methods=['GET', 'POST'])
@login_required
@admin_required
def user_create():
    form = AdminUserForm()
    form.obj = None
    form.role.choices = [(r.id, r.name) for r in Role.query.all()]
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            display_name=form.display_name.data,
            email=form.email.data,
            role_id=form.role.data,
            password_hash=generate_password_hash(form.password.data) 
                           if form.password.data else ''
        )
        db.session.add(user)
        db.session.commit()
        flash(f'Пользователь {user.username} создан', 'success')
        return redirect(url_for('admin.user_list'))

    existing_user = User.query.filter_by(email=form.email.data).first()
    if existing_user:
        flash('Пользователь с таким email уже существует.', 'warning')
    return render_template('user_form.html', form=form, title='Новый пользователь')
        



@admin_bp.route('/admin/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def user_edit(user_id):
    user = User.query.get_or_404(user_id)
    form = AdminUserForm(obj=user)
    form.obj = user
    form.role.choices = [(r.id, r.name) for r in Role.query.all()]
    if form.validate_on_submit():
        user.username = form.username.data
        user.display_name = form.display_name.data
        user.email = form.email.data
        user.role_id = form.role.data
        if form.password.data:
            user.password_hash = generate_password_hash(form.password.data)
        db.session.commit()
        flash(f'Данные пользователя {user.username} обновлены', 'success')
        return redirect(url_for('admin.user_list'))
    return render_template('user_form.html', form=form, title=f'Редактировать {user.username}')

@admin_bp.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def user_delete(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Нельзя удалить себя', 'warning')
    else:
        db.session.delete(user)
        db.session.commit()
        flash(f'Пользователь {user.username} удалён', 'success')
    return redirect(url_for('admin.user_list'))

@admin_bp.route('/admin/dashboard')
@login_required
@admin_required
def dashboard():
    try:
        stats = get_dashboard_stats()
        return render_template('dashboard.html', **stats)
    except Exception as e:
        current_app.logger.error(f"Ошибка в dashboard: {str(e)}")
        flash('Произошла ошибка при загрузке данных', 'danger')
        return render_template('dashboard.html', 
                            online_users=0,
                            total_users=0,
                            total_mails=0,
                            blocked_users=0,
                            recent_activity=[],
                            next_outgoing='H-0/00',
                            next_incoming='ВХ-0/00')


@admin_bp.route('/outgoing')
@login_required
@admin_required
def all_outgoing():
    letters = LetterOutgoing.query.order_by(LetterOutgoing.date_created.desc()).all()
    return render_template('admin/outgoing_all.html', letters=letters)


# Блокировка пользователей 
@admin_bp.route('/admin/users/<int:user_id>/block', methods=['POST'])
@login_required
@admin_required
def block_user(user_id):
    user = User.query.get_or_404(user_id)

    # Защита от блокировки администраторов и себя
    if user.role.name == 'Admin':
        flash('⛔ Нельзя заблокировать администратора', 'warning')
        return redirect(url_for('admin.user_list'))

    if user.id == current_user.id:
        flash('🚨 Вы не можете заблокировать самого себя', 'danger')
        return redirect(url_for('admin.user_list'))

    duration = request.form.get('duration', 'permanent')
    reason = request.form.get('reason', 'Причина не указана').strip()
    now = datetime.utcnow()

    # Логирование
    current_app.logger.info(
        f'🛡️ Блокировка пользователя {user.username} '
        f'администратором {current_user.username}. '
        f'Тип: {duration}, Причина: {reason}'
    )

    # Типы блокировок
    block_data = {
        '15min': ('15 минут', timedelta(minutes=15)),
        '1hour': ('1 час', timedelta(hours=1)),
        '1day': ('1 день', timedelta(days=1)),
        'custom': (
            f"{request.form.get('custom_minutes', 15)} минут",
            timedelta(minutes=int(request.form.get('custom_minutes', 15)))
        ),
        'permanent': ('навсегда', None)
    }

    duration_text, delta = block_data.get(duration, ('навсегда', None))

    if duration == 'permanent':
        user.is_permanently_blocked = True
        user.blocked_until = None
    else:
        user.blocked_until = now + delta
        user.is_permanently_blocked = False



    # История блокировок
    block_record = UserBlockHistory(
        user_id=user.id,
        admin_id=current_user.id,
        timestamp=now,
        block_type=duration,
        reason=reason,
        blocked_until=user.blocked_until,
        is_permanent=(duration == 'permanent'),
        action=None  # Если хочешь — можно добавить “manual” или “system”
    )
    db.session.add(block_record)

    # Выход текущего пользователя, если он себя блокирует (хотя выше есть защита от этого)
    if user == current_user:
        logout_user()

    db.session.commit()

    flash(f'🔒 Пользователь {user.username} заблокирован {duration_text}. Причина: {reason}', 'success')
    return redirect(url_for('admin.user_list'))


# разблокировка пользователей 
@admin_bp.route('/admin/users/<int:user_id>/unblock', methods=['POST'])
@login_required
@admin_required
def unblock_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if not (user.is_permanently_blocked or user.is_temporarily_blocked):
        flash('ℹ️ Пользователь не заблокирован', 'info')
        return redirect(url_for('admin.user_list', user_id=user.id))

    # Логирование разблокировки
    current_app.logger.info(
        f'🛡️ Разблокировка пользователя {user.username} '
        f'администратором {current_user.username}'
    )

    # Запись в историю
    unblock_record = UserBlockHistory(
        user_id=user.id,
        admin_id=current_user.id,
        action='unblock'
    )
    db.session.add(unblock_record)
    
    # Сброс блокировки
    user.is_permanently_blocked = False
    user.blocked_until = None
    
    db.session.commit()
    
    flash(f'🔓 Пользователь {user.username} успешно разблокирован', 'success')
    return redirect(url_for('admin.user_list', user_id=user.id))

