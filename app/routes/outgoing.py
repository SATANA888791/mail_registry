from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask import send_file
from flask import session
import os
import datetime
from flask_login import login_required, current_user
from app import db
from app.models import LetterOutgoing, Attachment
from app.forms import OutgoingForm
from app.utils import generate_outgoing_number, save_attachment, allowed_file
from app.decorators import admin_required



outgoing_bp = Blueprint('outgoing', __name__, template_folder='../templates/outgoing')


@outgoing_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_outgoing():
    form = OutgoingForm()
    if form.validate_on_submit():
        number = generate_outgoing_number()
        letter = LetterOutgoing(
            user_id=current_user.id,
            number=number,
            subject=form.subject.data,
            recipient=form.recipient.data,
            is_protected=form.is_protected.data
        )
        db.session.add(letter)
        db.session.commit()
        flash(f'Исходящее письмо {number} создано.', 'success')
        return redirect(url_for('outgoing.attachments', letter_id=letter.id))
    return render_template('outgoing/new.html', form=form)


@outgoing_bp.route('/<int:letter_id>/attachments', methods=['GET', 'POST'])
@login_required
def attachments(letter_id):
    letter = LetterOutgoing.query.get_or_404(letter_id)

    # 🔒 Проверка доступа
    # 👁 Проверка доступа к вложениям
    # 🔒 Расширенная проверка доступа
    if letter.is_protected:
    # Защищённое письмо — только автор или админ
        if current_user.id != letter.user_id and current_user.role.name != 'Admin':
            flash('⛔ Вложение защищено автором. Доступ запрещён.', 'danger')
            return redirect(url_for('outgoing.list_outgoing'))
    else:
    # Открытое письмо — viewer может смотреть
        if current_user.role.name == 'Viewer' and current_user.id != letter.user_id:
        # разрешаем
         pass
        elif current_user.id != letter.user_id and current_user.role.name not in ['Admin', 'Editor']:
            flash('⛔ Вам не разрешён доступ к вложению.', 'danger')
            return redirect(url_for('outgoing.list_outgoing'))



    # 📥 Скачивание вложения
    download_id = request.args.get('download')
    if download_id:
        attachment = Attachment.query.filter_by(
            id=download_id,
            letter_id=letter.id,
            letter_type='outgoing'
        ).first_or_404()

        if not os.path.exists(attachment.filepath):
            flash('Файл не найден на сервере.', 'danger')
            return redirect(url_for('outgoing.attachments', letter_id=letter.id))

        return send_file(
            attachment.filepath,
            as_attachment=True,
            download_name=attachment.filename,
            mimetype='application/octet-stream'
        )

    # 📤 Загрузка нового файла с проверкой на дубликаты
    if request.method == 'POST':
        file = request.files.get('file')
        if not file or file.filename.strip() == "":
            flash('Файл не выбран.', 'warning')
            return redirect(request.url)

        original_name = file.filename.strip()
        already = Attachment.query.filter_by(
            letter_id=letter.id,
            letter_type='outgoing',
            filename=original_name
        ).first()

        if not allowed_file(original_name):
            flash('Недопустимый формат файла. Разрешены только: PDF, Word, Excel, RAR.', 'danger')
            return redirect(request.url)

        if already and 'force' not in request.form:
            attachments = Attachment.query.filter_by(
                letter_id=letter.id, letter_type='outgoing'
            ).all()
            flash(f'Файл "{original_name}" уже прикреплён. Нажмите "Загрузить всё равно", чтобы подтвердить.', 'warning')
            return render_template(
                'outgoing/attachments.html',
                letter=letter,
                attachments=attachments,
                pending_upload=True,
                allowed_extensions=current_app.config['ALLOWED_EXTENSIONS']
            )

        save_attachment(file, letter, 'outgoing')
        flash('Вложение добавлено.', 'success')
        return redirect(request.url)

    # 📋 Получение всех вложений
    attachments = Attachment.query.filter_by(
        letter_id=letter.id, letter_type='outgoing'
    ).all()

    return render_template(
        'outgoing/attachments.html',
        letter=letter,
        attachments=attachments
    )

@outgoing_bp.route('/list')
@login_required
def list_outgoing():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', type=int)
    if per_page:
        session['outgoing_per_page'] = per_page
    else:
        per_page = session.get('outgoing_per_page', 10)

    # 🔍 Фильтры
    query = LetterOutgoing.query

    number = request.args.get('number', '').strip()
    if number:
        query = query.filter(LetterOutgoing.number.ilike(f"%{number}%"))

    recipient = request.args.get('recipient', '').strip()
    if recipient:
        query = query.filter(LetterOutgoing.recipient.ilike(f"%{recipient}%"))

    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    if date_from:
        query = query.filter(LetterOutgoing.date_created >= date_from)
    if date_to:
        query = query.filter(LetterOutgoing.date_created <= date_to)

    subject = request.args.get('subject', '').strip()
    if subject:
        query = query.filter(LetterOutgoing.subject.ilike(f"%{subject}%"))


    # 📋 Сортировка как у тебя была
    query = query.order_by(
        db.text("CAST(SUBSTRING(letter_outgoing.number FROM 3 FOR POSITION('/' IN letter_outgoing.number) - 3) AS INTEGER) DESC")
    )

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template(
        'outgoing/list.html',
        pagination=pagination,
        letters=pagination.items,
        per_page=per_page,
        search_params={
            'number': number,
            'subject': subject,
            'recipient': recipient,
            'date_from': date_from,
            'date_to': date_to
        }
    )


@outgoing_bp.route('/<int:letter_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_outgoing(letter_id):
    letter = LetterOutgoing.query.get_or_404(letter_id)
    if letter.user_id != current_user.id:
        flash('Доступ запрещён.', 'danger')
        return redirect(url_for('outgoing.list_outgoing'))

    form = OutgoingForm(obj=letter)
    form.is_protected.data = letter.is_protected
    if form.validate_on_submit():
        letter.subject = form.subject.data
        letter.recipient = form.recipient.data
        letter.is_protected = form.is_protected.data
        db.session.commit()
        flash('Письмо обновлено.', 'success')
        return redirect(url_for('outgoing.list_outgoing'))

    attachments = Attachment.query.filter_by(
        letter_id=letter.id, letter_type='outgoing'
    ).all()
    return render_template(
        'outgoing/edit.html',
        form=form,
        letter=letter,
        attachments=attachments
    )

@outgoing_bp.route('/<int:letter_id>/attachments/<int:attachment_id>/delete', methods=['POST'])
@login_required
def delete_attachment(letter_id, attachment_id):
    letter = LetterOutgoing.query.get_or_404(letter_id)

    # 🔐 Проверка прав доступа
    if current_user.role.name not in ['Admin', 'Editor']:
        flash('У вас нет прав для удаления вложений.', 'danger')
        return redirect(url_for('outgoing.attachments', letter_id=letter_id))

    attachment = Attachment.query.filter_by(
        id=attachment_id,
        letter_id=letter_id,
        letter_type='outgoing'
    ).first_or_404()

    # 🧹 Удаление файла с диска
    try:
        if os.path.exists(attachment.filepath):
            os.remove(attachment.filepath)
    except Exception as e:
        flash(f'Ошибка при удалении файла: {e}', 'warning')

    # ❌ Удаление из БД
    db.session.delete(attachment)
    db.session.commit()
    flash('Файл удалён.', 'success')
    return redirect(url_for('outgoing.attachments', letter_id=letter_id))


# Удаление исходящего письма
@outgoing_bp.route("/outgoing/delete/<int:letter_id>", methods=["POST"])
@admin_required
def delete_outgoing_letter(letter_id):  
    letter = LetterOutgoing.query.get_or_404(letter_id)
    letter.delete_with_attachments()
    db.session.commit()
    flash(f"Письмо {letter.number} успешно удалено ✅", "success")
    return redirect(url_for("outgoing.list_outgoing"))




# Експорт в exel
@outgoing_bp.route('/export')
@login_required
def export_outgoing():
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment
    from io import BytesIO

    query = LetterOutgoing.query

    number = request.args.get('number', '').strip()
    if number:
        query = query.filter(LetterOutgoing.number.ilike(f"%{number}%"))

    recipient = request.args.get('recipient', '').strip()
    if recipient:
        query = query.filter(LetterOutgoing.recipient.ilike(f"%{recipient}%"))

    subject = request.args.get('subject', '').strip()
    if subject:
        query = query.filter(LetterOutgoing.subject.ilike(f"%{subject}%"))


    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    if date_from:
        query = query.filter(LetterOutgoing.date_created >= date_from)
    if date_to:
        query = query.filter(LetterOutgoing.date_created <= date_to)

    

    query = query.order_by(
        db.text("CAST(SUBSTRING(letter_outgoing.number FROM 3 FOR POSITION('/' IN letter_outgoing.number) - 3) AS INTEGER) DESC")
    )

    letters = query.all()

    wb = Workbook()
    ws = wb.active
    ws.title = 'Исходящие'

    headers = ['Номер', 'Тема', 'Получатель', 'Дата']
    ws.append(headers)

    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal='center')

    for letter in letters:
        ws.append([
            letter.number,
            letter.subject,
            letter.recipient,
            letter.date_created.strftime('%Y-%m-%d') if letter.date_created else ''
        ])

    for column_cells in ws.columns:
        max_length = max(len(str(cell.value)) if cell.value else 0 for cell in column_cells)
        ws.column_dimensions[column_cells[0].column_letter].width = max_length + 4

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"Исходящие_{datetime.datetime.utcnow().strftime('%Y-%m-%d')}.xlsx"
    return send_file(
        output,
        download_name=filename,
        as_attachment=True,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
