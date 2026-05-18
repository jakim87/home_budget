from app import ma
from marshmallow import fields, validate

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

class CategorySchema(ma.Schema):
    name = fields.String(required=True, validate=validate.Length(min=1))
    type = fields.String(required=True, validate=validate.OneOf(['income', 'expense', 'transfer']))

class ContractorSchema(ma.Schema):
    name = fields.String(required=True, validate=validate.Length(min=1))
    rules = fields.String(load_default="")
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

class StagingApproveSchema(ma.Schema):
    category = fields.String(required=True)
    contractor_id = fields.Integer(required=True)