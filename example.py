import ray
from sim_env import SimulationEnvironment
from data_structures import SimConfig, TaskSpec, AgentAction, ActionType

async def example_usage():
    # Initialize Ray
    if not ray.is_initialized():
        ray.init()
    
    # Initialize simulation environment as Ray actor
    config = SimConfig(
        max_workspaces=100,
        resource_limits={"cpu_cores": 2, "memory_gb": 4, "disk_gb": 10},
        security_policy={"allow_network": True, "block_internal_ips": True}
    )
    sim_env = SimulationEnvironment.remote(config)
    
    # Create workspace for agent
    task_spec = TaskSpec(
        task_id="fix_authentication_bug",
        description="Fix the login system that's failing for users with special characters in passwords",
        codebase_snapshot="snapshot_123",
        evaluation_criteria=["tests pass", "security best practices", "no breaking changes"]
    )
    
    workspace = await sim_env.create_workspace.remote("agent_001", task_spec)
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
            payload={"command": "python3 -m pytest tests/test_auth.py -v", "working_dir": "/workspace"},
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
        result = await sim_env.execute_action.remote(workspace.workspace_id, action)
        print(f"Action {action.action_type}: {'SUCCESS' if result.success else 'FAILED'}")
        if not result.success:
            print(f"Error: {result.error_message}")
        if result.security_violations:
            print(f"Security violations: {result.security_violations}")
    
    # Evaluate progress
    metrics = await sim_env.evaluate_progress.remote(workspace.workspace_id)
    print(f"Task completion: {metrics.completion_percentage:.1%}")
    print(f"Code quality: {metrics.code_quality_score:.2f}")
    
    # Cleanup
    await sim_env.cleanup_workspace.remote(workspace.workspace_id)
    
    # Demonstrate concurrent usage with multiple actors
    print("\n--- Demonstrating concurrent simulations ---")
    
    # Create multiple simulation environments
    sim_envs = [SimulationEnvironment.remote(config) for _ in range(3)]
    
    # Create concurrent tasks
    async def run_concurrent_simulation(sim_env, agent_id):
        task = TaskSpec(
            task_id=f"concurrent_task_{agent_id}",
            description=f"Concurrent task for agent {agent_id}",
            codebase_snapshot="concurrent_snapshot",
            evaluation_criteria=["basic functionality"]
        )
        
        workspace = await sim_env.create_workspace.remote(agent_id, task)
        
        # Simple file operation
        action = AgentAction(
            action_type=ActionType.FILE_EDIT,
            payload={
                "file_path": f"agent_{agent_id}_output.txt",
                "operation": "write",
                "content": f"Output from agent {agent_id}"
            },
            timestamp=1642784400.0
        )
        
        result = await sim_env.execute_action.remote(workspace.workspace_id, action)
        print(f"Agent {agent_id}: {'SUCCESS' if result.success else 'FAILED'}")
        
        await sim_env.cleanup_workspace.remote(workspace.workspace_id)
        return result.success
    
    # Run concurrent simulations
    import asyncio
    tasks = [run_concurrent_simulation(sim_env, f"agent_{i}") for i, sim_env in enumerate(sim_envs)]
    results = await asyncio.gather(*tasks)
    
    print(f"Concurrent simulation results: {results}")
    
    # Shutdown Ray
    ray.shutdown()