"""
Structured logging for auditability.
All side effects must be logged.
"""
import logging
import sys
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional, Union
import json


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)


class AuditLogger:
    """
    Audit logger for tracking all system side effects.
    Logs are structured JSON for easy parsing and analysis.
    """
    
    def __init__(self, name: str = "academy"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # Console handler with JSON formatting
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(logging.INFO)
            formatter = logging.Formatter('%(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def _log(
        self,
        level: str,
        event: str,
        actor_id: Optional[str] = None,
        actor_role: Optional[str] = None,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> None:
        """Internal logging method that produces structured JSON."""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "event": event,
            "actor": {
                "id": actor_id,
                "role": actor_role
            } if actor_id else None,
            "target": {
                "type": target_type,
                "id": target_id
            } if target_type else None,
            "details": details,
            "error": error
        }
        
        # Remove None values for cleaner logs
        log_entry = {k: v for k, v in log_entry.items() if v is not None}
        
        log_method = getattr(self.logger, level.lower())
        log_method(json.dumps(log_entry, cls=DecimalEncoder))
    
    def info(
        self,
        event: str,
        actor_id: Optional[str] = None,
        actor_role: Optional[str] = None,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None
    ) -> None:
        """Log an informational event."""
        self._log("INFO", event, actor_id, actor_role, target_type, target_id, details)
    
    def warning(
        self,
        event: str,
        actor_id: Optional[str] = None,
        actor_role: Optional[str] = None,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None
    ) -> None:
        """Log a warning event."""
        self._log("WARNING", event, actor_id, actor_role, target_type, target_id, details)
    
    def error(
        self,
        event: str,
        error: str,
        actor_id: Optional[str] = None,
        actor_role: Optional[str] = None,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None
    ) -> None:
        """Log an error event."""
        self._log("ERROR", event, actor_id, actor_role, target_type, target_id, details, error)
    
    # Specific audit events
    def log_login(self, user_id: str, role: str, success: bool, ip: Optional[str] = None) -> None:
        """Log a login attempt."""
        event = "auth.login.success" if success else "auth.login.failure"
        self.info(event, actor_id=user_id, actor_role=role, details={"ip": ip})
    
    def log_password_change(self, user_id: str, role: str) -> None:
        """Log a password change."""
        self.info("auth.password.changed", actor_id=user_id, actor_role=role)
    
    def log_attendance_scan(
        self,
        teacher_id: str,
        student_id: str,
        session_id: str,
        status: str
    ) -> None:
        """Log an attendance scan."""
        self.info(
            "attendance.scan",
            actor_id=teacher_id,
            actor_role="teacher",
            target_type="student",
            target_id=student_id,
            details={"session_id": session_id, "status": status}
        )
    
    def log_store_transaction(
        self,
        staff_id: str,
        student_id: str,
        amount: Union[Decimal, float],
        balance_after: Union[Decimal, float],
        location: Optional[str] = None
    ) -> None:
        """Log a store transaction."""
        self.info(
            "store.transaction",
            actor_id=staff_id,
            actor_role="store",
            target_type="student",
            target_id=student_id,
            details={
                "amount": amount,
                "balance_after": balance_after,
                "location": location
            }
        )
    
    def log_allowance_reset(
        self,
        admin_id: str,
        target_id: Optional[str] = None,
        scope: str = "single"
    ) -> None:
        """Log an allowance reset."""
        self.info(
            "admin.allowance.reset",
            actor_id=admin_id,
            actor_role="admin",
            target_type="student" if target_id else "all",
            target_id=target_id,
            details={"scope": scope}
        )
    
    def log_user_created(
        self,
        admin_id: str,
        new_user_id: str,
        role: str
    ) -> None:
        """Log user creation."""
        self.info(
            "admin.user.created",
            actor_id=admin_id,
            actor_role="admin",
            target_type="user",
            target_id=new_user_id,
            details={"new_user_role": role}
        )


# Global audit logger instance
audit_log = AuditLogger()
