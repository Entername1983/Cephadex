from run.extensions import db

from models.association_tables import (
    cards, source_files, cards_shared, questions,
    distribution, deck_relationships, user_group_association, skills_category_skill
)

##  Decks folder
from models.decks.card_factory import CardFactory
from models.decks.deck import Deck
from models.decks.card import Card
from models.decks.deck_attributes import DeckAttributes
from models.decks.deck_files import DeckFiles

from models.decks.job import Job
from models.decks.job_notification import JobNotification
from models.decks.shared_decks import SharedDecks

## Games folder
from models.games.game_answer import GameAnswer
from models.games.game_vote import GameVote
from models.games.game import Game
from models.games.player_game import PlayerGame

## Group folder
from models.group.group_invite import GroupInvite
from models.group.group import Group

## Quiz folder
from models.quiz.question_result import QuestionResult
from models.quiz.question import Question
from models.quiz.quiz_result import TestResult
from models.quiz.quiz import Test

## Tracking
from models.tracking.cached_response import CachedResponse
from models.tracking.event_tracking import EventTracking
from models.tracking.feedback import Feedback
from models.tracking.response_data import ResponseData

## User
from models.user.deleted_accounts import DeletedAccounts
from models.user.subscriber import Subscriber
from models.user.subscription_plan import SubscriptionPlan
from models.user.usage_record import UsageRecord
from models.user.user_settings import UserSettings
from models.user.user import User


##  Gamification --> Need to fix names and remove underscores :/
from models.gamification import Skill, Skills_Category, User_Skill, Badge, Goal

