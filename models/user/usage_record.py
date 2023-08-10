from datetime import datetime
from models.extensions import db, migrate



class UsageRecord(db.Model):
    __tablename__ = 'usage_records'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    operation_type = db.Column(db.String(50), nullable=False)
    operation_details = db.Column(db.String(1000))
    operation_count = db.Column(db.Integer, nullable=False)
    remaining_count = db.Column(db.Integer, nullable=False)
    time_period = db.Column(db.String(50), nullable=False)
    limit_count = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(50), nullable=False, default='active')
    source_ip = db.Column(db.String(50))
    payment_status = db.Column(db.String(50), default='unpaid')

    def __repr__(self):
        return f'<UsageRecord {self.id}>'