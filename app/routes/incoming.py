from flask import (
    Blueprint, render_template, redirect,
    url_for, request, flash, send_file, current_app
)
from flask import session
from sqlalchemy import func
import os
import datetime
import uuid

from werkzeug.utils import secure_filename
from flask_login import login_required, current_user

from app import db
from app.models import LetterIncoming, Attachment
from app.forms import IncomingForm
from app.utils import generate_incoming_number, save_attachment, transliterate, allowed_file
from app.decorators import admin_required
import uuid
from app.utils import transliterate, allowed_file




incoming_bp = Blueprint('incoming', __name__, template_folder='../templates/incoming')


@incoming_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_incoming():
    if current_user.role.name not in ['Admin', 'Editor']:
        flash('У вас нет прав для создания входящих писем.', 'danger')
        return redirect(url_for('incoming.list_incoming'))

    form = IncomingForm()
    if form.validate_on_submit():
        db_number, fs_number = generate_incoming_number()
        letter = LetterIncoming(
            user_id=current_user.id,
            number=db_number,
            sequence_num=int(db_number.split('-')[1].split('/')[0]),
            year=int(db_number.split('/')[1]),
            organization=form.organization.data,
            subject=form.subject.data,
            forwarded_to=form.forwarded_to.data,
            date_received=form.date.data
        )
        db.session.add(letter)
        db.session.commit()
        flash(f'Входящее письмо {db_number} создано.', 'success')
        return redirect(url_for('incoming.attachments', letter_id=letter.id))

    return render_template('incoming/new.html', form=form)



@incoming_bp.route('/<int:letter_id>/attachments', methods=['GET', 'POST'])
@login_required
def attachments(letter_id):
    letter = LetterIncoming.query.get_or_404(letter_id)
    
    # Проверка прав
    if current_user.role.name not in ['Admin', 'Editor'] and letter.user_id != current_user.id:
        flash('У вас нет прав для работы с этим письмом.', 'danger')
        return redirect(url_for('incoming.list_incoming'))

    # Обработка загрузки файла
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Файл не выбран', 'warning')
            return redirect(url_for('incoming.attachments', letter_id=letter.id))

        file = request.files['file']
        
        # Проверка размера файла
        if file.content_length > current_app.config['MAX_CONTENT_LENGTH']:
            flash('Файл слишком большой. Максимальный размер 50 МБ', 'danger')
            return redirect(url_for('incoming.attachments', letter_id=letter.id))
            
        if file.filename == '':
            flash('Файл не выбран', 'warning')
            return redirect(url_for('incoming.attachments', letter_id=letter.id))

        if not allowed_file(file.filename):
            flash('Недопустимый формат файла', 'danger')
            return redirect(url_for('incoming.attachments', letter_id=letter.id))

        # Формируем путь для сохранения
        now = datetime.datetime.utcnow()
        user_folder = transliterate(current_user.username)
        letter_number = letter.number.replace('/', '_')
        
        upload_path = os.path.join(
            current_app.config['UPLOAD_FOLDER'],
            'incoming',
            user_folder,
            str(now.year),
            f"{now.month:02d}",
            letter_number
        )
        
        # Создаем папки если их нет
        os.makedirs(upload_path, exist_ok=True)

        # Генерируем уникальное имя файла
        original_name = secure_filename(file.filename)
        unique_name = f"{uuid.uuid4().hex[:8]}_{original_name}"
        file_path = os.path.join(upload_path, unique_name)
        
        try:
            # Сохраняем файл
            file.save(file_path)
            
            # Сохраняем запись в БД
            new_attachment = Attachment(
                letter_id=letter.id,
                letter_type='incoming',
                filename=original_name,
                stored_filename=unique_name,
                filepath=file_path,
                uploaded_at=now
            )
            db.session.add(new_attachment)
            db.session.commit()
            
            flash(f'Файл "{original_name}" успешно загружен', 'success')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Ошибка при загрузке файла: {str(e)}")
            flash('Ошибка при сохранении файла', 'danger')

        return redirect(url_for('incoming.attachments', letter_id=letter.id))

    # Получаем список вложений
    attachments = Attachment.query.filter_by(
        letter_id=letter.id,
        letter_type='incoming'
    ).order_by(Attachment.uploaded_at.desc()).all()

    return render_template(
        'incoming/attachments.html',
        letter=letter,
        attachments=attachments,
        allowed_extensions=current_app.config['ALLOWED_EXTENSIONS'],
        pending_upload=False
    )

    # 📤 Загрузка файла с проверкой на дубликаты
    if request.method == 'POST':
        if current_user.role.name not in upload_roles:
            flash('У вас нет прав для загрузки вложений.', 'danger')
            return redirect(request.url)

        file = request.files.get('file')
        if not file or file.filename.strip() == "":
            flash('Файл не выбран.', 'warning')
            return redirect(request.url)

        original_name = file.filename.strip()
        already = Attachment.query.filter_by(
            letter_id=letter.id,
            letter_type='incoming',
            filename=original_name
        ).first()
        
        if not allowed_file(original_name):
            flash('Недопустимый формат файла. Разрешены только: PDF, Word, Excel, RAR.', 'danger')
            return redirect(request.url)

        if already and 'force' not in request.form:
            attachments = Attachment.query.filter_by(
                letter_id=letter.id, letter_type='incoming'
            ).all()
            flash(f'Файл "{original_name}" уже прикреплён. Нажмите "Загрузить всё равно", чтобы подтвердить.', 'warning')
            return render_template(
                'incoming/attachments.html',
                letter=letter,
                attachments=attachments,
                pending_upload=True,
                allowed_extensions=current_app.config['ALLOWED_EXTENSIONS']
            )

        # 🛡️ Уникализируем имя на диске
        from app.utils import transliterate
        safe_name = secure_filename(transliterate(original_name))
        unique_suffix = uuid.uuid4().hex[:6]
        name, ext = os.path.splitext(safe_name)
        safe_name = f"{name}_{unique_suffix}{ext}"

        now = datetime.datetime.utcnow()
        prefix = "VH"
        subfolder = f"{prefix}_{letter.id}_{now.year % 100}"
        folder = os.path.join(
            current_app.config['UPLOAD_FOLDER'],
            'incoming',
            letter.user.username,
            str(now.year),
            f"{now.month:02d}",
            subfolder
        )
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, safe_name)
        file.save(path)

        new = Attachment(
            letter_id=letter.id,
            letter_type='incoming',
            filename=original_name,
            stored_filename=safe_name,
            filepath=path,
            uploaded_at=now
        )
        db.session.add(new)
        db.session.commit()
        flash('Вложение добавлено.', 'success')
        return redirect(request.url)

    # 📦 Получение вложений
    attachments = Attachment.query.filter_by(
        letter_id=letter.id, letter_type='incoming'
    ).all()

    return render_template(
        'incoming/attachments.html',
        letter=letter,
        attachments=attachments
    )


@incoming_bp.route('/list')
@login_required
def list_incoming():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', type=int)
    if per_page:
        session['per_page'] = per_page
    else:
        per_page = session.get('per_page', 10)

    # 📌 Фильтрация
    query = LetterIncoming.query

    org = request.args.get('organization', '').strip()
    if org:
        query = query.filter(LetterIncoming.organization.ilike(f"%{org}%"))

    number = request.args.get('number', '').strip()
    if number:
        query = query.filter(LetterIncoming.number.ilike(f"%{number}%"))

    subject = request.args.get('subject', '').strip()
    if subject:
        query = query.filter(LetterIncoming.subject.ilike(f"%{subject}%"))

    forwarded_to = request.args.get('forwarded_to', '').strip()
    if forwarded_to:
        query = query.filter(LetterIncoming.forwarded_to.ilike(f"%{forwarded_to}%"))


    # 📅 Опциональная фильтрация по дате
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    if date_from:
        query = query.filter(LetterIncoming.date_received >= date_from)
    if date_to:
        query = query.filter(LetterIncoming.date_received <= date_to)

    # 📌 Сортировка по номеру (как у тебя было)
    query = query.order_by(
        db.text("CAST(SUBSTRING(letter_incoming.number FROM 4 FOR POSITION('/' IN letter_incoming.number) - 4) AS INTEGER) DESC")
    )

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template(
        'incoming/list.html',
        pagination=pagination,
        letters=pagination.items,
        per_page=per_page,
        search_params={
            'organization': org,
            'number': number,
            'subject': subject,
            'forwarded_to': forwarded_to,
            'date_from': date_from,
            'date_to': date_to
        }
    )

@incoming_bp.route('/<int:letter_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_incoming(letter_id):
    letter = LetterIncoming.query.get_or_404(letter_id)
    if letter.user_id != current_user.id and current_user.role.name not in ['Admin', 'Editor']:
        flash('Доступ запрещён.', 'danger')
        return redirect(url_for('incoming.list_incoming'))

    form = IncomingForm(
        date=letter.date_received,
        organization=letter.organization,
        subject=letter.subject,
        forwarded_to=letter.forwarded_to
    )
    if form.validate_on_submit():
        letter.organization = form.organization.data
        letter.subject = form.subject.data
        letter.forwarded_to = form.forwarded_to.data
        letter.date_received = form.date.data
        db.session.commit()
        flash('Письмо обновлено.', 'success')
        return redirect(url_for('incoming.list_incoming'))

    attachments = Attachment.query.filter_by(
        letter_id=letter.id, letter_type='incoming'
    ).all()
    return render_template(
        'incoming/edit.html',
        form=form,
        letter=letter,
        attachments=attachments
    )


@incoming_bp.route('/<int:letter_id>/attachments/<int:attachment_id>/delete', methods=['POST'])
@login_required
def delete_attachment(letter_id, attachment_id):
    letter = LetterIncoming.query.get_or_404(letter_id)

    # 🔒 Только Admin и Editor
    if current_user.role.name not in ['Admin', 'Editor']:
        flash('У вас нет прав для удаления вложений.', 'danger')
        return redirect(url_for('incoming.attachments', letter_id=letter_id))

    attachment = Attachment.query.filter_by(
        id=attachment_id,
        letter_id=letter_id,
        letter_type='incoming'
    ).first_or_404()

    # 🗑️ Удаляем файл с диска
    try:
        if os.path.exists(attachment.filepath):
            os.remove(attachment.filepath)
    except Exception as e:
        flash(f'Не удалось удалить файл: {e}', 'warning')

    # ❌ Удаляем запись из БД
    db.session.delete(attachment)
    db.session.commit()

    flash('Вложение удалено.', 'success')
    return redirect(url_for('incoming.attachments', letter_id=letter_id))

# удаление входящего письма
@incoming_bp.route("/incoming/delete/<int:letter_id>", methods=["POST"])
@admin_required
def delete_incoming_letter(letter_id):
    letter = LetterIncoming.query.get_or_404(letter_id)
    letter.delete_with_attachments()
    db.session.commit()
    flash(f"Письмо {letter.number} успешно удалено ✅", "success")
    return redirect(url_for("incoming.list_incoming"))



# Экспорт в exel
@incoming_bp.route('/export')
@login_required
def export_incoming():
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment
    from io import BytesIO

    # 🔍 Фильтрация по параметрам запроса
    query = LetterIncoming.query

    number = request.args.get('number', '').strip()
    if number:
        query = query.filter(LetterIncoming.number.ilike(f"%{number}%"))

    organization = request.args.get('organization', '').strip()
    if organization:
        query = query.filter(LetterIncoming.organization.ilike(f"%{organization}%"))

    date_from = request.args.get('date_from')
    if date_from:
        query = query.filter(LetterIncoming.date_received >= date_from)

    date_to = request.args.get('date_to')
    if date_to:
        query = query.filter(LetterIncoming.date_received <= date_to)

    query = query.order_by(
        db.text("CAST(SUBSTRING(letter_incoming.number FROM 4 FOR POSITION('/' IN letter_incoming.number) - 4) AS INTEGER) DESC")
    )
    letters = query.all()


    # 📋 Создаём Excel-файл
    wb = Workbook()
    ws = wb.active
    ws.title = 'Входящие письма'

    headers = ['Номер', 'Организация', 'Тема', 'Направлено', 'Дата получения']
    ws.append(headers)

    # 💎 Формат заголовков
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal='center')

    # 📦 Заполняем строки
    for letter in letters:
        ws.append([
            letter.number,
            letter.organization,
            letter.subject,
            letter.forwarded_to,
            letter.date_received.strftime('%Y-%m-%d')
        ])

    # 📏 Автоширина
    for column_cells in ws.columns:
        max_length = max(len(str(cell.value)) if cell.value else 0 for cell in column_cells)
        ws.column_dimensions[column_cells[0].column_letter].width = max_length + 4

    # 🎯 Сохраняем файл в память
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"Входящие_{datetime.datetime.utcnow().strftime('%Y-%m-%d')}.xlsx"
    return send_file(
        output,
        download_name=filename,
        as_attachment=True,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
