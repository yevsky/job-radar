from enum import StrEnum


class ExperienceLevel(StrEnum):
    TRAINEE = 'trainee'
    JUNIOR = 'junior'
    MIDDLE = 'middle'
    SENIOR = 'senior'
    LEAD = 'lead'


class EmploymentType(StrEnum):
    FULL_TIME = 'full_time'
    PART_TIME = 'part_time'
    CONTRACT = 'contract'
    INTERNSHIP = 'internship'
    B2B = 'b2b'


class ApplicationStatus(StrEnum):
    """Where the user is with one offer, from saving it to the final answer."""

    SAVED = 'saved'
    APPLIED = 'applied'
    SCREENING = 'screening'
    INTERVIEW = 'interview'
    OFFER = 'offer'
    ACCEPTED = 'accepted'
    REJECTED = 'rejected'
    DECLINED = 'declined'


class SourceKind(StrEnum):
    SEARCH = 'search'
    BROWSER = 'browser'
    MANUAL = 'manual'
    POSTED = 'posted'
