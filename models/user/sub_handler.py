
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

logger = logging.getLogger("payment")


class StripeEventHandler:
    def __init__(self, api_key= None):
        stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
        self.plan_modifier = PlanModifier()
        self.customer_id = None
        self.user_id = None
        self.price_id = None
        self.account_status = None
        self.event_type = None
        self.customer_email = None

    def handle_event(self, event):
        print("----------------------------------------------------")
        self.log_stripe_event(event)
        self.event_type = event['type']
        print(dt.datetime.now(dt.timezone.utc), event['type'])


        customer_data = event['data']['object']
        if 'customer' in customer_data:
            print("customer in customer_data")
            self.customer_id = customer_data.get('customer')
            print(self.customer_id)
        else:
            self.customer_id = customer_data['id']
    
        self.customer_email = customer_data.get('email')

        self.price_id = event['data']['object'].get('items', {}).get('data', [{}])[0].get('price', {}).get('id')
        self.account_status = event['data']['object'].get('status')

        self.user_id = event['data']['object'].get('client_reference_id')
        if self.user_id is None:
            self.user_id = event['data']['object'].get('metadata', {}).get('user_id')
        if self.user_id is None:
            user = User.query.filter_by(stripe_customer_id=self.customer_id).first()
            if user:
                self.user_id = user.id
        
        print(f"customer_id: {self.customer_id}, user_id: {self.user_id}, price_id: {self.price_id}, account_status: {self.account_status}, customer_email: {self.customer_email}")


        ## Use to associate user_id with stripe customer id
        if self.event_type == 'checkout.session.completed':
            self.handle_checkout_session()

        ## associate stripe customer id with my customer id
        elif self.event_type == 'customer.created':
            self.handle_customer_creation()


        ## create customer subscription
        elif self.event_type == 'customer.subscription.created':
            self.handle_subscription_creation()

        ## Set customer subscription to free tier
        elif self.event_type == 'customer.subscription.deleted':
            self.handle_subscription_deletion()

        ## update customer subscription
        elif self.event_type == 'customer.subscription.updated':
            self.handle_subscription_update()

        ## send email notification trial will end
        elif self.event_type == 'customer.subscription.trial_will_end':
            self.handle_subscription_trial_end()

        ## set customer subscription to free tier
        elif self.event_type == 'customer.deleted':
            self.handle_customer_deletion()

        ## update customer details
        elif self.event_type == 'customer.updated':
            self.handle_customer_update()

        elif self.event_type == 'invoice.created':
            self.handle_invoice_created()
        
        elif self.event_type == 'invoice.payment_failed':
            self.handle_invoice_payment_failed()

        elif self.event_type == 'invoice.payment_succeeded':
            self.handle_invoice_payment_succeeded()

        elif self.event_type == 'invoice.paid':
            self.handle_invoice_paid()
        
        elif self.event_type == 'invoice.updated':
            self.handle_invoice_updated()

        elif self.event_type == 'invoice.finalized':
            self.handle_invoice_finalized()
        
        elif self.event_type == 'invoice_finalization_failed':
            self.handle_invoice_finalization_failed()


    def handle_customer_creation(self):
        logger.info("customer created")
        self.associate_stripe_customer_with_user(self.user_id, self.customer_id)

    def handle_subscription_creation(self):
        logger.info("subscription created")
        if self.account_status == "trialing":
            self.plan_modifier.update_user_subscription(self.user_id, self.price_id, self.account_status)
        if self.account_status == "active":
            self.plan_modifier.update_user_subscription(self.user_id, self.price_id, self.account_status)
        if self.account_status == "paid":
            self.plan_modifier.update_user_subscription(self.user_id, self.price_id, self.account_status)


    def handle_subscription_deletion(self):
        logger.info("subscription deleted")
        self.plan_modifier.update_user_subscription(self.user_id, self.price_id, self.account_status)

        
    def handle_subscription_update(self):
        logger.info("handle subscription update")
        ## ensure subscription is active
        if self.account_status == 'active':
            self.plan_modifier.update_user_subscription(self.user_id, self.price_id, self.account_status)
        if self.account_status == 'canceled':
            self.plan_modifier.update_user_subscription(self.user_id, self.price_id, self.account_status)


    def handle_subscription_trial_end(self):
        logger.info(f"trial ending in 3 days for {self.user_id}")
        user = User.query.filter_by(stripe_customer_id=self.customer_id).first()
        send_email(user.email, user.first_name, "trial_over")


    def handle_new_subscription_with_existing_customer(self, user, stripe_customer_id):
        logger.info(f"changing user {user.id} to have a new stripe customer id {stripe_customer_id}, previous stripe id was {user.stripe_customer_id}")
        user.stripe_customer_id = stripe_customer_id
        db.session.commit()

    def handle_invoice_paid(self):
        customer_id = self.customer_id
        user = User.query.filter_by(stripe_customer_id=customer_id).first()
        if not user:
            ## Call stripe API and search for customer ID
            ## Associate customer with user
            logger.critical(f"user {customer_id} not found, cannot handle invoice_paid event")

        if user.account_status == "active":
            ## user is already subscribed, subrollover takes care of updating credit
            pass
        if user.account_status in ["free", "trialing"]:
            user.subscription_start_date = dt.datetime.now(dt.timezone.utc)
            user.account_status = "active"
            user.account_type = "paid"
            self.plan_modifier.update_user_subscription(self.user_id, self.price_id, self.account_status)
            db.session.commit()

    def handle_customer_deletion(self):
        logger.info("customer deleted")
        self.plan_modifier.update_user_subscription(self.user_id, self.price_id, 'canceled')
        

    def handle_customer_update(self):
        logger.info("customer updated")

    def handle_checkout_session(self):
        print(f"user_id: {self.user_id}")
        self.associate_stripe_customer_with_user()
        self.add_user_id_metadata_to_stripe_customer()
        subscriptions = stripe.Subscription.list(customer=self.customer_id)
        self.price_id = subscriptions['data'][0]['items']['data'][0]['price']['id']
        self.account_status = subscriptions['data'][0]['status']
        print(self.account_status)
        print(self.price_id)
        self.plan_modifier.update_user_subscription(self.user_id, self.price_id, self.account_status)


    def log_stripe_event(self, event, user_id= None):
        time_created = dt.datetime.now(dt.timezone.utc)
        stripe_event = StripeEvents(stripe_event_id=event['id'], event_type=event['type'],
                event_data=json.dumps(event), time_created=time_created, user_id=user_id,
                stripe_customer_id=self.customer_id,
            )
        db.session.add(stripe_event)
        db.session.commit()
        return stripe_event
    

    def associate_stripe_customer_with_user(self):
        print("calling associate_stripe_customer_with_user")
        logger.info(f"associating stripe customer id {self.customer_id} with user {self.user_id}")
        user = User.query.filter_by(id=self.user_id).first()
        if user.stripe_customer_id is not None:
            if user.stripe_customer_id == self.customer_id:
                logger.info(f"User {self.user_id} already has a stripe customer id {user.stripe_customer_id}, which matches {self.customer_id}")
                return
            error_message = f"User {self.user_id} already has a stripe customer id {user.stripe_customer_id}, which conflicts with:{self.customer_id} - modifying to use original stripe customer id"
            logger.critical(error_message)
            event = StripeEvents(event_type = "customer_id_conflict", user_id = self.user_id, stripe_customer_id = user.stripe_customer_id, error_message = error_message)
            try:
                stripe.Customer.modify(
                    str(user.stripe_customer_id), metadata={'user_id': str(user.id)})
                time.sleep(2)

            except stripe.error.InvalidRequestError:
                print("Unable associate meta data with user, stripe customer id does not exist")
            db.session.add(event)
            self.customer_id = user.stripe_customer_id
        else:
            user.stripe_customer_id = self.customer_id
        db.session.commit()
        return user.id


    def add_user_id_metadata_to_stripe_customer(self):
        print("calling add_user_id_metadata_to_stripe_customer")
        print(self.user_id)
        try:
            stripe.Customer.modify(
                str(self.customer_id), metadata={'user_id': self.user_id})
            time.sleep(2)
        except stripe.error.InvalidRequestError:
            print("Unable associate meta data with user, stripe customer id does not exist")

    def handle_invoice_created(self):
        logger.info(f"invoice created")

    def handle_invoice_payment_failed(self):
        logger.error(f"invoice payment failed")

    def handle_invoice_payment_succeeded(self):
        logger.info(f"invoice payment succeeded")

    def handle_invoice_updated(self):
        logger.info(f"invoice updated")

    def handle_invoice_finalized(self):
        logger.info(f"invoice finalized ")

    def handle_invoice_finalization_failed(self):
        logger.info(f"invoice finalization failed")





class PlanModifier:
    def __init__(self):
        self.user = None
        self.plan = None

    def update_user_subscription(self, user_id, price_id, status):
        user = User.query.filter_by(id=user_id).first()
        if not user:
            logger.critical(f"Unable to update user subscription, user_id {user_id} not found")
            return
        if user.account_status == status:
            logger.error(f"user {user.id} is already in {status} mode")
            return f"user is already in {status} mode"
        self.user = user
        self.plan = PLAN_CONFIG.get(price_id)
        user.subscription_plan = self.plan['subscription_plan']
        user.subscription_start_date = dt.datetime.now(dt.timezone.utc)
        user.subscription_latest_roll_over = dt.datetime.now(dt.timezone.utc)
        if status == "trialing":
            user.subscription_end_date =dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=7)
        user.account_status = status
        if status == "canceled":
            send_email(user.email, user.first_name, 'sub_cancelled')
        elif status in ["upgrade", "sub_changed", "complete"]:
            send_email(user.email, user.first_name, status)
        self.set_usage_limit(user, self.plan['usage_limit'])
        db.session.commit()

    def set_usage_limit(self, user, n):
        if self.plan in ['premium_yearly', 'premium_monthly']:
            latest_record = UsageRecord.query.filter_by(user_id=user.id).order_by(UsageRecord.date.desc()).first()
            n = latest_record.remaining_count + n
        new_record = UsageRecord(user_id=user.id, operation_type="Update plan",
            limit_count=n, operation_count=0, remaining_count=n, date=dt.datetime.now(dt.timezone.utc),
            time_period="month",
        )
        db.session.add(new_record)
        db.session.commit()

