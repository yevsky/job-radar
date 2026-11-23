"""SQLAlchemy models: the shape of the database tables."""

from app.models.ai_analysis import AiAnalysis
from app.models.application import Application, ApplicationStatusChange
from app.models.chat import ChatAction, Conversation, ConversationMessage
from app.models.job_offer import JobOffer
from app.models.resume import Resume
from app.models.role import Role
from app.models.search_run import SearchRun
from app.models.search_source_switch import SearchSourceSwitch
from app.models.technology import Technology
from app.models.user import User
from app.models.user_preferred_employment_type import UserPreferredEmploymentType
from app.models.user_preferred_location import UserPreferredLocation
from app.models.user_profile import UserProfile

__all__ = [
    'Role',
    'User',
    'UserProfile',
    'UserPreferredLocation',
    'UserPreferredEmploymentType',
    'Technology',
    'JobOffer',
    'SearchRun',
    'SearchSourceSwitch',
    'Application',
    'ApplicationStatusChange',
    'Resume',
    'AiAnalysis',
    'Conversation',
    'ConversationMessage',
    'ChatAction',
]
