# app/routes/my_letters.py

from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from app.models import LetterOutgoing, LetterIncoming
from app import db
import datetime
from flask import send_file

my_letters_bp = Blueprint(
    'my_letters', __name__,
    template_folder='../templates/my_letters'
)

@my_letters_bp.route('/outgoing')
@login_required
def outgoing_list():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    query = LetterOutgoing.query.filter_by(user_id=current_user.id)

    number = request.args.get('number', '').strip()
    if number:
        query = query.filter(LetterOutgoing.number.ilike(f"%{number}%"))

    subject = request.args.get('subject', '').strip()
    if subject:
        query = query.filter(LetterOutgoing.subject.ilike(f"%{subject}%"))

    recipient = request.args.get('recipient', '').strip()
    if recipient:
        query = query.filter(LetterOutgoing.recipient.ilike(f"%{recipient}%"))

    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    if date_from:
        query = query.filter(LetterOutgoing.date_created >= date_from)
    if date_to:
        query = query.filter(LetterOutgoing.date_created <= date_to)

    query = query.order_by(
        db.text("CAST(SUBSTRING(letter_outgoing.number FROM 3 FOR POSITION('/' IN letter_outgoing.number) - 3) AS INTEGER) DESC")
    )

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template(
        'my_letters/outgoing.html',
        letters=pagination.items,
        pagination=pagination,
        per_page=per_page,
        search_params={
            'number': number,
            'subject': subject,
            'recipient': recipient,
            'date_from': date_from,
            'date_to': date_to
        }
    )

# Експорт в Exel
@my_letters_bp.route('/export')
@login_required
def export_my_letters():
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment
    from io import BytesIO

    query = LetterOutgoing.query.filter_by(user_id=current_user.id)

    number = request.args.get('number', '').strip()
    if number:
        query = query.filter(LetterOutgoing.number.ilike(f"%{number}%"))

    subject = request.args.get('subject', '').strip()
    if subject:
        query = query.filter(LetterOutgoing.subject.ilike(f"%{subject}%"))

    recipient = request.args.get('recipient', '').strip()
    if recipient:
        query = query.filter(LetterOutgoing.recipient.ilike(f"%{recipient}%"))

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
    ws.title = 'Мои письма'

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

    filename = f"Мои_письма_{datetime.datetime.utcnow().strftime('%Y-%m-%d')}.xlsx"
    return send_file(
        output,
        download_name=filename,
        as_attachment=True,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


# @my_letters_bp.route('/incoming')
# @login_required
# def incoming_list():
#     """
#     Список входящих писем текущего пользователя.
#     """
#     page = request.args.get('page', 1, type=int)
#     pagination = LetterIncoming.query \
#         .filter_by(user_id=current_user.id) \
#         .order_by(LetterIncoming.date_received.desc()) \
#         .paginate(page=page, per_page=10, error_out=False)

#     return render_template(
#         'my_letters/incoming.html',
#         letters=pagination.items,
#         pagination=pagination
#     )
