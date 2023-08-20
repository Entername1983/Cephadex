from datetime import datetime
from run.extensions import db


class GroupInvite(db.Model):
    __tablename__ = "group_invite"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    group_id = db.Column(db.Integer, db.ForeignKey("group.id"))
    group = db.relationship("Group", foreign_keys=[group_id])
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    invited_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    invited_by_email = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)