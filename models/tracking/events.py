from models.tracking.event_tracking import EventTracking
from models.extensions import db

def event_tracker(user_id, event_type, event_data = None, event_details = None):
    event = EventTracking(user=user_id, event_type=event_type, event_data=event_data, event_details=event_details)
    db.session.add(event)
    db.session.commit()
    return True