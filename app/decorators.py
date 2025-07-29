from functools import wraps
from flask import abort
from flask_login import current_user

def admin_required(f):
    """Декоратор: доступ только для админов."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role.name != 'Admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated


