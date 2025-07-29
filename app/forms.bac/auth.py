# app/forms/auth.py

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo

class LoginForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[DataRequired(), Length(1,64)])
    password = PasswordField('Пароль', validators=[DataRequired()])
    submit   = SubmitField('Войти')

class RegisterForm(FlaskForm):
    username  = StringField('Имя пользователя', validators=[DataRequired(), Length(1,64)])
    email     = StringField('Email', validators=[DataRequired(), Email(), Length(1,120)])
    password  = PasswordField('Пароль',
                              validators=[DataRequired(), EqualTo('password2', 'Пароли должны совпадать')])
    password2 = PasswordField('Повтор пароля', validators=[DataRequired()])
    submit    = SubmitField('Зарегистрироваться')
