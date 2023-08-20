from run.extensions import db



class UserSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'),
                      nullable=True)
    language = db.Column(db.String(50))
    theme = db.Column(db.String(50))
    new_user = db.Column(db.Boolean, default = True)
    new_user_study = db.Column(db.Boolean, default = True)
    new_user_decks = db.Column(db.Boolean, default = True)
    new_user_tests = db.Column(db.Boolean, default = True)
    new_user_cards = db.Column(db.Boolean, default = True)
    srs_setting_1 = db.Column(db.Integer)
    srs_setting_2 = db.Column(db.Integer)
    srs_setting_3 = db.Column(db.Integer)
    srs_setting_4 = db.Column(db.Integer)        
        