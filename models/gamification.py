from datetime import datetime
from models.association_tables import skills_category_skill

from run.extensions import db


class Skills_Category(db.Model):
    __tablename__ = 'skills_category'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

class Skill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    users = db.relationship('User_Skill', backref='skill')
    categories = db.relationship('Skills_Category',
                                  secondary=skills_category_skill, backref='skills')
    
class User_Skill(db.Model):
    __tablename__ = 'user_skill'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'),
                         nullable=False)
    skill_id = db.Column(db.Integer, db.ForeignKey('skill.id'), nullable=False)

class Badge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    avatar = db.Column(db.String(100), nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey('skills_category.id'),
                             nullable=True)

class Goal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'),
                         nullable=False)
    skill_id = db.Column(db.Integer, db.ForeignKey('skill.id'), nullable=False)
    skill = db.relationship('Skill', backref='goals')
    target_level = db.Column(db.Integer, nullable=False)
    start_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    end_date = db.Column(db.DateTime)
