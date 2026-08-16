from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from marshmallow import ValidationError
from app.schemas import StagingApproveSchema
from app.services.account_service import resolve_statement_account
from app.services.budget_service import parse_ing_csv, parse_mbank_csv, save_transactions_to_staging, approve_staging_record, reanalyze_all_staging, clear_pending_staging, accept_staging_contractor, list_pending_staging, dismiss_staging_as_duplicate
from app.services.statement_parsers import detect_bank_and_format, decode_statement_bytes, extract_statement_ibans, parse_mbank_html, parse_mbank_pdf, parse_ing_pdf
from app.services.import_history_service import list_import_history, record_batch

import_bp = Blueprint('import', __name__)

# Rejestr parserów wyciągów wg banku (CSV, ścieżka /api/import/<bank>).
# Każdy parser ma tę samą sygnaturę (file_content, user_token, main_account_id)
# i zwraca ten sam kształt wyniku, dzięki czemu dalszy przepływ
# (save_transactions_to_staging) jest bank-agnostyczny.
CSV_PARSERS = {
    'ing': parse_ing_csv,
    'mbank': parse_mbank_csv,
}

# Pełny rejestr (bank, format) -> (parser, tryb_wejścia).
# 'text' = parser przyjmuje zdekodowany str; 'bytes' = surowe bajty (PDF).
# Dodanie parsera = jedna pozycja tutaj + funkcja w services.
STATEMENT_PARSERS = {
    ('ing', 'csv'): (parse_ing_csv, 'text'),
    ('ing', 'pdf'): (parse_ing_pdf, 'bytes'),
    ('mbank', 'csv'): (parse_mbank_csv, 'text'),
    ('mbank', 'html'): (parse_mbank_html, 'text'),
    ('mbank', 'pdf'): (parse_mbank_pdf, 'bytes'),
}


def _read_upload():
    """Wspólna walidacja uploadu: zwraca (raw_bytes, error_response)."""
    if 'file' not in request.files:
        return None, (jsonify({'error': 'Brak pliku w żądaniu.'}), 400)
    file = request.files['file']
    if file.filename == '':
        return None, (jsonify({'error': 'Nie wybrano pliku.'}), 400)
    return file.read(), None


def _stage_and_respond(result: dict, user_token: str, extra: dict | None = None,
                       meta: dict | None = None):
    """Wspólne zakończenie importu: zapis do stagingu + historia + odpowiedź."""
    transactions = result['transactions']
    skipped_count = result['skipped_count']
    meta = meta or {}

    if not transactions:
        msg = 'Plik nie zawiera poprawnych transakcji lub jest uszkodzony.'
        if skipped_count:
            msg += f' Pominięto {skipped_count} transakcji z kont nieznanych aplikacji.'
        return jsonify({'error': msg}), 400

    try:
        overlap_warning = record_batch(
            user_token=user_token,
            transactions=transactions,
            filename=meta.get('filename') or 'wyciąg',
            bank=meta.get('bank') or 'nieznany',
            file_format=meta.get('format') or 'nieznany',
            skipped_count=skipped_count,
        )
        saved_records = save_transactions_to_staging(transactions, user_token=user_token)
        resp: dict = {
            'message': f'Udało się zaimportować {len(saved_records)} transakcji do weryfikacji.',
            'count': len(saved_records),
        }
        if result['csv_accounts']:
            resp['csv_accounts'] = result['csv_accounts']
        if skipped_count:
            resp['skipped_count'] = skipped_count
        if overlap_warning:
            resp['overlap_warning'] = overlap_warning
        if extra:
            resp.update(extra)
        return jsonify(resp), 201
    except ValueError as e:
        # Rollback należy do serwisów — record_batch i save_transactions_to_staging
        # same wycofują swoją transakcję, zanim podniosą wyjątek.
        return jsonify({'error': str(e)}), 400


@import_bp.route('/api/import/history', methods=['GET'])
@login_required
def import_history():
    """Historia wgranych wyciągów bieżącego użytkownika."""
    return jsonify(list_import_history(current_user.token)), 200


@import_bp.route('/api/import/auto', methods=['POST'])
@login_required
def import_auto():
    """Import z automatyczną detekcją banku i formatu po zawartości pliku."""
    user_token = current_user.token

    raw, err = _read_upload()
    if err:
        return err

    bank, fmt = detect_bank_and_format(raw, request.files['file'].filename or '')
    if bank is None or fmt is None:
        detected = f" (rozpoznany format: {fmt.upper()})" if fmt else ''
        return jsonify({'error': f'Nie rozpoznano banku lub formatu pliku{detected}. Wybierz bank ręcznie z listy.'}), 400

    entry = STATEMENT_PARSERS.get((bank, fmt))
    if entry is None:
        return jsonify({'error': f'Wykryto wyciąg {bank.upper()} w formacie {fmt.upper()} — ten format nie jest jeszcze obsługiwany.'}), 400
    parser, input_mode = entry

    if input_mode == 'text':
        try:
            payload = decode_statement_bytes(raw)
        except UnicodeDecodeError:
            return jsonify({'error': 'Nieobsługiwane kodowanie pliku. Oczekiwano UTF-8 lub Windows-1250 (eksport z banku).'}), 400
    else:
        payload = raw

    # Rozpoznanie konta po numerze rachunku z NAGŁÓWKA wyciągu (mBank ma go
    # w każdym formacie). Chroni przed importem na złe konto i pozwala
    # importować wiele plików bez ręcznego wskazywania konta per plik.
    try:
        account_id, matched = resolve_statement_account(
            user_token, extract_statement_ibans(raw, bank, fmt), request.form.get('account_id')
        )
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    resolved_account = {'id': matched.id, 'name': matched.name} if matched else None

    try:
        result = parser(
            payload,
            user_token=user_token,
            main_account_id=int(account_id) if account_id else None
        )
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    extra = {'detected': {'bank': bank, 'format': fmt}}
    if resolved_account:
        extra['resolved_account'] = resolved_account
    return _stage_and_respond(result, user_token, extra=extra,
                              meta={'filename': request.files['file'].filename,
                                    'bank': bank, 'format': fmt})


@import_bp.route('/api/import/<bank>', methods=['POST'])
@login_required
def import_csv(bank):
    user_token = current_user.token

    parser = CSV_PARSERS.get(bank.lower())
    if parser is None:
        return jsonify({'error': f"Nieobsługiwany bank: '{bank}'. Dostępne: {', '.join(sorted(CSV_PARSERS))}."}), 400

    raw, err = _read_upload()
    if err:
        return err

    try:
        file_content = decode_statement_bytes(raw)
    except UnicodeDecodeError:
        return jsonify({'error': 'Nieobsługiwane kodowanie pliku. Oczekiwano UTF-8 lub Windows-1250 (eksport z banku).'}), 400

    account_id = request.form.get('account_id')

    # Własność konta sprawdzana PRZED parsowaniem — bez tego dało się wskazać cudze
    # konto w formularzu importu (statement_ibans=[] bo ten endpoint nie wykrywa IBAN-u
    # z nagłówka, ale resolve_statement_account i tak waliduje chosen_account_id — #127).
    if account_id:
        try:
            account_id, _ = resolve_statement_account(user_token, [], account_id)
        except ValueError as e:
            return jsonify({'error': str(e)}), 400

    try:
        result = parser(
            file_content,
            user_token=user_token,
            main_account_id=int(account_id) if account_id else None
        )
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    return _stage_and_respond(result, user_token,
                              meta={'filename': request.files['file'].filename,
                                    'bank': bank, 'format': 'csv'})

@import_bp.route('/api/staging/pending', methods=['GET'])
@login_required
def get_pending_staging_transactions():
    return jsonify(list_pending_staging(current_user.token)), 200

@import_bp.route('/api/staging/reanalyze', methods=['POST'])
@login_required
def reanalyze_staging():
    """Ponownie uruchamia autokategoryzację na wszystkich pending rekordach stagingu."""
    try:
        count = reanalyze_all_staging(current_user.token)
        return jsonify({'message': f'Przeanalizowano ponownie {count} rekordów.', 'count': count}), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 500

@import_bp.route('/api/staging/pending', methods=['DELETE'])
@login_required
def clear_pending_staging_transactions():
    try:
        deleted_count = clear_pending_staging(current_user.token)
        return jsonify({'message': f'Odrzucono {deleted_count} transakcji.'}), 200
    except ValueError:
        return jsonify({'error': 'Wystąpił błąd podczas odrzucania transakcji.'}), 500

@import_bp.route('/api/staging/<int:stg_id>/accept-contractor', methods=['POST'])
@login_required
def accept_suggested_contractor(stg_id):
    data = request.get_json() or {}
    name = data.get('name', '').strip()

    if not name:
        return jsonify({'error': 'Nazwa kontrahenta nie może być pusta.'}), 400

    try:
        result = accept_staging_contractor(current_user.token, stg_id, name)
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 404 if 'Nie znaleziono' in str(e) else 500


@import_bp.route('/api/staging/<int:stg_id>/duplicate-of', methods=['POST'])
@login_required
def mark_staging_duplicate(stg_id):
    """Użytkownik wskazał, że wiersz stagingu to ta sama operacja co istniejąca transakcja."""
    data = request.get_json() or {}
    transaction_id = data.get('transaction_id')

    if not isinstance(transaction_id, int):
        return jsonify({'error': 'Wymagane pole transaction_id (liczba całkowita).'}), 400

    try:
        dismiss_staging_as_duplicate(current_user.token, stg_id, transaction_id)
        return jsonify({'message': 'Wiersz odrzucony jako duplikat.'}), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 404 if 'Nie znaleziono' in str(e) else 400


@import_bp.route('/api/staging/<int:stg_id>/approve', methods=['POST'])
@login_required
def approve_staging_transaction(stg_id):
    user_token = current_user.token

    try:
        data = StagingApproveSchema().load(request.get_json() or {})
        new_tx = approve_staging_record(user_token, stg_id, data)
        return jsonify({'message': 'Transakcja zatwierdzona.', 'transaction_id': new_tx.id}), 200
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400
    except ValueError as err:
        return jsonify({'error': str(err)}), 400
