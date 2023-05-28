import csv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import SQLALCHEMY_DATABASE_URI, SQLALCHEMY_ENGINE_OPTIONS
from models import User, Subscriber



engine = create_engine(
    SQLALCHEMY_DATABASE_URI, **SQLALCHEMY_ENGINE_OPTIONS
)

Session = sessionmaker(bind=engine)


def write_csv(data, filename):
    with open(filename, 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(["email", "first_name", "last_name"])
        for row in data:
            writer.writerow(row)

def fetch_data():
    session = Session()
    
    # Fetch subscribers
    subscribers = session.query(Subscriber.email, Subscriber.first_name, Subscriber.last_name).all()
    write_csv(subscribers, 'subscribers.csv')
    
    # Fetch users with contacted_email = true
    contacted_users = session.query(User.email, User.first_name, User.last_name)\
        .filter(User.contacted_email == True).all()
    write_csv(contacted_users, 'contacted.csv')

    # Combine subscribers and contacted users
    all_mail = list(set(subscribers + contacted_users))
    write_csv(all_mail, 'all_mail.csv')

fetch_data()