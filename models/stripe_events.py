from datetime import datetime
from run.extensions import db


class StripeEvents(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    stripe_event_id = db.Column(db.String(255), nullable=True)
    event_type = db.Column(db.String(255), nullable=True)
    event_data = db.Column(db.Text, nullable=True)
    # event_created = db.Column(db.DateTime, default=datetime.utcnow)
    time_created = db.Column(db.DateTime, default=datetime.utcnow)

    stripe_customer_id = db.Column(db.String(255), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    processed = db.Column(db.Boolean, default=False)
    processed_at = db.Column(db.DateTime, nullable=True)
    error_message = db.Column(db.String(255), nullable=True)