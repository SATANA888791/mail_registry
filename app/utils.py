import os, uuid
from datetime import datetime
from flask import current_app
from werkzeug.utils import secure_filename
from app import db
from app.models import LetterOutgoing, LetterIncoming, Attachment
import unicodedata
import re
from sqlalchemy.sql import text


def generate_outgoing_number():
    """Генерирует следующий номер вида H-{seq}/{YY}."""
    year = datetime.datetime.now().year % 100
    seq = (db.session.query(db.func.max(LetterOutgoing.id)).scalar() or 0) + 1
    return f'H-{seq}/{year}'


def generate_incoming_number():
    now = datetime.utcnow()
    current_year = now.year % 100
    
    # Получаем следующий номер
    next_num = db.session.execute(
        text("SELECT nextval('incoming_number_seq')")
    ).scalar()
    
    # Формируем номер (в базе - кириллический)
    db_number = f"ВХ-{next_num}/{current_year}"
    
    # Для файловой системы - латинский вариант
    fs_number = f"VH-{next_num}/{current_year}"
    
    return db_number, fs_number


def save_attachment(file, letter, letter_type):
    """
    Сохраняет файл вложения с транслитерацией имени в:
    uploads/{type}/{user}/{YYYY}/{MM}/{PREFIX}_{id}_{YY}/
    """
    original_filename = file.filename
    safe_name = secure_filename(transliterate(original_filename))  # транслитерируем

     # 🆎 Уникальный суффикс
    unique_suffix = uuid.uuid4().hex[:8]
    name, ext = os.path.splitext(safe_name)
    safe_name = f"{name}_{unique_suffix}{ext}"

    now = datetime.datetime.now()
    prefix = 'H' if letter_type == 'outgoing' else 'VH'
    subdir = f"{prefix}_{letter.id}_{now.year % 100}"

    folder = os.path.join(
        current_app.config['UPLOAD_FOLDER'],
        letter_type,
        letter.user.username,
        str(now.year),
        f"{now.month:02d}",
        subdir
    )
    os.makedirs(folder, exist_ok=True)

    path = os.path.join(folder, safe_name)
    file.save(path)

    # Сохраняем запись в БД
    attach = Attachment(
        letter_id=letter.id,
        letter_type=letter_type,
        filename=original_filename,     # то, что отображается пользователю
        stored_filename=safe_name,      # безопасное имя на диске
        filepath=path,
        uploaded_at=datetime.datetime.utcnow()
    )
    db.session.add(attach)
    db.session.commit()

    return original_filename, path


def transliterate(text):
    translit_map = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e',
        'ё': 'yo', 'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k',
        'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r',
        'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'ts',
        'ч': 'ch', 'ш': 'sh', 'щ': 'sch', 'ъ': '', 'ы': 'y', 'ь': '',
        'э': 'e', 'ю': 'yu', 'я': 'ya'
    }
    result = []
    for char in text.lower():
        result.append(translit_map.get(char, char))
    return ''.join(result)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']