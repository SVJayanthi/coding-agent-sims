# Mechanize Simulation Environment

A secure, scalable execution system for AI agents in software engineering simulations. Built with Docker for containerization, Ray for massive concurrency, and comprehensive security controls for safe agent code execution.

## 🚀 Quick Start

### Prerequisites

- **Docker**: Version 20.10 or higher
- **Python**: 3.8+ with pip
- **Git**: For cloning and version control
- **System**: macOS, Linux, or Windows with WSL2

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd mechanize
   ```

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Build the base Docker image**
   ```bash
   docker build -t mechanize/dev-env:latest .
   ```

4. **Verify installation**
   ```bash
   python -m pytest tests.py -v
   ```

### Basic Usage

```python
import asyncio
import ray
from sim_env import SimulationEnvironment
from data_structures import SimConfig, TaskSpec, AgentAction, ActionType

async def simple_example():
    # Initialize Ray for concurrency
    ray.init()
    
    # Create simulation environment
    config = SimConfig(
        resource_limits={"memory_gb": 2, "cpu_cores": 1}
    )
    sim_env = SimulationEnvironment.remote(config)
    
    # Create workspace for agent
    task_spec = TaskSpec(
        task_id="hello_world",
        description="Simple hello world task",
        codebase_snapshot="example_snapshot",
        evaluation_criteria=["basic functionality"]
    )
    
    workspace = await sim_env.create_workspace.remote("agent_001", task_spec)
    
    # Execute actions
    action = AgentAction(
        action_type=ActionType.FILE_EDIT,
        payload={
            "file_path": "hello.py",
            "operation": "write", 
            "content": "print('Hello, Mechanize!')"
        },
        timestamp=1642784400.0
    )
    
    result = await sim_env.execute_action.remote(workspace.workspace_id, action)
    print(f"Action successful: {result.success}")
    
    # Cleanup
    await sim_env.cleanup_workspace.remote(workspace.workspace_id)
    ray.shutdown()

# Run the example
asyncio.run(simple_example())
```

## 📊 Performance Benchmarking

### Run 100 Concurrent Simulations

```bash
# Basic concurrent profiling
python profile_concurrent.py

# Custom configuration
python profile_concurrent.py --num-concurrent 50 --actions-per-sim 3

# Detailed memory profiling (slower but more comprehensive)
python profile_concurrent.py --profile-memory --save-results my_benchmark.json
```

### Optimization Benchmarking

```bash
# Compare regular vs optimized performance
python optimize_simulation.py
```

**Expected Performance:**
- **Throughput**: 5-15 simulations/second (depending on hardware)
- **Workspace Creation**: 8-12 seconds per workspace
- **Action Execution**: 50-200ms per action
- **Memory Usage**: ~500MB base + 100-200MB per concurrent simulation
- **Success Rate**: >95% under normal conditions

## 🏗️ Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Ray Distributed System                   │
├─────────────────────────────────────────────────────────────┤
│  SimulationEnvironment (Ray Actor)                         │
│  ├── create_workspace()     # Docker container creation     │
│  ├── execute_action()       # Secure command execution     │
│  ├── evaluate_progress()    # Task assessment              │
│  └── cleanup_workspace()    # Resource cleanup             │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Docker Containers                        │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐│
│  │   Workspace 1   │ │   Workspace 2   │ │   Workspace N   ││
│  │ ┌─────────────┐ │ │ ┌─────────────┐ │ │ ┌─────────────┐ ││
│  │ │/workspace/  │ │ │ │/workspace/  │ │ │ │/workspace/  │ ││
│  │ │- agent code │ │ │ │- agent code │ │ │ │- agent code │ ││
│  │ │- temp files │ │ │ │- temp files │ │ │ │- temp files │ ││
│  │ └─────────────┘ │ │ └─────────────┘ │ │ └─────────────┘ ││
│  │   Security:     │ │                 │ │                 ││
│  │   - Non-root    │ │   Isolated      │ │   Resource      ││
│  │   - No network  │ │   Filesystem    │ │   Limited       ││
│  │   - Sandboxed   │ │                 │ │                 ││
│  └─────────────────┘ └─────────────────┘ └─────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### Security Model

- **Container Isolation**: Each agent runs in isolated Docker containers
- **Resource Limits**: CPU and memory restrictions prevent abuse
- **Network Controls**: Blocked external access with optional proxy whitelist
- **Filesystem Sandbox**: Restricted to `/workspace` directory
- **Privilege Dropping**: No root access, minimal capabilities
- **Path Validation**: Prevents directory traversal attacks

## 🔧 Configuration

### SimConfig Options

```python
config = SimConfig(
    max_workspaces=1000,           # Maximum concurrent workspaces
    resource_limits={
        "cpu_cores": 2,            # CPU cores per workspace
        "memory_gb": 4,            # Memory limit per workspace
        "memory_mb": 4000,         # Alternative memory specification
    },
    security_policy={
        "allow_network": False,     # Block network access
        "block_internal_ips": True, # Block internal network
    },
    base_image="mechanize/dev-env:latest"  # Docker base image
)
```

### Environment Variables

```bash
# Ray configuration
export RAY_DISABLE_IMPORT_WARNING=1
export RAY_memory_monitor_refresh_ms=1000

# Docker configuration  
export DOCKER_HOST=unix:///var/run/docker.sock

# Performance tuning
export PYTHONUNBUFFERED=1
```

## 🧪 Testing

### Run Test Suite

```bash
# All tests
python -m pytest tests.py -v

# Specific test
python -m pytest tests.py::TestSimulationEnvironment::test_basic_file_operations -v

# With coverage
pip install pytest-cov
python -m pytest tests.py --cov=sim_env --cov-report=html
```

### Test Categories

- **`test_basic_file_operations`**: File read/write functionality
- **`test_security_violations`**: Security control validation
- **`test_resource_limits`**: Memory and CPU limit enforcement
- **`test_concurrent_workspaces`**: Multi-workspace isolation

## 📈 Monitoring & Observability

### Built-in Metrics

Every action execution provides:

```python
result = await sim_env.execute_action.remote(workspace_id, action)

# Available metrics
result.success              # Boolean success status
result.execution_time_ms    # Execution time in milliseconds
result.resource_usage       # CPU and memory usage
result.security_violations  # List of security violations
result.state_changes        # Modified files/directories
result.output              # Command stdout
result.error_message       # Error details if failed
```

### System Monitoring

The profiling script provides comprehensive system metrics:

- CPU and memory utilization over time
- Docker container statistics
- Ray cluster resource usage
- Network and disk I/O patterns
- Process count and system load

### Ray Dashboard

Access the Ray dashboard for cluster monitoring:

```bash
# Ray dashboard URL (displayed when Ray starts)
http://127.0.0.1:8265
```

## 🔍 Troubleshooting

### Common Issues

**Docker Permission Denied**
```bash
# Add user to docker group (Linux)
sudo usermod -aG docker $USER
newgrp docker

# Or use sudo
sudo python profile_concurrent.py
```

**Memory Issues with High Concurrency**
```bash
# Reduce concurrent simulations
python profile_concurrent.py --num-concurrent 25

# Or increase system limits
# Edit /etc/docker/daemon.json
{
  "default-ulimits": {
    "memlock": {"Hard": -1, "Name": "memlock", "Soft": -1}
  }
}
```

**Ray Initialization Failures**
```bash
# Clear Ray temporary files
ray stop
rm -rf /tmp/ray

# Restart with explicit configuration
ray start --head --num-cpus=4 --memory=8000000000
```

**Container Creation Timeouts**
```bash
# Check Docker daemon status
docker info

# Restart Docker service
sudo systemctl restart docker  # Linux
# or restart Docker Desktop
```

### Debug Mode

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Or set environment variable
export PYTHONLOGLEVEL=DEBUG
```

### Performance Issues

**Slow Workspace Creation**
- Check available disk space
- Monitor Docker image pull times
- Consider using optimized images

**High Memory Usage**
- Reduce `max_workspaces` in configuration
- Lower per-workspace memory limits
- Enable swap if needed

**Network Timeouts**
- Check Docker network configuration
- Verify proxy settings if using network controls
- Test with `--allow-network` flag

## 🚢 Production Deployment

### Production Checklist

- [ ] **gVisor Runtime**: Enable `runtime="runsc"` for enhanced sandboxing
- [ ] **Network Proxy**: Deploy squid proxy with production configuration
- [ ] **Resource Monitoring**: Integrate with Prometheus/Grafana
- [ ] **Log Aggregation**: Configure centralized logging
- [ ] **Backup Strategy**: Implement workspace data backup
- [ ] **Security Scan**: Run container vulnerability scans
- [ ] **Load Testing**: Validate performance under expected load

### Production Configuration

```python
# production_config.py
config = SimConfig(
    max_workspaces=5000,
    resource_limits={
        "cpu_cores": 1,
        "memory_mb": 1024,
    },
    security_policy={
        "allow_network": False,
        "block_internal_ips": True,
        "enable_gvisor": True,
        "proxy_url": "http://proxy.internal:3128"
    },
    base_image="mechanize/prod-env:latest"
)
```

### Kubernetes Deployment

```yaml
# k8s-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mechanize-simulation
spec:
  replicas: 3
  selector:
    matchLabels:
      app: mechanize-simulation
  template:
    metadata:
      labels:
        app: mechanize-simulation
    spec:
      containers:
      - name: mechanize
        image: mechanize/simulation-env:latest
        resources:
          requests:
            memory: "4Gi"
            cpu: "2"
          limits:
            memory: "8Gi" 
            cpu: "4"
        volumeMounts:
        - name: docker-socket
          mountPath: /var/run/docker.sock
      volumes:
      - name: docker-socket
        hostPath:
          path: /var/run/docker.sock
```

## 📚 API Reference

### SimulationEnvironment

#### `create_workspace(agent_id: str, task_spec: TaskSpec) -> Workspace`
Creates an isolated workspace for an agent.

**Parameters:**
- `agent_id`: Unique identifier for the agent
- `task_spec`: Task specification with ID, description, and criteria

**Returns:** Workspace object with container details

#### `execute_action(workspace_id: str, action: AgentAction) -> ActionResult`
Executes an agent action securely within the workspace.

**Parameters:**
- `workspace_id`: Target workspace identifier
- `action`: Action specification (file edit, terminal command, etc.)

**Returns:** Result with success status, output, and metrics

#### `evaluate_progress(workspace_id: str) -> EvaluationMetrics`
Assesses agent progress on the assigned task.

**Parameters:**
- `workspace_id`: Target workspace identifier

**Returns:** Metrics including completion percentage and quality scores

#### `cleanup_workspace(workspace_id: str) -> None`
Removes workspace and frees all associated resources.

**Parameters:**
- `workspace_id`: Target workspace identifier

### Data Structures

```python
# Action types
ActionType.FILE_EDIT        # File read/write operations
ActionType.TERMINAL_COMMAND # Shell command execution
ActionType.GIT_OPERATION    # Git commands
ActionType.TEST_RUN         # Test execution
ActionType.IDE_ACTION       # IDE-specific actions

# File edit operations
{
    "file_path": "path/to/file.py",
    "operation": "read|write|edit",
    "content": "file content",
    "line_range": [start, end]  # For edit operations
}

# Terminal commands
{
    "command": "python script.py",
    "working_dir": "/workspace",
    "timeout": 30
}
```

## 🤝 Contributing

### Development Setup

```bash
# Clone and setup development environment
git clone <repo-url>
cd mechanize
pip install -r requirements.txt
pip install -r requirements-dev.txt  # If available

# Install pre-commit hooks
pre-commit install

# Run tests
python -m pytest tests.py -v
```

### Code Style

- **Python**: Follow PEP 8, use type hints
- **Documentation**: Docstrings for all public methods
- **Testing**: Add tests for new functionality
- **Security**: All user inputs must be validated

### Submitting Changes

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Update documentation
6. Submit pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

- **Issues**: Report bugs and request features on GitHub Issues
- **Documentation**: Check the `/docs` directory for detailed guides
- **Community**: Join discussions in GitHub Discussions
- **Security**: Report security issues privately to security@mechanize.ai

---

Built with ❤️ for secure AI agent execution environments.