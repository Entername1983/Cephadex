from models import User, SubscriptionPlan, UsageRecord
from app import db
from datetime import datetime, timedelta
from config import SQLALCHEMY_DATABASE_URI, SQLALCHEMY_ENGINE_OPTIONS, CONST_PLAN
from sqlalchemy import create_engine
from app import app
from flask import current_app
from sqlalchemy.orm import scoped_session, sessionmaker
from models import UsageRecord, SubscriptionPlan, User, cards, source_files, cards_shared, questions, distribution
from events import event_tracker
engine = create_engine(
    SQLALCHEMY_DATABASE_URI, **SQLALCHEMY_ENGINE_OPTIONS
)
print(engine)

def roll_over():
    # Set up Flask application context
    with app.app_context():
        # Query active subscriptions
        subscriptions = User.query.filter_by(account_status='active').all()
        # Loop through each subscription and check if 30 days have passed
        for subscription in subscriptions:
            if subscription.latest_roll_over is None:
                if subscription.subscription_start_date == None:
                    subscription.subscription_start_date = datetime.utcnow()
                
                subscription.latest_roll_over = subscription.subscription_start_date 
            if subscription.latest_roll_over + timedelta(days=30) <= datetime.utcnow():
                print("rolling over " + subscription.username)
                subscription.latest_roll_over = datetime.utcnow()
                # Reset the usage limit for this subscription type
                user = User.query.filter_by(id=subscription.id).first()
                db.session.add(user)
                user.latest_roll_over = datetime.utcnow()
                subscription_plan = SubscriptionPlan.query.filter_by(id=user.subscription_plan).first()
                usage_limit = subscription_plan.limit_count
                new_record = UsageRecord(
                    user_id=subscription.id,
                    operation_type="reset",
                    limit_count=usage_limit,
                    operation_count=0,
                    remaining_count=usage_limit,
                    date=datetime.utcnow(),
                    time_period = "month",
                )
                db.session.add(new_record)
                db.session.commit()
                    

        # Save changes to the database
        db.session.commit()
        return "Usage limits have been reset successfully."


def delete_accounts():
    accounts_to_delete = User.query.filter_by(account_expiration_reason='deleted').all()
    for account in accounts_to_delete:
        print(account.id)
        event_tracker(account.id, "delete_account", "account deleted", account.email)
        print("Deleted account: " + account.username)
        db.session.delete(account)
        db.session.commit()
        


if __name__ == "__main__":
    # Set up SQLAlchemy session and run roll over function
    with app.app_context():
        Session = scoped_session(sessionmaker(bind=engine))
        roll_over()
        delete_accounts()