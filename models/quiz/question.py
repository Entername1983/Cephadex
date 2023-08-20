
from run.extensions import db

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    question = db.Column(db.String(1000), nullable=False)
    term = db.Column(db.String(1000), nullable=False)
    content = db.Column(db.String(1000), nullable=False)
    boc_2 = db.Column(db.String(1000), nullable=True) 
    boc_3 = db.Column(db.String(1000), nullable=True) 
    boc_4 = db.Column(db.String(255), nullable=True)
    formula = db.Column(db.String(255), nullable=True)
    prompt_option = db.Column(db.String(255), nullable=True)
    q_type = db.Column(db.String(50), nullable=True)
    q_order = db.Column(db.Integer, nullable=True)
    points = db.Column(db.Integer, nullable=True)
