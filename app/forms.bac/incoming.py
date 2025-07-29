# app/forms/incoming.py

from flask_wtf import FlaskForm
from wtforms import StringField, DateField, SubmitField
from wtforms.validators import DataRequired, Length

class IncomingForm(FlaskForm):
    date         = DateField(
        'Дата',
        format='%Y-%m-%d',
        validators=[DataRequired()]
    )
    organization = StringField(
        'Организация',
        validators=[DataRequired(), Length(max=200)]
    )
    subject      = StringField(
        'Тема',
        validators=[DataRequired(), Length(max=200)]
    )
    forwarded_to = StringField(
        'Перенаправлено',
        validators=[Length(max=120)]
    )
    submit       = SubmitField('Зарегистрировать')
