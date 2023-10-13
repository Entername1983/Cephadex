
from datetime import datetime
from run.extensions import db

class BlogPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    slug = db.Column(db.String(100))
    content = db.Column(db.Text)
    summary = db.Column(db.Text)
    author_name = db.Column(db.String(100))
    tags = db.Column(db.String(100))
    thumbnail = db.Column(db.String(100))
    tags = db.Column(db.String(100))
    time_created = db.Column(db.DateTime, default=datetime.utcnow)
    time_updated = db.Column(db.DateTime, nullable=True)
    views = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))


    def to_json(self):
        return {
            "id": self.id,
            "title": self.title,
            "slug": self.slug,
            "content": self.content,
            "summary": self.summary,
            "author_name": self.author_name,
            "tags": self.tags,
            "thumbnail": self.thumbnail,
            "time_created": self.time_created,
            "time_updated": self.time_updated,
            "views": self.views,
            "user_id": self.user_id
        }