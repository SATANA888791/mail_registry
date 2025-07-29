from datetime import datetime
from flask import current_app, request
from flask_login import UserMixin
from app import db, login
from sqlalchemy.orm import foreign
from sqlalchemy.sql import or_, and_
from werkzeug.security import check_password_hash
from datetime import datetime, timedelta
import os
from sqlalchemy import event


class Role(db.Model):
    __tablename__ = 'roles' 
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), unique=True)


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, index=True)
    email = db.Column(db.String(120), unique=True, index=True)
    display_name = db.Column(db.String(120), nullable=True)
    password_hash = db.Column(db.Text, nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    role = db.relationship('Role', backref='users')
    outgoing = db.relationship('LetterOutgoing', backref='user', lazy='dynamic')
    incoming = db.relationship('LetterIncoming', backref='user', lazy='dynamic')
    last_active_at = db.Column(db.DateTime, default=None)
    
    # Поля для системы блокировок
    blocked_until = db.Column(db.DateTime, nullable=True)
    is_permanently_blocked = db.Column(db.Boolean, default=False)
    last_failed_attempt = db.Column(db.DateTime)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_blocked(self):
        return self.is_permanently_blocked or (self.blocked_until and self.blocked_until > datetime.utcnow())


    @property
    def is_temporarily_blocked(self):
        return self.blocked_until and self.blocked_until > datetime.utcnow()

    @property
    def remaining_block_time(self):
        if not self.blocked_until:
            return 0
        remaining = (self.blocked_until - datetime.utcnow()).seconds // 60
        return max(1, remaining)  # Всегда показываем минимум 1 минуту

    @property
    def login_block_status(self):
        now = datetime.utcnow()
        if self.is_permanently_blocked:
            return 'permanent'
        if self.blocked_until and self.blocked_until > now:
            return 'temporary'
        return 'active'

    @property
    def is_admin(self):
        return self.role and self.role.name == 'Admin'

    @property
    def role_emoji(self):
        return '👑' if self.is_admin else '🙋‍♂️'

    def get_greeting(self):
        hour = datetime.now().hour
        if hour < 6: return '🌙 Доброй ночи'
        if hour < 12: return '🌅 Доброе утро'
        if hour < 18: return '🌞 Добрый день'
        return '🌆 Добрый вечер'

    def apply_login_security_policy(self, attempts):
        now = datetime.utcnow()
        
        # Сброс блокировки если прошло более суток с последней попытки
        if self.last_failed_attempt and (now - self.last_failed_attempt) > timedelta(days=1):
            self.blocked_until = None
            self.is_permanently_blocked = False
        
        # Обновление времени последней неудачной попытки
        self.last_failed_attempt = now
        
        # Градуальная система блокировок
        if attempts >= 10:
            self.is_permanently_blocked = True
            self.blocked_until = None
        elif attempts >= 7:
            self.blocked_until = now + timedelta(hours=1)
        elif attempts >= 5:
            if not self.blocked_until or self.blocked_until < now:
                self.blocked_until = now + timedelta(minutes=15)
            elif now < self.blocked_until <= now + timedelta(minutes=15):
                self.blocked_until += timedelta(minutes=15)

        # Автоматическая отправка уведомления администратору
        if attempts == 5 or attempts == 10:
            self.send_security_notification(attempts)

    def send_security_notification(self, attempts):
        """Отправка уведомления администратору"""
        if not current_app.config.get('ADMIN_NOTIFICATIONS_ENABLED', True):
            return
            
        message = (f"🔒 Security Alert!\n"
                  f"User: {self.username}\n"
                  f"Failed attempts: {attempts}\n"
                  f"Status: {self.login_block_status}\n"
                  f"IP: {request.remote_addr if request else 'N/A'}")
        
        # Реальная реализация зависит от вашей системы нотификаций
        # send_admin_notification.delay(
        #     subject=f"Security Alert: {self.username}",
        #     message=message
        # )
        current_app.logger.warning(f"Security notification would be sent: {message}")

class UserBlockHistory(db.Model):
    __tablename__ = 'user_block_history'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    block_type = db.Column(db.String(20))  # '15min', '1hour', 'permanent' etc
    reason = db.Column(db.Text)
    blocked_until = db.Column(db.DateTime)
    is_permanent = db.Column(db.Boolean, default=False)
    action = db.Column(db.String(10))  # 'block' or 'unblock'
    
    user = db.relationship('User', foreign_keys=[user_id])
    admin = db.relationship('User', foreign_keys=[admin_id])

@login.user_loader
def load_user(id):
    return User.query.get(int(id))


class LetterOutgoing(db.Model):
    __tablename__ = 'letter_outgoing'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    number = db.Column(db.String(20), unique=True, index=True)
    subject = db.Column(db.String(200))
    recipient = db.Column(db.String(120))
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    is_protected = db.Column(db.Boolean, default=False)  
    sequence_num = db.Column(db.Integer, unique=True)
    year = db.Column(db.Integer)


    # 👇 Вот эта строка — создаёт связь с вложениями
    attachments = db.relationship(
        'Attachment',
        lazy='dynamic',
        cascade='all, delete-orphan',
        passive_deletes=True,
        primaryjoin="and_(foreign(Attachment.letter_id)==LetterOutgoing.id, Attachment.letter_type=='outgoing')",
        overlaps="outgoing_letter,incoming_letter"
    )

    def delete_with_attachments(self):
        for attachment in self.attachments:
            try:
                os.remove(attachment.filepath)
                current_app.logger.info(f"Файл удалён: {attachment.filepath}")
            except FileNotFoundError:
                current_app.logger.warning(f"Файл не найден при удалении: {attachment.filepath}")
            db.session.delete(attachment)
        current_app.logger.info(f"Удаление письма (исходящего): ID={self.id}, Номер={self.number}")
        db.session.delete(self)


class Attachment(db.Model):
    __tablename__ = 'attachment'
    id = db.Column(db.Integer, primary_key=True)
    letter_id = db.Column(db.Integer, nullable=False)  # убираем ForeignKey — он будет опосредованным
    letter_type = db.Column(db.String(10))  # 'incoming' или 'outgoing'
    filename = db.Column(db.String(255))
    stored_filename = db.Column(db.String(255))
    filepath = db.Column(db.String(300))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 📨 Входящее письмо
    incoming_letter = db.relationship(
        'LetterIncoming',
        primaryjoin="and_(foreign(Attachment.letter_id)==LetterIncoming.id, Attachment.letter_type=='incoming')",
        overlaps="attachments,outgoing_letter"
    )

    # 📤 Исходящее письмо
    outgoing_letter = db.relationship(
        'LetterOutgoing',
        primaryjoin="and_(foreign(Attachment.letter_id)==LetterOutgoing.id, Attachment.letter_type=='outgoing')",
        overlaps="attachments,incoming_letter"
    )


class LetterIncoming(db.Model):
    __tablename__ = 'letter_incoming'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    number = db.Column(db.String(20), unique=True, index=True)
    organization = db.Column(db.String(200))
    subject = db.Column(db.String(200))
    forwarded_to = db.Column(db.String(120))
    date_received = db.Column(db.DateTime, default=datetime.utcnow)
    sequence_num = db.Column(db.Integer, unique=True)  # Новое поле
    year = db.Column(db.Integer)  # Новое поле



    # 👇 Добавляем связь с вложениями
    attachments = db.relationship(
        'Attachment',
        lazy='dynamic',
        primaryjoin=and_(
            foreign(Attachment.letter_id) == id,
            Attachment.letter_type == 'incoming'
        ),
        overlaps="outgoing_letter,incoming_letter,attachments"
    )

    def delete_with_attachments(self):
        for attachment in self.attachments:
            try:
                os.remove(attachment.filepath)
                current_app.logger.info(f"Файл удалён: {attachment.filepath}")
            except FileNotFoundError:
                current_app.logger.warning(f"Файл не найден при удалении: {attachment.filepath}")
            db.session.delete(attachment)
        current_app.logger.info(f"Удаление письма (входящего): ID={self.id}, Номер={self.number}")
        db.session.delete(self)



class LoginAttempt(db.Model):
    __tablename__ = 'login_attempts'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    ip_address = db.Column(db.String(100), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    successful = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)



@event.listens_for(LetterOutgoing, 'before_insert')
def set_outgoing_values(mapper, connection, target):
    if not target.year:
        target.year = datetime.now().year
    if not target.sequence_num:
        target.sequence_num = db.session.execute(
            db.text("SELECT nextval('outgoing_number_seq')")
        ).scalar()

@event.listens_for(LetterIncoming, 'before_insert')
def set_incoming_values(mapper, connection, target):
    if not target.year:
        target.year = datetime.now().year
    if not target.sequence_num:
        target.sequence_num = db.session.execute(
            db.text("SELECT nextval('incoming_number_seq')")
        ).scalar()