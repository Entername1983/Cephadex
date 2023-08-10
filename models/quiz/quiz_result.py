from models.extensions import db, migrate
from models.quiz.question_result import QuestionResult

class TestResult(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    test_id = db.Column(db.Integer, db.ForeignKey('test.id', ondelete='SET NULL'))
    taker = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'),
                       nullable=True)
    creator = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'),
                         nullable=True)
    due_date = db.Column(db.DateTime)
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    points = db.Column(db.Integer)
    correct = db.Column(db.Integer)
    blank = db.Column(db.Integer)
    
    def sum_points(self):
        points = 0
        question_results = QuestionResult.query.filter_by(test_id=self.test_id, 
                                                          taker=self.taker).all()
        for questions in question_results:
            if questions.points is None:
                questions.points = 0
            points = points + questions.points
        self.points = points