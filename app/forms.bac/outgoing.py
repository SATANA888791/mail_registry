# app/forms/outgoing.py

from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length

class OutgoingForm(FlaskForm):
    subject   = StringField(
        'Тема',
        validators=[DataRequired(), Length(max=200)]
    )
    recipient = StringField(
        'Получатель',
        validators=[DataRequired(), Length(max=120)]
    )
    submit    = SubmitField('Зарегистрировать')
