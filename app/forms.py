# app/forms.py

from wtforms import ValidationError
from app.models import User
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, FileField, DateField, ValidationError
from wtforms.validators import DataRequired, Length, Email, Optional
from app.models import Role
from wtforms import BooleanField

# ---------------- Авторизация ----------------

class LoginForm(FlaskForm):
    username = StringField(
        'Пользователь', 
        validators=[DataRequired(), Length(1, 64)]
    )
    password = PasswordField(
        'Пароль', 
        validators=[DataRequired(), Length(1, 128)]
    )
    submit = SubmitField('Войти')

    display_name = StringField(
        'Отображаемое имя', 
        validators=[Length(max=120)]
    )

    remember = BooleanField('Запомнить меня')

# ---------------- Админ: Пользователь ----------------

class AdminUserForm(FlaskForm):
    username = StringField(
        'Логин', 
        validators=[DataRequired(), Length(3, 64)]
    )
    email = StringField(
        'E-mail',
        validators=[DataRequired(), Email(), Length(1, 120)]
    )

    display_name = StringField(
        'Отображаемое имя', 
        validators=[DataRequired(), Length(max=120)]
    
    )

    password = PasswordField(
        'Пароль', 
    )

    submit = SubmitField('Сохранить')  # 👈 вот то, чего не хватает

    role = SelectField('Роль', coerce=int, validators=[DataRequired()])

def validate_password(self, field):
    # если создаём нового — пароль обязателен
    if not hasattr(self, 'obj') or self.obj is None:
        if not field.data:
            raise ValidationError('Пароль обязателен при создании пользователя.')
        elif len(field.data) < 6:
            raise ValidationError('Пароль должен быть не менее 6 символов.')
    else:
        # при редактировании: если пароль введён — проверим длину
        if field.data and len(field.data) < 6:
            raise ValidationError('Пароль должен быть не менее 6 символов.')


    role = SelectField(
        'Роль',
        coerce=int, 
        validators=[DataRequired()]
    )

    submit = SubmitField('Сохранить')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # подтягиваем роли из БД
        self.role.choices = [
            (r.id, r.name) for r in Role.query.order_by(Role.name).all()
        ]

    def validate_username(self, field):
        user = User.query.filter_by(username=field.data).first()
        if user and (not self.obj or user.id != self.obj.id):
            raise ValidationError('Такой логин уже используется.')

    def validate_email(self, field):
        user = User.query.filter_by(email=field.data).first()
        if user and (not self.obj or user.id != self.obj.id):
            raise ValidationError('Этот email уже зарегистрирован.')


# ---------------- Исходящие письма ----------------

class OutgoingForm(FlaskForm):
    subject = StringField(
        'Тема письма', 
        validators=[DataRequired(), Length(1, 256)]
    )
    recipient = StringField(
        'Получатель', 
        validators=[DataRequired(), Length(1, 128)]
    )

    is_protected = BooleanField('🔒 Закрыть доступ для других пользователей')

    submit = SubmitField('Сохранить')

    

# ---------------- Входящие письма ----------------

class IncomingForm(FlaskForm):
    date = DateField(
        'Дата получения', 
        format='%Y-%m-%d',
        validators=[DataRequired()]
    )
    organization = StringField(
        'Организация', 
        validators=[DataRequired(), Length(1, 128)]
    )
    subject = StringField(
        'Тема письма', 
        validators=[DataRequired(), Length(1, 256)]
    )
    forwarded_to = StringField(
        'Передано кому', 
        validators=[Optional(), Length(0, 64)]
    )
    submit = SubmitField('Сохранить')
