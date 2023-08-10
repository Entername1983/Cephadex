from datetime import datetime
from models.extensions import db, migrate


class DeletedAccounts(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer)
    email = db.Column(db.String(255))
    date_created = db.Column(db.DateTime)
    date_deleted = db.Column(db.DateTime, default=datetime.utcnow)
    reason = db.Column(db.String(255))
    reason_details = db.Column(db.Text)