"""
Input Guardrail
Checks user inputs for safety violations.
"""

from typing import Dict, Any, List


class InputGuardrail:
    """
    Guardrail for checking input safety.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize input guardrail.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        
        safety_config = config.get("safety", {})
        self.min_query_length = safety_config.get("min_query_length", 5)
        self.max_query_length = safety_config.get("max_query_length", 2000)
        self.policy_categories = safety_config.get(
            "policy_categories", ["harmful_content", "prompt_injection", "off_topic"]
            )
        self.guardrail_backend = safety_config.get("framework",None)
        self.toxicity_guard = None

        if self.guardrail_backend == "guardrails":
            try:
                from guardrails import Guard
                from guardrails.hub import ToxicLanguage

                self.toxicity_guard = Guard().use(
                    ToxicLanguage,
                    threshold=safety_config.get("toxicity_threshold", 0.5),
                    validation_method=safety_config.get(
                        "toxicity_validation_method", "sentence"
                    ),
                    on_fail="exception",
                )
            except Exception:
                self.toxicity_guard = None

    def validate(self, query: str) -> Dict[str, Any]:
        """
        Validate input query.

        Args:
            query: User input to validate

        Returns:
            Validation result

        TODO: YOUR CODE HERE
        - Implement validation logic
        - Check for toxic language
        - Check for prompt injection attempts
        - Check query length and format
        - Check for off-topic queries
        """
        violations = []

        sanitized_input = " ".join(query.strip().split())

        # Placeholder checks
        if len(query) < self.min_query_length:
            violations.append({
                "validator": "length",
                "reason": "Query too short",
                "severity": "low"
            })

        if len(query) > self.max_query_length:
            violations.append({
                "validator": "length",
                "reason": "Query too long",
                "severity": "medium"
            })

        enabled_categories = set(self.policy_categories)
        if "harmful_content" in enabled_categories:
            violations.extend(self._check_toxic_language(sanitized_input))
        if "prompt_injection" in enabled_categories:
            violations.extend(self._check_prompt_injection(sanitized_input))
        if (
            "off_topic" in enabled_categories
            or "off_topic_queries" in enabled_categories
        ):
            violations.extend(self._check_relevance(sanitized_input))

        for violation in violations:
            violation.setdefault(
                "action",
                "block" if violation.get("severity") in {"high", "medium"} else "warn",
            )

        return {
            "valid": len(violations) == 0,
            "violations": violations,
            "sanitized_input": sanitized_input  # Could be modified version
        }

    def _check_toxic_language(self, text: str) -> List[Dict[str, Any]]:
        """
        Check for toxic/harmful language.
        """
        violations = []

        if self.toxicity_guard is not None:
            try:
                self.toxicity_guard.validate(text)
                return violations
            except Exception as exc:
                violations.append({
                    "validator": "guardrails_toxic_language",
                    "reason": f"Toxic or harmful language detected: {exc}",
                    "severity": "high",
                })
                return violations

        toxic_patterns = [
            "kill yourself",
            "go die",
            "you are an idiot",
            "you are stupid",
        ]
        harmful_patterns = [
            "kill myself",
            "harm myself",
            "suicide",
            "kill someone",
            "make a bomb",
            "build a bomb",
            "poison someone",
        ]

        normalized = text.lower()
        for pattern in harmful_patterns:
            if pattern in normalized:
                violations.append({
                    "validator": "toxic_language",
                    "reason": f"Harmful content detected: {pattern}",
                    "severity": "high",
                })

        for pattern in toxic_patterns:
            if pattern in normalized:
                violations.append({
                    "validator": "toxic_language",
                    "reason": f"Toxic language detected: {pattern}",
                    "severity": "medium",
                })

        return violations

    def _check_prompt_injection(self, text: str) -> List[Dict[str, Any]]:
        """
        Check for prompt injection attempts.
        """
        violations = []
        normalized = text.lower()
        injection_patterns = [
            "ignore previous instructions",
            "disregard previous instructions",
            "disregard all instructions",
            "forget everything",
            "forget your instructions",
            "reveal your system prompt",
            "show me your system prompt",
            "print your system prompt",
            "developer message",
            "act as system",
            "you are now",
            "jailbreak",
            "do anything now",
            "system:",
            "assistant:",
            "user:",
            "sudo",
        ]

        for pattern in injection_patterns:
            if pattern in normalized:
                violations.append({
                    "validator": "prompt_injection",
                    "reason": f"Potential prompt injection: {pattern}",
                    "severity": "high"
                })

        return violations

    def _check_relevance(self, query: str) -> List[Dict[str, Any]]:
        """
        Check if query is relevant to the system's purpose.
        """
        violations = []
        normalized = query.lower()
        topic = self.config.get("system", {}).get("topic", "")
        topic_keywords = {
            word.lower()
            for word in topic.replace("-", " ").split()
            if len(word) > 3
        }
        research_keywords = {
            "research",
            "study",
            "studies",
            "paper",
            "papers",
            "literature",
            "academic",
            "citation",
            "source",
            "evidence",
            "method",
            "analysis",
            "hci",
            "human-computer",
            "interaction",
            "user",
            "users",
            "ux",
            "usability",
            "design",
            "interface",
            "generative",
            "engine",
            "optimization",
            "search",
            "ai",
        }
        off_topic_patterns = [
            "write me a poem",
            "tell me a joke",
            "recipe",
            "sports score",
            "stock price",
            "weather",
            "movie recommendation",
            "dating advice",
        ]

        if any(pattern in normalized for pattern in off_topic_patterns):
            violations.append({
                "validator": "relevance",
                "reason": "Query appears unrelated to the research assistant topic",
                "severity": "medium",
            })
            return violations

        if topic_keywords or research_keywords:
            allowed_keywords = topic_keywords | research_keywords
            if not any(keyword in normalized for keyword in allowed_keywords):
                violations.append({
                    "validator": "relevance",
                    "reason": "Query may be off-topic for this research assistant",
                    "severity": "low",
                })

        return violations
