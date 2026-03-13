"""Controlled Tentacle Growth - Managed skill lifecycle.

P7 Refactor: SkillBootstrapper integrated with:
- SensorRegistry (for skill registration)
- SwarmPolicy (for approval and constraints)
- ExecutionPolicy (for safe testing)
- Approval workflow (before skills enter production)
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum

from backend.core.agent_contracts import (
    SwarmPolicy, ExecutionPolicy, SensorSpec
)
from backend.core.spec_loader import get_spec_loader
from backend.skills.skill_library import SkillLibrary, Skill
from backend.skills.skill_library import SkillBootstrapper
from backend.validators.ast_validator import ASTValidator

logger = logging.getLogger(__name__)


class SkillApprovalStatus(str, Enum):
    """Lifecycle states for a skill."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEPRECATED = "deprecated"


class SkillRequest:
    """Request to create a new skill (tentacle growth request)."""
    
    def __init__(
        self,
        task_description: str,
        input_signature: Dict[str, Any],
        output_signature: Dict[str, Any],
        test_cases: Optional[List[Dict[str, Any]]] = None,
        requested_by: str = "coordinator",
        priority: int = 1
    ):
        self.task_description = task_description
        self.input_signature = input_signature
        self.output_signature = output_signature
        self.test_cases = test_cases or []
        self.requested_by = requested_by
        self.priority = priority
        self.requested_at = datetime.now().isoformat()
        self.request_id = f"skill_req_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


class ControlledSkillBootstrapper:
    """Policy-controlled skill bootstrapper.
    
    P7 Refactor: Integrates SkillBootstrapper with the contract/policy layer.
    All new skills go through validation, testing, and approval before
    being added to the production registry.
    """
    
    def __init__(
        self,
        skill_library: SkillLibrary,
        swarm_policy: Optional[SwarmPolicy] = None,
        execution_policy: Optional[ExecutionPolicy] = None,
        llm_client: Optional[Any] = None
    ):
        """Initialize the controlled bootstrapper.
        
        Args:
            skill_library: Library for storing approved skills.
            swarm_policy: Policy for approval and constraints.
            execution_policy: Policy for safe execution during testing.
            llm_client: LLM for code generation.
        """
        self.library = skill_library
        self.swarm_policy = swarm_policy
        self.execution_policy = execution_policy
        self.llm_client = llm_client
        
        # Internal bootstrapper for actual generation
        self._bootstrapper = SkillBootstrapper(skill_library, llm_client)
        
        # Pending approvals storage
        self._pending_approvals: Dict[str, Skill] = {}
        
        # AST validator for security
        self._validator = ASTValidator()
        
        logger.info("[ControlledSkillBootstrapper] Initialized")
    
    def request_skill(
        self,
        skill_request: SkillRequest
    ) -> Dict[str, Any]:
        """Request creation of a new skill (controlled growth).
        
        P7: Coordinator calls this to "grow a tentacle".
        
        Args:
            skill_request: Request details.
        
        Returns:
            Status dict with request_id and next steps.
        """
        logger.info(f"[ControlledSkillBootstrapper] Skill request: {skill_request.request_id}")
        
        # Check policy constraints
        policy_check = self._check_policy_constraints(skill_request)
        if not policy_check["allowed"]:
            logger.warning(f"[ControlledSkillBootstrapper] Request rejected by policy: {policy_check['reason']}")
            return {
                "success": False,
                "request_id": skill_request.request_id,
                "error": policy_check["reason"],
                "status": "rejected"
            }
        
        # Generate skill code
        skill = self._bootstrapper.bootstrap_skill(
            task_description=skill_request.task_description,
            input_signature=skill_request.input_signature,
            output_signature=skill_request.output_signature,
            test_cases=skill_request.test_cases
        )
        
        if not skill:
            return {
                "success": False,
                "request_id": skill_request.request_id,
                "error": "Skill generation failed",
                "status": "failed"
            }
        
        # Validate before approval
        validation_errors = self._validator.validate(skill.code)
        if validation_errors:
            logger.error(f"[ControlledSkillBootstrapper] Validation failed: {validation_errors}")
            return {
                "success": False,
                "request_id": skill_request.request_id,
                "error": f"Validation failed: {validation_errors}",
                "status": "rejected"
            }
        
        # Store for approval
        self._pending_approvals[skill_request.request_id] = skill
        
        # Auto-approve if policy allows
        if self._should_auto_approve(skill_request):
            return self._auto_approve(skill_request.request_id)
        
        # Return pending status
        return {
            "success": True,
            "request_id": skill_request.request_id,
            "skill_name": skill.name,
            "status": "pending_approval",
            "message": "Skill generated and awaiting approval"
        }
    
    def _check_policy_constraints(self, request: SkillRequest) -> Dict[str, Any]:
        """Check if request complies with swarm policy.
        
        Args:
            request: Skill request to check.
        
        Returns:
            Dict with 'allowed' bool and 'reason' if not allowed.
        """
        if not self.swarm_policy:
            return {"allowed": True}
        
        # Check max skills limit
        max_skills = 50  # Default limit
        if len(self.library.list_skills()) >= max_skills:
            return {
                "allowed": False,
                "reason": f"Skill library at capacity ({max_skills} skills)"
            }
        
        # Check description safety (basic)
        forbidden_keywords = ['exec', 'eval', 'compile', '__import__']
        desc_lower = request.task_description.lower()
        for keyword in forbidden_keywords:
            if keyword in desc_lower:
                return {
                    "allowed": False,
                    "reason": f"Request contains forbidden keyword: {keyword}"
                }
        
        return {"allowed": True}
    
    def _should_auto_approve(self, request: SkillRequest) -> bool:
        """Determine if skill should be auto-approved.
        
        Args:
            request: Skill request.
        
        Returns:
            True if auto-approval is allowed.
        """
        if not self.swarm_policy:
            return False
        
        # Auto-approve only low-priority, safe requests
        if request.priority > 2:
            return False
        
        # Check if auto-approval is enabled in policy
        # (This could be a new field in SwarmPolicy)
        return False  # Conservative default
    
    def _auto_approve(self, request_id: str) -> Dict[str, Any]:
        """Auto-approve a skill request.
        
        Args:
            request_id: ID of request to approve.
        
        Returns:
            Approval result dict.
        """
        skill = self._pending_approvals.get(request_id)
        if not skill:
            return {
                "success": False,
                "request_id": request_id,
                "error": "Request not found"
            }
        
        # Save to library
        self.library.save_skill(skill)
        
        # Remove from pending
        del self._pending_approvals[request_id]
        
        logger.info(f"[ControlledSkillBootstrapper] Auto-approved: {skill.name}")
        
        return {
            "success": True,
            "request_id": request_id,
            "skill_name": skill.name,
            "status": "approved",
            "message": "Skill approved and added to library"
        }
    
    def approve_skill(
        self,
        request_id: str,
        approved_by: str = "admin"
    ) -> Dict[str, Any]:
        """Manually approve a pending skill.
        
        Args:
            request_id: ID of request to approve.
            approved_by: Who approved the skill.
        
        Returns:
            Approval result.
        """
        skill = self._pending_approvals.get(request_id)
        if not skill:
            return {
                "success": False,
                "request_id": request_id,
                "error": "Request not found or already processed"
            }
        
        # Save to library
        self.library.save_skill(skill)
        
        # Remove from pending
        del self._pending_approvals[request_id]
        
        logger.info(f"[ControlledSkillBootstrapper] Manually approved by {approved_by}: {skill.name}")
        
        return {
            "success": True,
            "request_id": request_id,
            "skill_name": skill.name,
            "approved_by": approved_by,
            "status": "approved"
        }
    
    def reject_skill(
        self,
        request_id: str,
        reason: str = "",
        rejected_by: str = "admin"
    ) -> Dict[str, Any]:
        """Reject a pending skill.
        
        Args:
            request_id: ID of request to reject.
            reason: Rejection reason.
            rejected_by: Who rejected the skill.
        
        Returns:
            Rejection result.
        """
        skill = self._pending_approvals.get(request_id)
        if not skill:
            return {
                "success": False,
                "request_id": request_id,
                "error": "Request not found"
            }
        
        # Remove from pending
        del self._pending_approvals[request_id]
        
        logger.info(f"[ControlledSkillBootstrapper] Rejected by {rejected_by}: {skill.name} - {reason}")
        
        return {
            "success": True,
            "request_id": request_id,
            "skill_name": skill.name,
            "rejected_by": rejected_by,
            "reason": reason,
            "status": "rejected"
        }
    
    def get_pending_requests(self) -> List[Dict[str, Any]]:
        """Get all pending skill requests.
        
        Returns:
            List of pending request summaries.
        """
        return [
            {
                "request_id": req_id,
                "skill_name": skill.name,
                "description": skill.description,
                "created_at": skill.created_at
            }
            for req_id, skill in self._pending_approvals.items()
        ]
    
    def get_skill_status(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a skill request.
        
        Args:
            request_id: Request ID to check.
        
        Returns:
            Status dict or None if not found.
        """
        if request_id in self._pending_approvals:
            skill = self._pending_approvals[request_id]
            return {
                "request_id": request_id,
                "skill_name": skill.name,
                "status": "pending_approval"
            }
        
        # Check if already in library
        for skill_name in self.library.list_skills():
            skill = self.library.get_skill(skill_name)
            if skill and skill.created_at and request_id in skill.created_at:
                return {
                    "request_id": request_id,
                    "skill_name": skill_name,
                    "status": "approved"
                }
        
        return None


def create_controlled_bootstrapper(
    skill_library: Optional[SkillLibrary] = None,
    llm_client: Optional[Any] = None
) -> ControlledSkillBootstrapper:
    """Factory for creating ControlledSkillBootstrapper.
    
    Loads policies from configuration.
    
    Args:
        skill_library: Optional skill library instance.
        llm_client: Optional LLM client.
    
    Returns:
        Configured ControlledSkillBootstrapper.
    """
    if skill_library is None:
        skill_library = SkillLibrary()
    
    # Load policies
    try:
        loader = get_spec_loader()
        swarm_policy = loader.load_swarm_policy()
    except Exception as e:
        logger.warning(f"[create_controlled_bootstrapper] Could not load swarm policy: {e}")
        swarm_policy = None
    
    execution_policy = None  # Could be loaded from separate config
    
    return ControlledSkillBootstrapper(
        skill_library=skill_library,
        swarm_policy=swarm_policy,
        execution_policy=execution_policy,
        llm_client=llm_client
    )
