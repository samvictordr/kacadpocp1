"""
Dashboard Pages Package
"""
from . import home
from . import user_management
from . import bulk_upload
from . import allowances
from . import cost_centers
from . import telemetry
from . import settings

__all__ = [
    "home",
    "user_management", 
    "bulk_upload",
    "allowances",
    "cost_centers",
    "telemetry",
    "settings"
]