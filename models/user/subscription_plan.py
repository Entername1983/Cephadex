from run.extensions import db


class SubscriptionPlan(db.Model):
    __tablename__ = 'subscription_plans'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200))
    limit_count = db.Column(db.Integer, nullable=False)
    limit_time_period = db.Column(db.String(50), nullable=False, default='month')
    price = db.Column(db.Float, nullable=False)
    duration = db.Column(db.Integer, default = 31)
    users = db.relationship('User', backref='subscription_plan_id')

    def __repr__(self):
        return f'<SubscriptionPlan {self.id}>'