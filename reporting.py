from datetime import datetime, timedelta
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from models import User, UsageRecord
from app import db
from sqlalchemy import create_engine
from app import app
from datetime import timezone
from flask import current_app
from sqlalchemy.orm import scoped_session, sessionmaker
from models import DeletedAccounts, StripeEvents
from models import Test, Feedback, DeckFiles, Deck, Card, EventTracking
from send_email import send_email_report
import os
from sqlalchemy import func
import csv

SQLALCHEMY_ENGINE_OPTIONS = os.environ.get("SQLALCHEMY_ENGINE_OPTIONS")
SQLALCHEMY_DATABASE_URI = os.environ.get("SQLALCHEMY_DATABASE_URI")
MAX_CONTENT = os.environ.get("MAX_CONTENT")
SQLALCHEMY_TRACK_MODIFICATIONS = os.environ.get("SQLALCHEMY_TRACK_MODIFICATIONS")

engine = create_engine(
    SQLALCHEMY_DATABASE_URI, **SQLALCHEMY_ENGINE_OPTIONS
)

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
        for _ in range(1):
            create_report()
