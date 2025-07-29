import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get('DATABASE_URL') or
        'postgresql://mailadmin:Uoc8-DFDAi@192.168.0.188:5433/mail'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Максимальный размер загруженного файла (50 МБ)
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024
    ALLOWED_EXTENSIONS = {
        'pdf': 'PDF документ',
        'doc': 'Word 97-2003',
        'docx': 'Word документ',
        'xls': 'Excel 97-2003',
        'xlsx': 'Excel документ',
        'rar': 'RAR архив'
    }
    UPLOAD_FOLDER = os.path.join(basedir, '..', 'uploads')
    