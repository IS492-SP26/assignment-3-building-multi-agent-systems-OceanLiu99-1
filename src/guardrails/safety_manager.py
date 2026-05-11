"""
Safety Manager
Coordinates safety guardrails and logs safety events.
"""

from typing import Dict, Any, List, Optional
import logging
from datetime import datetime
import json

from .input_guardrail import InputGuardrail
from .output_guardrail import OutputGuardrail


class SafetyManager:
    """
    Manages safety guardrails for the multi-agent system.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize safety manager.

        Args:
            config: Safety configuration
        """
        self.config = config
        self.enabled = config.get("enabled", True)
        self.log_events = config.get("log_events", True)
        self.logger = logging.getLogger("safety")

        # Safety event log
        self.safety_events: List[Dict[str, Any]] = []

        # Prohibited categories
        self.prohibited_categories = config.get("prohibited_categories", [
            "harmful_content",
            "personal_attacks",
            "misinformation",
            "off_topic_queries"
        ])

        # Violation response strategy
        self.on_violation = config.get("on_violation", {})
        full_config = {"safety": config}
        self.input_guardrail = InputGuardrail(full_config)
        self.output_guardrail = OutputGuardrail(full_config)

    def check_input_safety(self, query: str) -> Dict[str, Any]:
        """
        Check if input query is safe to process.

        Args:
            query: User query to check

        Returns:
            Dictionary with 'safe' boolean and optional 'violations' list
        """
        if not self.enabled:
            return {"safe": True, "query": query}

        validation = self.input_guardrail.validate(query)
        violations = validation.get("violations", [])
        is_safe = validation.get("valid", False)
        action = self.on_violation.get("action", "refuse") if not is_safe else "allow"

        if not is_safe and self.log_events:
            self._log_safety_event("input", query, violations, is_safe)

        result = {
            "safe": is_safe,
            "violations": violations,
            "query": validation.get("sanitized_input", query),
            "action": action,
        }

        if not is_safe and action == "refuse":
            result["message"] = self.on_violation.get(
                "message",
                "I cannot process this request due to safety policies.",
            )

        return result

    def check_output_safety(
        self,
        response: str,
        sources: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Check if output response is safe to return.

        Args:
            response: Generated response to check
            sources: Optional source metadata used by output validation

        Returns:
            Dictionary with 'safe' boolean and optional 'violations' list
        """
        if not self.enabled:
            return {"safe": True, "response": response}

        validation = self.output_guardrail.validate(response, sources)
        violations = validation.get("violations", [])
        is_safe = validation.get("valid", False)
        action = self.on_violation.get("action", "refuse") if not is_safe else "allow"

        if not is_safe and self.log_events:
            self._log_safety_event("output", response, violations, is_safe)

        result = {
            "safe": is_safe,
            "violations": violations,
            "response": response,
            "action": action,
        }

        if not is_safe:
            if action == "sanitize":
                result["response"] = validation.get(
                    "sanitized_output",
                    self._sanitize_response(response, violations),
                )
            elif action == "refuse":
                result["response"] = self.on_violation.get(
                    "message",
                    "I cannot provide this response due to safety policies."
                )

        return result

    def _sanitize_response(self, response: str, violations: List[Dict[str, Any]]) -> str:
        """
        Sanitize response by removing or redacting unsafe content.
        """
        return self.output_guardrail._sanitize(response, violations)

    def _log_safety_event(
        self,
        event_type: str,
        content: str,
        violations: List[Dict[str, Any]],
        is_safe: bool
    ):
        """
        Log a safety event.

        Args:
            event_type: "input" or "output"
            content: The content that was checked
            violations: List of violations found
            is_safe: Whether content passed safety checks
        """
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "safe": is_safe,
            "violations": violations,
            "content_preview": content[:100] + "..." if len(content) > 100 else content
        }

        self.safety_events.append(event)
        self.logger.warning(f"Safety event: {event_type} - safe={is_safe}")

        # Write to safety log file if configured
        log_file = self.config.get("safety_log_file")
        if log_file and self.log_events:
            try:
                with open(log_file, "a") as f:
                    f.write(json.dumps(event) + "\n")
            except Exception as e:
                self.logger.error(f"Failed to write safety log: {e}")

    def get_safety_events(self) -> List[Dict[str, Any]]:
        """Get all logged safety events."""
        return self.safety_events

    def get_safety_stats(self) -> Dict[str, Any]:
        """
        Get statistics about safety events.

        Returns:
            Dictionary with safety statistics
        """
        total = len(self.safety_events)
        input_events = sum(1 for e in self.safety_events if e["type"] == "input")
        output_events = sum(1 for e in self.safety_events if e["type"] == "output")
        violations = sum(1 for e in self.safety_events if not e["safe"])

        return {
            "total_events": total,
            "input_checks": input_events,
            "output_checks": output_events,
            "violations": violations,
            "violation_rate": violations / total if total > 0 else 0
        }

    def clear_events(self):
        """Clear safety event log."""
        self.safety_events = []
