from datetime import datetime
from run.extensions import db


class DeletedAccounts(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer)
    email = db.Column(db.String(255))
    time_created = db.Column(db.DateTime)
    time_deleted = db.Column(db.DateTime, default=datetime.utcnow)
    reason = db.Column(db.String(255))
    reason_details = db.Column(db.Text)