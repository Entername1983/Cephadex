from models import User, SubscriptionPlan, UsageRecord
from app import db
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from app import app
from sqlalchemy.orm import scoped_session, sessionmaker
from models.tracking.events import event_tracker
from datetime import timezone
from models.extensions import db
from models.decks.job import Job
from models.decks.card_factory import CardFactory
from models.decks.card import Card
from models.decks.deck import Deck
from models.decks.card_pre_processor import CardPreProcessor
from models.decks.deck_attributes import DeckAttributes
from models.decks.deck_files import DeckFiles
from models.decks.job_notification import JobNotification
from models.decks.shared_decks import SharedDecks
from models.games.game_answer import GameAnswer
from models.games.game_vote import GameVote
from models.games.game import Game
from models.games.player_game import PlayerGame
from models.groups.group_invite import GroupInvite
from models.groups.group import Group
from models.quiz.question_result import QuestionResult
from models.quiz.question import Question
from models.quiz.quiz import Test
from models.quiz.quiz_result import TestResult
from models.tracking.cached_response import CachedResponse
from models.tracking.event_tracking import EventTracking
from models.tracking.feedback import Feedback
from models.tracking.response_data import ResponseData
from models.user.deleted_accounts import DeletedAccounts
from models.user.subscriber import Subscriber
from models.user.user_settings import UserSettings
from models.stripe_events import StripeEvents
from models.association_tables import cards, source_files, cards_shared, questions
from models.association_tables import distribution, deck_relationships, user_group_association
from models.association_tables import skills_category_skill
from models.creators.creator import AiCaller
from models.creators.formatters import count_tokens, token_encoding, token_decoding, split_tokens, remove_html_tags, add_period, check_comma_list, add_underscores, comma_list_to_list, clean_text, insert_paragraph, double_backlash
from models.extractors.extractor import Extractor
from models.send_email import send_email_report
import os
from sqlalchemy import func
import csv
import json

SQLALCHEMY_ENGINE_OPTIONS = json.loads(os.environ['SQLALCHEMY_ENGINE_OPTIONS'])
SQLALCHEMY_DATABASE_URI = os.environ.get("SQLALCHEMY_DATABASE_URI")
MAX_CONTENT = os.environ.get("MAX_CONTENT")
SQLALCHEMY_TRACK_MODIFICATIONS = os.environ.get("SQLALCHEMY_TRACK_MODIFICATIONS")



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
        


def create_report():
    csv_file_path = 'report.csv'

    # Check if CSV file exists, create it if not
    is_new_file = not os.path.isfile(csv_file_path)
    with open(csv_file_path, 'a', newline='') as csv_file:
        writer = csv.writer(csv_file)
        if is_new_file:
            # Write categories as the first column
            categories = ['User Accounts Created', 'Deleted Accounts', 'Stripe Events', 'Usage Records', 'Cards Created', 'Decks Created', 'Deck Files', 'Feedback', 'Tests Created', 'Event Types']
            writer.writerow(['Date'] + categories)

    # Get counts for each metric
    user_accounts_created = count_user_accounts_created()
    deleted_accounts = count_deleted_accounts_by_reason()
    stripe_events = count_stripe_events()
    usage_records = count_usage_record()
    cards_created = count_card_created_by_type()
    decks_created = count_decks_created()
    deck_files = count_deck_files()
    feedback = list_feedback()
    tests_created = count_tests_created()
    event_types = count_events_by_type()

    # Create a new row with the data and time
    row_data = [
        datetime.now().strftime('%Y-%m-%d %H'),
        {'accounts_created': user_accounts_created},
        {'deleted_accounts': deleted_accounts},
        {'stripe_events': stripe_events},
        {'usage_records': usage_records},
        {'cards_created': cards_created},
        {'decks_created': decks_created},
        {'deck_files': deck_files},
        {'feedback': feedback},
        {'tests_created': tests_created},
        {'event_types': event_types}
    ]

    # Append the row to the CSV file
    with open(csv_file_path, 'a', newline='') as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(row_data)
    
    formatted_report = f"{datetime.now().strftime('%Y-%m-%d %H')}, \
                    {'accounts_created':<20} {user_accounts_created}, \
                    {'deleted_accounts':<20} {deleted_accounts}, \
                    {'stripe_events':<20} {stripe_events}, \
                    {'usage_records':<20} {usage_records}, \
                    {'cards_created':<20} {cards_created}, \
                    {'decks_created':<20} {decks_created}, \
                    {'deck_files':<20} {deck_files}, \
                    {'feedback':<20} {feedback}, \
                    {'tests_created':<20} {tests_created}, \
                    {'event_types':<20} {event_types}"


    # Send email with the report
    send_email_report('pro.mccarthy@gmail.com', formatted_report)





def count_user_accounts_created():
    start_time = datetime.now(timezone.utc) - timedelta(hours=24)
    count = User.query.filter(User.time_created >= start_time).count()
    return count

def count_deleted_accounts_by_reason():
    start_time = datetime.utcnow() - timedelta(hours=24)
    deleted_accounts = DeletedAccounts.query.filter(
        DeletedAccounts.date_deleted >= start_time
    ).all()

    count_by_reason = {}
    for account in deleted_accounts:
        reason = account.reason
        count_by_reason[reason] = count_by_reason.get(reason, 0) + 1

    return count_by_reason

def count_stripe_events():
    start_time = datetime.now(timezone.utc) - timedelta(hours=24)
    event_counts = (
        db.session.query(
            StripeEvents.event_type,
            func.count(StripeEvents.event_type)
        )
        .filter(StripeEvents.event_created >= start_time)
        .group_by(StripeEvents.event_type)
        .all()
    )

    event_counts_dict = {event_type: count for event_type, count in event_counts}
    return event_counts_dict


def count_usage_record():
    start_time = datetime.utcnow() - timedelta(hours=24)
    usage_records = UsageRecord.query.filter(
        UsageRecord.date >= start_time
    ).all()

    count_by_operation = {}
    for record in usage_records:
        operation = record.operation_type
        count_by_operation[operation] = count_by_operation.get(operation, 0) + 1

    return count_by_operation

def count_card_created_by_type():
    start_time = datetime.utcnow() - timedelta(hours=24)
    cards_created = Card.query.filter(
        Card.time_created >= start_time
    ).count()
    return cards_created

def count_decks_created():
    start_time = datetime.utcnow() - timedelta(hours=24)
    decks_created = Deck.query.filter(
        Deck.time_created >= start_time
    ).all()
    count_by_type = {}
    for deck in decks_created:
        create_method = deck.create_method
        count_by_type[create_method] = count_by_type.get(create_method, 0) + 1
    return count_by_type

def count_deck_files():
    start_time = datetime.utcnow() - timedelta(hours=24)
    deck_files = DeckFiles.query.filter(
        DeckFiles.time_created >= start_time
    ).all()
    count_by_type = {}
    for deck in deck_files:
        file_type = deck.file_type
        count_by_type[file_type] = count_by_type.get(file_type, 0) + 1
    return count_by_type

def list_feedback():
    start_time = datetime.utcnow() - timedelta(hours=24)
    feedback = Feedback.query.filter(
        Feedback.timestamp >= start_time
    ).all()
    feedback_list = []
    for message in feedback:
        feedback_list.append(message.message)
    return feedback_list


def count_tests_created():
    start_time = datetime.utcnow() - timedelta(hours=24)
    count = Test.query.filter(Test.time_created >= start_time).count()
    return count

def count_events_by_type():
    start_time = datetime.utcnow() - timedelta(hours=24)
    events = EventTracking.query.filter(EventTracking.created_at >= start_time).all()

    event_counts = {}
    for event in events:
        event_type = event.event_type
        event_counts[event_type] = event_counts.get(event_type, 0) + 1

    return event_counts



if __name__ == "__main__":
    # Set up SQLAlchemy session and run roll over function
    with app.app_context():
        Session = scoped_session(sessionmaker(bind=engine))
        roll_over()
        delete_accounts()
        create_report()