from app import ma
from marshmallow import fields, validate, post_load
from app.models import Frequency, Category, Account, Contractor # Import models for nested schemas or enums

class RegisterSchema(ma.Schema):
    username = fields.String(required=True, validate=validate.Length(min=3))
    email = fields.Email(required=True)
    password = fields.String(required=True, validate=validate.Length(min=6))

class LoginSchema(ma.Schema):
    username = fields.String(required=False)
    email = fields.String(required=False)
    password = fields.String(required=True)

class AccountSchema(ma.Schema):
    name = fields.String(required=True, validate=validate.Length(min=1))
    bank_name = fields.String(load_default="")
    account_number = fields.String(load_default="")
    is_default = fields.Boolean(load_default=False)
    owner = fields.String(load_default=None, allow_none=True)
    co_owner = fields.String(load_default=None, allow_none=True)

class CategorySchema(ma.Schema):
    name = fields.String(required=True, validate=validate.Length(min=1))
    type = fields.String(required=True, validate=validate.OneOf(['income', 'expense', 'transfer']))

class ContractorSchema(ma.Schema):
    name = fields.String(required=True, validate=validate.Length(min=1))
    rules = fields.String(load_default="")
    default_category_id = fields.Integer(load_default=None, allow_none=True)
    category = fields.String(load_default=None, allow_none=True)

class SplitSchema(ma.Schema):
    amount = fields.Float(required=True)
    desc = fields.String(load_default="")
    category = fields.String(required=True)

class TransactionSchema(ma.Schema):
    title = fields.String(required=False)
    desc = fields.String(required=False)
    amount = fields.Float(required=True)
    date = fields.String(required=True)
    category = fields.String(load_default=None, allow_none=True)
    contractor_id = fields.Integer(load_default=None, allow_none=True)
    account_id = fields.Integer(required=True)
    splits = fields.List(fields.Nested(SplitSchema), load_default=[])
    comment = fields.String(load_default=None, allow_none=True, validate=validate.Length(max=255))

class StagingApproveSchema(ma.Schema):
    category = fields.String(required=True)
    contractor_id = fields.Integer(required=True)

class PlannedTransactionSchema(ma.Schema):
    id = fields.Integer(dump_only=True)
    user_id = fields.Integer(dump_only=True)
    account_id = fields.Integer(required=True)
    category_id = fields.Integer(required=True, allow_none=False)
    contractor_id = fields.Integer(allow_none=True)
    
    title = fields.String(required=True, validate=validate.Length(min=1, max=120))
    amount = fields.Decimal(required=True, as_string=True)
    
    execution_date = fields.Date(required=True, format='%Y-%m-%d')
    status = fields.String(dump_only=True)
    created_at = fields.DateTime(dump_only=True)

class RecurringTransactionSchema(ma.Schema):
    id = fields.Integer(dump_only=True)
    user_id = fields.Integer(dump_only=True)
    account_id = fields.Integer(required=True)
    category_id = fields.Integer(allow_none=True)
    contractor_id = fields.Integer(allow_none=True)
    
    title = fields.String(required=True, validate=validate.Length(min=1, max=120))
    amount = fields.Decimal(required=True, as_string=True) # Allow negative for now, frontend will handle sign
    
    frequency = fields.Enum(Frequency, required=True, by_value=True)
    interval = fields.Integer(load_default=1, validate=validate.Range(min=1))
    day_of_week = fields.Integer(allow_none=True, validate=validate.Range(min=0, max=6)) # 0=Mon, 6=Sun
    day_of_month = fields.Integer(allow_none=True, validate=validate.Range(min=1, max=31)) # 1-31

    start_date = fields.Date(required=True, format='%Y-%m-%d')
    end_date = fields.Date(allow_none=True, format='%Y-%m-%d')
    next_run_date = fields.Date(dump_only=True, format='%Y-%m-%d') # Calculated by backend
    
    is_active = fields.Boolean(load_default=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    # Optional: Nested fields for relationships if needed for dumping detailed info
    # account = fields.Nested(AccountSchema, dump_only=True)
    # category = fields.Nested(CategorySchema, dump_only=True)
    # contractor = fields.Nested(ContractorSchema, dump_only=True)

    @post_load
    def validate_frequency_specific_fields(self, data, **kwargs):
        freq = data.get('frequency')
        day_of_week = data.get('day_of_week')
        day_of_month = data.get('day_of_month')

        if freq == Frequency.WEEKLY and day_of_week is None:
            raise validate.ValidationError("day_of_week is required for WEEKLY frequency.", "day_of_week")
        if freq == Frequency.MONTHLY and day_of_month is None:
            raise validate.ValidationError("day_of_month is required for MONTHLY frequency.", "day_of_month")
            
        return data