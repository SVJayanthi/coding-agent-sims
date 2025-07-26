from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from enum import Enum
import asyncio

class ActionType(Enum):
    FILE_EDIT = "file_edit"
    TERMINAL_COMMAND = "terminal_command"
    GIT_OPERATION = "git_operation"
    TEST_RUN = "test_run"
    IDE_ACTION = "ide_action"

@dataclass
class SimConfig:
    max_workspaces: int = 1000
    resource_limits: Dict[str, Any] = None
    security_policy: Dict[str, Any] = None
    base_image: str = "mechanize/dev-env:latest"

@dataclass
class TaskSpec:
    task_id: str
    description: str
    codebase_snapshot: str
    evaluation_criteria: List[str]
    time_limit_hours: int = 24

@dataclass
class AgentAction:
    action_type: ActionType
    payload: Dict[str, Any]
    timestamp: float
    
    # Example payloads:
    # FILE_EDIT: {"file_path": "src/main.py", "content": "...", "line_range": [10, 20]}
    # TERMINAL_COMMAND: {"command": "npm test", "working_dir": "/workspace"}
    # GIT_OPERATION: {"command": "git commit -m 'fix bug'"}

@dataclass
class ActionResult:
    success: bool
    output: str
    error_message: Optional[str]
    execution_time_ms: int
    resource_usage: Dict[str, float]  # CPU, memory, disk I/O
    security_violations: List[str]
    state_changes: List[str]  # Files modified, processes started, etc.

@dataclass
class Workspace:
    workspace_id: str
    agent_id: str
    container_id: str
    status: str  # "active", "suspended", "terminated"
    created_at: float
    resource_limits: Dict[str, Any]

@dataclass
class EvaluationMetrics:
    completion_percentage: float
    code_quality_score: float
    test_pass_rate: float
    task_specific_metrics: Dict[str, float]