"""Extraction Engine - extracts job data from pages."""

from app.engines.extract.service import ExtractionEngine
from app.engines.extract.base import BaseExtractor, ExtractedJob

# Core ATS extractors
from app.engines.extract.greenhouse import GreenhouseExtractor
from app.engines.extract.lever import LeverExtractor
from app.engines.extract.ashby import AshbyExtractor
from app.engines.extract.workable import WorkableExtractor

# Extended ATS extractors
from app.engines.extract.bamboohr import BambooHRExtractor
from app.engines.extract.zoho_recruit import ZohoRecruitExtractor
from app.engines.extract.bullhorn import BullhornExtractor
from app.engines.extract.gem import GemExtractor
from app.engines.extract.jazzhr import JazzHRExtractor
from app.engines.extract.freshteam import FreshteamExtractor
from app.engines.extract.recruitee import RecruiteeExtractor
from app.engines.extract.pinpoint import PinpointExtractor
from app.engines.extract.pcrecruiter import PCRecruiterExtractor
from app.engines.extract.recruitcrm import RecruitCRMExtractor
from app.engines.extract.manatal import ManatalExtractor
from app.engines.extract.recooty import RecootyExtractor
from app.engines.extract.successfactors import SuccessFactorsExtractor
from app.engines.extract.gohire import GoHireExtractor
from app.engines.extract.folkshr import FolksHRExtractor
from app.engines.extract.boon import BoonExtractor
from app.engines.extract.talentreef import TalentReefExtractor
from app.engines.extract.eddy import EddyExtractor
from app.engines.extract.smartrecruiters import SmartRecruitersExtractor
from app.engines.extract.jobvite import JobviteExtractor
from app.engines.extract.icims import ICIMSExtractor

# Fallback extractors
from app.engines.extract.generic import GenericExtractor
from app.engines.extract.llm_fallback import LLMFallbackExtractor

__all__ = [
    "ExtractionEngine",
    "BaseExtractor",
    "ExtractedJob",
    # Core
    "GreenhouseExtractor",
    "LeverExtractor",
    "AshbyExtractor",
    "WorkableExtractor",
    # Extended
    "BambooHRExtractor",
    "ZohoRecruitExtractor",
    "BullhornExtractor",
    "GemExtractor",
    "JazzHRExtractor",
    "FreshteamExtractor",
    "RecruiteeExtractor",
    "PinpointExtractor",
    "PCRecruiterExtractor",
    "RecruitCRMExtractor",
    "ManatalExtractor",
    "RecootyExtractor",
    "SuccessFactorsExtractor",
    "GoHireExtractor",
    "FolksHRExtractor",
    "BoonExtractor",
    "TalentReefExtractor",
    "EddyExtractor",
    "SmartRecruitersExtractor",
    "JobviteExtractor",
    "ICIMSExtractor",
    # Fallback
    "GenericExtractor",
    "LLMFallbackExtractor",
]
