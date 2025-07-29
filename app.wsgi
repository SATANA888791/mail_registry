import sys, os

# путь до вашего проекта
proj_path = '/volume7/web/mail_registry'
if proj_path not in sys.path:
    sys.path.insert(0, proj_path)

# активируем виртуальное окружение
activate = os.path.join(proj_path, 'venv/bin/activate_this.py')
with open(activate) as f:
    exec(f.read(), {'__file__': activate})

# импортируем Flask-приложение
from run import app as application
