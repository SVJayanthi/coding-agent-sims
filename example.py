from sim_env import SimulationEnvironment
from data_structures import SimConfig, TaskSpec, AgentAction, ActionType

async def example_usage():
    # Initialize simulation environment
    config = SimConfig(
        max_workspaces=100,
        resource_limits={"cpu_cores": 2, "memory_gb": 4, "disk_gb": 10},
        security_policy={"allow_network": True, "block_internal_ips": True}
    )
    sim_env = SimulationEnvironment(config)
    
    # Create workspace for agent
    task_spec = TaskSpec(
        task_id="fix_authentication_bug",
        description="Fix the login system that's failing for users with special characters in passwords",
        codebase_snapshot="snapshot_123",
        evaluation_criteria=["tests pass", "security best practices", "no breaking changes"]
    )
    
    workspace = await sim_env.create_workspace("agent_001", task_spec)
    print(f"Created workspace: {workspace.workspace_id}")
    
    # Agent performs actions
    actions = [
        # Agent examines the code
        AgentAction(
            action_type=ActionType.FILE_EDIT,
            payload={"file_path": "src/auth.py", "operation": "read"},
            timestamp=1642784400.0
        ),
        # Agent runs tests to understand the issue
        AgentAction(
            action_type=ActionType.TERMINAL_COMMAND,
            payload={"command": "python -m pytest tests/test_auth.py -v", "working_dir": "/workspace"},
            timestamp=1642784401.0
        ),
        # Agent makes a fix
        AgentAction(
            action_type=ActionType.FILE_EDIT,
            payload={
                "file_path": "src/auth.py",
                "operation": "edit",
                "line_range": [45, 50],
                "content": "# Fixed: properly escape special characters\npassword = html.escape(password)\nif validate_password(password):"
            },
            timestamp=1642784402.0
        ),
        # Agent commits the fix
        AgentAction(
            action_type=ActionType.GIT_OPERATION,
            payload={"command": "git add . && git commit -m 'Fix password validation for special characters'"},
            timestamp=1642784403.0
        )
    ]
    
    # Execute actions and collect results
    for action in actions:
        result = await sim_env.execute_action(workspace.workspace_id, action)
        print(f"Action {action.action_type}: {'SUCCESS' if result.success else 'FAILED'}")
        if not result.success:
            print(f"Error: {result.error_message}")
        if result.security_violations:
            print(f"Security violations: {result.security_violations}")
    
    # Evaluate progress
    metrics = await sim_env.evaluate_progress(workspace.workspace_id)
    print(f"Task completion: {metrics.completion_percentage:.1%}")
    print(f"Code quality: {metrics.code_quality_score:.2f}")
    
    # Cleanup
    await sim_env.cleanup_workspace(workspace.workspace_id)