from datetime import datetime
from models.extensions import db, migrate

class EventTracking(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'),
                      nullable=True)
    event_type = db.Column(db.String(64), nullable=True)
    event_data = db.Column(db.Text, nullable=True)
    event_details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True)
    