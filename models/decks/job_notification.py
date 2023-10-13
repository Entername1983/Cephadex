from datetime import datetime
from run.extensions import db

class JobNotification(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'),
                         nullable=True)
    slug = db.Column(db.String(128), nullable=False)
    state = db.Column(db.String(10), nullable=False, default="queued")
    complete = db.Column(db.Boolean, default=False)
    notified = db.Column(db.Boolean, default=False)
    # date_created = db.Column(db.DateTime, default=datetime.utcnow)
    time_created = db.Column(db.DateTime, default=datetime.utcnow)
    cost = db.Column(db.Integer, default=0)
    input_details = db.Column(db.String(128), nullable=True)
    extract_type = db.Column(db.String(128), nullable=True)