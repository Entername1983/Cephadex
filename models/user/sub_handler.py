
import stripe
import os
import datetime as dt
import uuid
from models.stripe_events import StripeEvents
import time
from models.helpers.log_decorators import log_decorator
import json
from models.models_ import UsageRecord, User
from run.extensions import db
import logging
from models.user.stripe_config import PLAN_CONFIG
from models.send_email import send_email

logger = logging.getLogger("flask_app")


class StripeEventHandler:
    def __init__(self, api_key= None):
        stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

    def handle_event(self, event):
        event_type = event['type']
        self.log_stripe_event(event)
        if event_type == 'customer.created':
            self.handle_customer_creation(event)
        elif event_type == 'checkout.session.completed':
            self.handle_checkout_session(event)
        elif event_type == 'customer.subscription.deleted':
            self.handle_subscription_deletion(event)
        elif event_type == 'customer.subscription.updated':
            self.handle_subscription_update(event)
        elif event_type == 'customer.subscription.created':
            self.handle_subscription_creation(event)
        elif event_type == 'customer.subscription.trial_will_end':
            self.handle_subscription_trial_end(event)
        elif event_type == 'customer.deleted':
            self.handle_customer_deletion(event)
        elif event_type == 'customer.updated':
            self.handle_customer_update(event)


    def handle_checkout_session(self, event):
        user_id = event['data']['object']['client_reference_id']
        self.associate_stripe_customer_with_user(event)
        time.sleep(1) ## giving webhook time to return a response
        stripe_event = self.log_stripe_event(event, user_id)
        line_items = stripe.checkout.Session.list_line_items(event['data']['object']['id'])
        logger.info(f"user id is {user_id}, line items are {line_items}")
        if line_items.data:
            try:
                item = line_items.data[0]
                # product_id = item['price']['product']        
                price_id = item['price']['id']
                # Retrieve the product details from Stripe API
                # product = stripe.Product.retrieve(product_id)
                # product_name = product['name']
                update_plan(user_id, price_id)
                stripe_event.processed = True
                stripe_event.processed_at = dt.datetime.now(dt.timezone.utc)
            except Exception as e:
            # Update the StripeEvents table with the error message if processing fails
                stripe_event.error_message = str(e)
                logger.critical(f'Exception in process_event_in_background - stripe {e} - see db')
                logger.error('Exception in process_event_background'
                                        'function):%s', e)
                raise e
            finally:
                db.session.commit()

    def handle_subscription_deletion(self, event):
        stripe_customer_id = event['data']['object']['customer']
        user = User.query.filter_by(stripe_customer_id=stripe_customer_id).first()
        update_plan(user, 0)
        send_email(user.email, user.first_name, "sub_cancelled")
        
    def handle_subscription_update(self, event):
        ## ensure subscription is active
        sub_is_active = event['data']['object']['status']
        if sub_is_active == 'active':
            stripe_customer_id = event['data']['object']['customer']

            user = User.query.filter_by(stripe_customer_id=stripe_customer_id).first()
            if event['items']['data']:
                price_id = event['items']['data'][0]['price']['id']
                update_plan(user, price_id)
            # line_items = stripe.checkout.Session.list_line_items(event['data']['object']['id'])
            # if line_items.data:
            #     item = line_items.data[0]
            #     price_id = item['price']['id']
            #     update_plan(user, price_id)

    def handle_subscription_creation(self, event):
        pass
    def handle_customer_deletion(self, event):
        pass
    def handle_customer_update(self, event):
        pass
    def handle_customer_creation(self, event):
        logger.info("customer created")


    def handle_subscription_trial_end(self, event):
        stripe_customer_id = event['data']['object']['customer']
        subscription = event['data']['object']
        timestamp = subscription.get('trial_end')
        dt_object = dt.datetime.fromtimestamp(timestamp)
        ## TO DO - Add end of trial time to email
        user = User.query.filter_by(stripe_customer_id=stripe_customer_id).first()
        send_email(user.email, user.first_name, "trial_over")
        logger.info(f"trial ended at {dt_object}")

    def associate_stripe_customer_with_user(self, event):
        try:
            idempo = str(uuid.uuid4())
            user_id = event['data']['object']['client_reference_id']
            stripe_customer_id = event['data']['object']['customer']
            ## modify user entry in DB
            user = User.query.filter_by(id=user_id).first()
            if user.stripe_customer_id is not None:
                logger.critical(f"User {user_id} already has a stripe customer id {user.stripe_customer_id}, which conflicts with:{stripe_customer_id}")
                self.handle_new_subscription_with_existing_customer(user, stripe_customer_id)
            user.stripe_customer_id = stripe_customer_id
            ## modify stripe customer entry
            stripe.Customer.modify(
                stripe_customer_id,
                metadata={'user_id': user_id},
                idempotency_key=idempo, 
                )
            db.session.commit()
            return user
        except Exception as e:
            logger.critical(f"Exception in associate_stripe_customer_with_user - stripe {e}, stripe customer id {stripe_customer_id},")
            raise e
        
    def handle_new_subscription_with_existing_customer(self, user, stripe_customer_id):
        pass

    def log_stripe_event(self, event, user_id: None):
        created_at = dt.datetime.now(dt.timezone.utc)
        stripe_event = StripeEvents(
                stripe_event_id=event['id'],
                event_type=event['type'],
                event_data=json.dumps(event),
                event_created=created_at,
                user_id=user_id,
                stripe_customer_id=event['data']['object']['customer'],
            )
        db.session.add(stripe_event)
        db.session.commit()
        return stripe_event
    
@log_decorator
def update_plan(user, price_id):
    plan = PLAN_CONFIG.get(price_id)
    if not plan:
        logger.error(f"Plan {price_id} not found.")
        return
    user.subscription_plan = plan['subscription_plan']
    user.subscription_start_date = dt.datetime.now(dt.timezone.utc)
    user.subscription_latest_roll_over = dt.datetime.now(dt.timezone.utc)
    set_usage_limit(user, plan['usage_limit'])
    send_email(user.email, user.first_name, 'upgrade')
    db.session.commit()
    
@log_decorator
def set_usage_limit(user, n):
    new_record = UsageRecord(
        user_id=user.id,
        operation_type="Change plan",
        limit_count=n,
        operation_count=0,
        remaining_count=n,
        date=dt.datetime.now(dt.timezone.utc),
        time_period = "month",
    )
    db.session.add(new_record)
    db.session.commit()
