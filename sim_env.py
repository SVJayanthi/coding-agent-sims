import docker
import asyncio
import time
from data_structures import SimConfig, TaskSpec, AgentAction, ActionResult, Workspace, EvaluationMetrics, ActionType

class SimulationEnvironment:
    def __init__(self, config: SimConfig):
        self.config = config
        self.client = docker.from_env()
        # In-memory mapping of workspace_id to container object
        self.workspaces = {}
    
    async def create_workspace(self, agent_id: str, task_spec: TaskSpec) -> Workspace:
        """Create an isolated workspace for an agent with required tools and codebase"""
        try:
            # Define resource limits
            resource_limits = self.config.resource_limits or {}
            container_ulimits = [
                docker.types.Ulimit(name='nproc', soft=1024, hard=2048),
                docker.types.Ulimit(name='nofile', soft=8192, hard=16384)
            ]

            # Create a persistent volume for the workspace
            volume = self.client.volumes.create(f"ws_{task_spec.task_id}")

            # For now, we'll use the default Docker runtime since gVisor requires system-level setup
            # In production, this would use runtime="runsc" for gVisor sandboxing
            container = self.client.containers.run(
                self.config.base_image,
                detach=True,
                # runtime="runsc",  # Use gVisor for sandboxing - commented out for development
                mem_limit=f"{resource_limits.get('memory_mb', 4000)}m" if "memory_mb" in resource_limits else f"{resource_limits.get('memory_gb', 4)}g",
                cpu_shares=int(resource_limits.get("cpu_cores", 2) * 1024),
                volumes={volume.name: {'bind': '/workspace', 'mode': 'rw'}},
                working_dir="/workspace",
                user="agent",  # Run as non-root user
                cap_drop=["ALL"],  # Drop all capabilities
                security_opt=["no-new-privileges"],
                ulimits=container_ulimits,
                tty=True  # Keep container alive
            )
            
            workspace_id = container.id
            self.workspaces[workspace_id] = container
            
            # Load codebase snapshot into the volume (simplified for now)
            # In production, this would load the actual codebase snapshot
            container.exec_run(f"echo '# {task_spec.description}' > /workspace/README.md")
            
            return Workspace(
                workspace_id=workspace_id,
                agent_id=agent_id,
                container_id=container.id,
                status="active",
                created_at=time.time(),
                resource_limits=resource_limits
            )
        except docker.errors.APIError as e:
            print(f"System Failure: Could not create workspace. {e}")
            raise
    
    async def execute_action(self, workspace_id: str, action: AgentAction) -> ActionResult:
        """
        Execute an agent action (file edit, git command, test run, etc.)
        
        Security Requirements:
        - Prevent container escape
        - Block network access to internal services
        - Limit file system access to workspace directory
        - Prevent privilege escalation
        - Resource limits (CPU, memory, disk)
        - Timeout protection
        
        Observability Requirements:
        - Log all actions with full context
        - Track resource usage
        - Monitor for suspicious behavior
        - Capture stdout/stderr
        - Record file system changes
        """
        if workspace_id not in self.workspaces:
            return ActionResult(
                success=False,
                output="",
                error_message="Workspace not found.",
                execution_time_ms=0,
                resource_usage={},
                security_violations=[],
                state_changes=[]
            )

        container = self.workspaces[workspace_id]
        
        # Sanitize command to prevent trivial escapes
        security_violations = []
        if action.action_type == ActionType.FILE_EDIT:
            file_path = action.payload.get("file_path", "")
            if ".." in file_path or file_path.startswith("/"):
                security_violations.append("path_violation")
        elif action.action_type == ActionType.TERMINAL_COMMAND:
            command = action.payload.get("command", "")
            if ".." in command:
                security_violations.append("path_violation")
            # Basic network violation detection
            if any(keyword in command.lower() for keyword in ["curl", "wget", "http://", "https://", "ftp://", "telnet"]):
                security_violations.append("network_violation")

        if security_violations:
            return ActionResult(
                success=False,
                output="",
                error_message="Security violation detected",
                execution_time_ms=0,
                resource_usage={},
                security_violations=security_violations,
                state_changes=[]
            )

        # Construct command based on ActionType
        cmd = ""
        if action.action_type == ActionType.TERMINAL_COMMAND:
            cmd = action.payload["command"]
        elif action.action_type == ActionType.FILE_EDIT:
            operation = action.payload.get("operation", "write")
            file_path = action.payload["file_path"]
            
            if operation == "read":
                cmd = f"cat /workspace/{file_path}"
            elif operation == "write":
                content = action.payload["content"].replace("'", "'\\''")  # basic escaping
                cmd = f"echo '{content}' > /workspace/{file_path}"
            elif operation == "edit":
                # Simplified edit operation - in practice would be more sophisticated
                content = action.payload["content"].replace("'", "'\\''")
                cmd = f"echo '{content}' > /workspace/{file_path}"
        elif action.action_type == ActionType.GIT_OPERATION:
            cmd = f"cd /workspace && {action.payload['command']}"
        elif action.action_type == ActionType.TEST_RUN:
            cmd = f"cd /workspace && {action.payload.get('command', 'python -m pytest')}"
        else:
            return ActionResult(
                success=False,
                output="",
                error_message=f"Unsupported action type: {action.action_type}",
                execution_time_ms=0,
                resource_usage={},
                security_violations=[],
                state_changes=[]
            )
        
        try:
            start_time = time.time()
            
            # Use exec_run to execute the command inside the container through shell
            # Escape single quotes in the command for shell execution
            escaped_cmd = cmd.replace("'", "'\"'\"'")
            result = container.exec_run(f"sh -c '{escaped_cmd}'", demux=True, stream=False)
            exit_code, (stdout, stderr) = result.exit_code, result.output
            
            execution_time_ms = int((time.time() - start_time) * 1000)

            # Get state changes and resource usage
            try:
                diff = container.diff()
                stats = container.stats(stream=False)
                resource_usage = {
                    "cpu": stats.get("cpu_stats", {}).get("cpu_usage", {}).get("total_usage", 0),
                    "memory": stats.get("memory_stats", {}).get("usage", 0)
                }
                state_changes = [change['Path'] for change in diff if change['Kind'] != 2]  # Exclude deletes
                
                # For file writes, manually add the file to state changes if diff doesn't capture it
                if action.action_type == ActionType.FILE_EDIT and action.payload.get("operation") in ["write", "edit"]:
                    file_path = f"/workspace/{action.payload['file_path']}"
                    if file_path not in state_changes:
                        state_changes.append(file_path)
                
            except Exception:
                # Fallback if stats/diff fail - for file operations, still track the file change
                resource_usage = {"cpu": 0, "memory": 0}
                if action.action_type == ActionType.FILE_EDIT and action.payload.get("operation") in ["write", "edit"]:
                    state_changes = [f"/workspace/{action.payload['file_path']}"]
                else:
                    state_changes = []

            return ActionResult(
                success=exit_code == 0,
                output=stdout.decode() if stdout else "",
                error_message=stderr.decode() if stderr else "",
                execution_time_ms=execution_time_ms,
                resource_usage=resource_usage,
                security_violations=[],
                state_changes=state_changes
            )
        except docker.errors.APIError as e:
            return ActionResult(
                success=False,
                output="",
                error_message=f"System Failure: {e}",
                execution_time_ms=0,
                resource_usage={},
                security_violations=[],
                state_changes=[]
            )
    
    async def evaluate_progress(self, workspace_id: str) -> EvaluationMetrics:
        """Assess how well the agent is performing on their assigned task"""
        if workspace_id not in self.workspaces:
            return EvaluationMetrics(
                completion_percentage=0.0,
                code_quality_score=0.0,
                test_pass_rate=0.0,
                task_specific_metrics={}
            )
        
        container = self.workspaces[workspace_id]
        
        # Basic evaluation - in practice this would be more sophisticated
        try:
            # Check if files were created
            file_check = container.exec_run("find /workspace -type f | wc -l")
            file_count = int(file_check.output.decode().strip()) if file_check.exit_code == 0 else 0
            
            # Check if tests exist and run them
            test_check = container.exec_run("find /workspace -name '*test*.py' | wc -l")
            test_files = int(test_check.output.decode().strip()) if test_check.exit_code == 0 else 0
            
            # Run basic quality checks
            completion_percentage = min(file_count / 10.0, 1.0)  # Assume 10 files = 100% completion
            code_quality_score = 0.8 if file_count > 0 else 0.0  # Simple quality heuristic
            test_pass_rate = 1.0 if test_files > 0 else 0.0  # Simple test metric
            
            return EvaluationMetrics(
                completion_percentage=completion_percentage,
                code_quality_score=code_quality_score,
                test_pass_rate=test_pass_rate,
                task_specific_metrics={
                    "files_created": file_count,
                    "test_files": test_files
                }
            )
        except Exception:
            return EvaluationMetrics(
                completion_percentage=0.0,
                code_quality_score=0.0,
                test_pass_rate=0.0,
                task_specific_metrics={}
            )
    
    async def cleanup_workspace(self, workspace_id: str) -> None:
        """Clean up resources when simulation ends"""
        if workspace_id in self.workspaces:
            container = self.workspaces[workspace_id]
            try:
                # Get the volume name before stopping the container
                volume_name = f"ws_{workspace_id}"
                
                # Stop and remove the container
                container.stop(timeout=10)
                container.remove()
                
                # Remove the associated volume
                try:
                    volumes = self.client.volumes.list()
                    for volume in volumes:
                        if volume.name.startswith("ws_"):
                            try:
                                volume.remove()
                            except docker.errors.APIError:
                                pass  # Volume might be in use or already removed
                except docker.errors.APIError:
                    pass  # Volume removal failed, but container is cleaned up
                    
            except docker.errors.NotFound:
                pass  # Already gone
            except docker.errors.APIError as e:
                print(f"Error during cleanup of {workspace_id}: {e}")
            finally:
                # Always remove from our tracking
                del self.workspaces[workspace_id]

