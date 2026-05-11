"""
Output Guardrail
Checks system outputs for safety violations.
"""

from typing import Dict, Any, List
import re


class OutputGuardrail:
    """
    Guardrail for checking output safety.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize output guardrail.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        safety_config = config.get("safety", {})
        self.guardrail_backend = safety_config.get("framework", None)
        self.max_response_length = safety_config.get("max_response_length", 8000)
        self.require_sources = safety_config.get("require_sources", False)

    def validate(self, response: str, sources: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Validate output response.

        Args:
            response: Generated response to validate
            sources: Optional list of sources used (for fact-checking)

        Returns:
            Validation result
        """
        violations = []

        if not isinstance(response, str):
            return {
                "valid": False,
                "violations": [{
                    "validator": "format",
                    "reason": "Response must be a string",
                    "severity": "high",
                }],
                "sanitized_output": "",
            }

        if len(response) > self.max_response_length:
            violations.append({
                "validator": "length",
                "reason": "Response too long",
                "severity": "low",
            })

        pii_violations = self._check_pii(response)
        violations.extend(pii_violations)

        harmful_violations = self._check_harmful_content(response)
        violations.extend(harmful_violations)

        violations.extend(self._check_bias(response))
        violations.extend(self._check_factual_consistency(response, sources or []))

        return {
            "valid": not any(v.get("severity") in {"high", "medium"} for v in violations),
            "violations": violations,
            "sanitized_output": self._sanitize(response, violations) if violations else response
        }

    def _check_pii(self, text: str) -> List[Dict[str, Any]]:
        """
        Check for personally identifiable information.
        """
        violations = []

        patterns = {
            "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            "phone": r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
            "ssn": r'\b\d{3}-\d{2}-\d{4}\b',
            "credit_card": r'\b(?:\d[ -]*?){13,16}\b',
        }

        for pii_type, pattern in patterns.items():
            matches = re.findall(pattern, text)
            if matches:
                violations.append({
                    "validator": "pii",
                    "pii_type": pii_type,
                    "reason": f"Contains {pii_type}",
                    "severity": "high",
                    "matches": matches
                })

        return violations

    def _check_harmful_content(self, text: str) -> List[Dict[str, Any]]:
        """
        Check for harmful or inappropriate content.
        """
        violations = []

        harmful_keywords = [
            "make a bomb",
            "build a bomb",
            "poison someone",
            "kill someone",
            "kill yourself",
            "deploy malware",
            "steal passwords",
        ]
        for keyword in harmful_keywords:
            if keyword in text.lower():
                violations.append({
                    "validator": "harmful_content",
                    "reason": f"May contain harmful content: {keyword}",
                    "severity": "high"
                })

        return violations

    def _check_factual_consistency(
        self,
        response: str,
        sources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Check if response is consistent with sources.
        """
        violations = []

        if self.require_sources and not sources:
            violations.append({
                "validator": "factual_consistency",
                "reason": "No sources provided for source-required output",
                "severity": "medium",
            })

        if sources and "[citation needed]" in response.lower():
            violations.append({
                "validator": "factual_consistency",
                "reason": "Response contains unsupported citation placeholder",
                "severity": "low",
            })

        return violations

    def _check_bias(self, text: str) -> List[Dict[str, Any]]:
        """
        Check for biased language.
        """
        violations = []
        biased_patterns = [
            "all women",
            "all men",
            "all immigrants",
            "all disabled people",
            "all elderly people",
        ]

        normalized = text.lower()
        for pattern in biased_patterns:
            if pattern in normalized:
                violations.append({
                    "validator": "bias",
                    "reason": f"Potential biased generalization: {pattern}",
                    "severity": "medium",
                })

        return violations

    def _sanitize(self, text: str, violations: List[Dict[str, Any]]) -> str:
        """
        Sanitize text by removing/redacting violations.
        """
        sanitized = text

        if any(
            violation.get("severity") == "high"
            and violation.get("validator") != "pii"
            for violation in violations
        ):
            return "I cannot provide this response due to safety policies."

        for violation in violations:
            if violation.get("validator") == "pii":
                for match in violation.get("matches", []):
                    sanitized = sanitized.replace(match, "[REDACTED]")

        return sanitized
