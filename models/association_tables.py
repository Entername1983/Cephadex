from run.extensions import db

# relational database cards & decks
cards = db.Table("cards", 
                 db.Column("card_id", db.Integer, db.ForeignKey("card.id", ondelete="CASCADE")), 
                 db.Column("deck_id", db.Integer, db.ForeignKey("deck.id", ondelete="CASCADE")),
                 )

source_files = db.Table("source_files",
                        db.Column("deck_file_id", db.Integer, db.ForeignKey("deck_files.id", ondelete="CASCADE")), 
                        db.Column("deck_id", db.Integer, db.ForeignKey("deck.id", ondelete="CASCADE")),  # 
                        )

cards_shared = db.Table("cards_shared", 
                 db.Column("card_id", db.Integer, db.ForeignKey("card.id", ondelete="CASCADE")), 
                 db.Column("shared_decks_id", db.Integer, db.ForeignKey("shared_decks.id", ondelete="CASCADE")),
                 )    
                         
questions = db.Table("questions",
                        db.Column("test_id", db.Integer, db.ForeignKey("test.id", ondelete="CASCADE")),
                        db.Column("question_id", db.Integer, db.ForeignKey("question.id", ondelete="CASCADE")),
                        db.Column("position", db.Integer),
                        db.Column("text", db.String(255)),
                        db.Column("image", db.String(255))
                     )
distribution = db.Table("distribution",
                        db.Column("test_id", db.Integer, db.ForeignKey("test.id", ondelete="CASCADE")),	
                        db.Column("taker_id", db.Integer, db.ForeignKey("user.id", ondelete="CASCADE")),	
                        )	

deck_relationships = db.Table("deck_relationships", 
                               db.Column("parent_deck", db.Integer, db.ForeignKey("deck.id", ondelete="CASCADE")),
                               db.Column("child_deck", db.Integer, db.ForeignKey("deck.id", ondelete="CASCADE"))  # 
                               )

user_group_association = db.Table("user_group_association",
                                  db.Column("user_id", db.Integer, db.ForeignKey("user.id", ondelete="CASCADE")),
                                  db.Column("group_id", db.Integer, db.ForeignKey("group.id", ondelete="CASCADE")),
                                  db.Column("role", db.String(255)),
                                  db.Column("permissions", db.String(255)),)


skills_category_skill = db.Table('skills_category_skill',
    db.Column('skill_id', db.Integer, db.ForeignKey('skill.id'), primary_key=True),
    db.Column('category_id', db.Integer, db.ForeignKey('skills_category.id'), primary_key=True)
)