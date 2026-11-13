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
    SAVED = 'saved'
    APPLIED = 'applied'
    INTERVIEW = 'interview'
    REJECTED = 'rejected'
    ACCEPTED = 'accepted'


class SourceKind(StrEnum):
    SEARCH = 'search'
    BROWSER = 'browser'
    MANUAL = 'manual'
