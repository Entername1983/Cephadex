from datetime import datetime
from run.extensions import db

class QuestionResult(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    test_id = db.Column(db.Integer, db.ForeignKey('test.id', ondelete='SET NULL'),
                         nullable=True)
    taker = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'),
                       nullable=True)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'))
    answer = db.Column(db.String(2500))
    points = db.Column(db.Integer)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    quiz_result_id = db.Column(db.Integer, db.ForeignKey('test_result.id', ondelete='SET NULL'))
