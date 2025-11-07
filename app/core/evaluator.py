"""
Query Evaluator Module

Manages the self-evaluation and regeneration workflow.
Determines when SQL needs to be regenerated and orchestrates retries.

MCP-Ready Interface:
- Compatible with MCP feedback loop pattern
- Tracks evaluation history
- Supports iterative improvement
"""

from typing import Any, Dict, List, Optional

import structlog

from app.core.config import get_settings
from app.core.llm_pipeline import LLMPipeline

logger = structlog.get_logger(__name__)
settings = get_settings()


class EvaluationResult:
    """
    Represents the result of a query evaluation.

    Attributes:
        is_correct: Whether query correctly answers request
        confidence: Confidence score (0-1)
        reasoning: Explanation of evaluation
        needs_regeneration: Whether SQL should be regenerated
        issues: List of identified issues
    """

    def __init__(
        self,
        is_correct: bool,
        confidence: float,
        reasoning: str,
        needs_regeneration: bool,
        issues: Optional[List[str]] = None,
    ) -> None:
        self.is_correct = is_correct
        self.confidence = confidence
        self.reasoning = reasoning
        self.needs_regeneration = needs_regeneration
        self.issues = issues or []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "is_correct": self.is_correct,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "needs_regeneration": self.needs_regeneration,
            "issues": self.issues,
        }


class QueryEvaluator:
    """
    Evaluates query results and manages regeneration workflow.

    Responsibilities:
    - Evaluate if results answer user request
    - Detect when regeneration is needed
    - Track evaluation history
    - Manage retry attempts
    - Store evaluation feedback
    """

    def __init__(self, llm_pipeline: LLMPipeline) -> None:
        """
        Initialize QueryEvaluator with LLM pipeline.

        Args:
            llm_pipeline: LLM pipeline for evaluation
        """
        self.llm_pipeline = llm_pipeline
        self.max_retries = settings.max_retry_attempts
        self._evaluation_history: List[Dict[str, Any]] = []

    async def evaluate_and_regenerate(
        self,
        user_request: str,
        schema_summary: Dict[str, Any],
        initial_sql: str,
        initial_results: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate query results and regenerate if necessary.

        This is the main orchestration method for the evaluation loop.

        Args:
            user_request: Original user request
            schema_summary: Database schema
            initial_sql: Initially generated SQL
            initial_results: Query execution results
            context: Optional additional context

        Returns:
            Dict containing:
                - sql: Final SQL query (original or regenerated)
                - results: Final query results
                - evaluation: Final evaluation result
                - attempts: Number of attempts made
                - history: List of all attempts

        Workflow:
        1. Evaluate initial results
        2. If incorrect and retries remain, regenerate SQL
        3. Execute new SQL and re-evaluate
        4. Repeat until correct or max retries reached

        MCP-Compatible: Supports iterative feedback loop
        """
        logger.info(
            "Starting evaluation and regeneration workflow",
            request=user_request[:100],
            max_retries=self.max_retries,
        )

        current_sql = initial_sql
        current_results = initial_results
        attempts = 1

        self._evaluation_history = []

        while attempts <= self.max_retries + 1:
            # Evaluate current results
            evaluation = await self.evaluate(
                user_request=user_request,
                sql=current_sql,
                results=current_results,
            )

            # Record attempt
            self._record_attempt(
                attempt=attempts,
                sql=current_sql,
                evaluation=evaluation,
            )

            # If correct or max retries reached, return
            if evaluation.is_correct or attempts > self.max_retries:
                logger.info(
                    "Evaluation complete",
                    is_correct=evaluation.is_correct,
                    attempts=attempts,
                )
                return {
                    "sql": current_sql,
                    "results": current_results,
                    "evaluation": evaluation.to_dict(),
                    "attempts": attempts,
                    "history": self._evaluation_history,
                }

            # Regenerate SQL
            logger.info(
                "Regenerating SQL",
                attempt=attempts + 1,
                reason=evaluation.reasoning,
            )

            # TODO: Implement regeneration logic
            # - Call LLM pipeline with feedback
            # - Execute new SQL
            # - Continue loop

            raise NotImplementedError("Regeneration logic not yet implemented")

    async def evaluate(
        self,
        user_request: str,
        sql: str,
        results: Dict[str, Any],
    ) -> EvaluationResult:
        """
        Evaluate if query results answer the user request.

        Args:
            user_request: Original user request
            sql: Executed SQL query
            results: Query results

        Returns:
            EvaluationResult: Structured evaluation result

        Uses LLM to determine:
        - Whether results correctly answer request
        - Confidence in the evaluation
        - Specific issues if any
        - Whether regeneration is needed
        """
        logger.info("Evaluating query results")

        # Call LLM pipeline evaluation chain
        evaluation_output = await self.llm_pipeline.evaluate_results(
            user_request=user_request,
            sql=sql,
            results=results,
        )

        # Parse LLM output into EvaluationResult
        return self._parse_evaluation_output(evaluation_output)

    async def should_regenerate(
        self,
        evaluation: EvaluationResult,
        attempt: int,
    ) -> bool:
        """
        Determine if SQL should be regenerated.

        Args:
            evaluation: Current evaluation result
            attempt: Current attempt number

        Returns:
            True if should regenerate, False otherwise

        Decision factors:
        - Is evaluation incorrect?
        - Are retries remaining?
        - Is confidence score too low?
        """
        if attempt > self.max_retries:
            logger.info("Max retries reached, not regenerating")
            return False

        if evaluation.is_correct:
            logger.info("Query is correct, no regeneration needed")
            return False

        if evaluation.needs_regeneration:
            logger.info("Regeneration recommended by evaluator")
            return True

        # Low confidence threshold
        if evaluation.confidence < 0.5:
            logger.info("Low confidence, regenerating", confidence=evaluation.confidence)
            return True

        return False

    def get_evaluation_history(self) -> List[Dict[str, Any]]:
        """
        Get history of all evaluation attempts.

        Returns:
            List of evaluation attempt records

        Useful for:
        - Debugging
        - Analysis of LLM performance
        - MCP feedback repository
        """
        return self._evaluation_history.copy()

    def _record_attempt(
        self,
        attempt: int,
        sql: str,
        evaluation: EvaluationResult,
    ) -> None:
        """
        Record an evaluation attempt in history.

        Args:
            attempt: Attempt number
            sql: SQL query evaluated
            evaluation: Evaluation result
        """
        record = {
            "attempt": attempt,
            "sql": sql,
            "evaluation": evaluation.to_dict(),
        }
        self._evaluation_history.append(record)
        logger.debug("Recorded evaluation attempt", attempt=attempt)

    def _parse_evaluation_output(
        self,
        output: Dict[str, Any],
    ) -> EvaluationResult:
        """
        Parse LLM evaluation output into EvaluationResult.

        Args:
            output: Raw LLM output

        Returns:
            EvaluationResult: Parsed evaluation result
        """
        # TODO: Implement robust parsing with validation
        # Handle different LLM output formats
        # Validate all required fields

        raise NotImplementedError("_parse_evaluation_output not yet implemented")


async def create_evaluator(llm_pipeline: LLMPipeline) -> QueryEvaluator:
    """
    Create QueryEvaluator instance.

    Args:
        llm_pipeline: Initialized LLM pipeline

    Returns:
        QueryEvaluator: Configured evaluator instance

    Usage:
        pipeline = await create_llm_pipeline()
        evaluator = await create_evaluator(pipeline)
    """
    return QueryEvaluator(llm_pipeline)
