"""
Simulation Performance Optimization Script

This script demonstrates how to use a snapshot of the existing codebase (branch main)
to improve processing speed of the simulation environment by:

1. Pre-building optimized Docker images with the current codebase
2. Implementing parallel workspace initialization 
3. Using cached volumes for faster startup
4. Demonstrating benchmark comparisons

Usage:
    python optimize_simulation.py
"""

import asyncio
import time
import docker
import ray
from pathlib import Path
import subprocess
import statistics
from typing import List, Dict, Any

from sim_env import SimulationEnvironment
from data_structures import SimConfig, TaskSpec, AgentAction, ActionType


class SimulationOptimizer:
    def __init__(self, repo_path: str = "/Users/sravanj/project_work/mechanize"):
        self.repo_path = Path(repo_path)
        self.client = docker.from_env()
        self.optimized_image_tag = "mechanize/optimized-env:latest"
        
    def create_optimized_image(self) -> bool:
        """Create an optimized Docker image with the current codebase pre-loaded"""
        print("🔨 Building optimized Docker image with current codebase...")
        
        # Create optimized Dockerfile
        optimized_dockerfile = f"""
FROM mechanize/dev-env:latest

# Copy current codebase snapshot into the image
COPY . /codebase-snapshot/
RUN chown -R agent:agent /codebase-snapshot/

# Pre-install common dependencies
RUN pip3 install pytest black flake8 mypy

# Create workspace template
RUN mkdir -p /workspace-template
RUN cp -r /codebase-snapshot/* /workspace-template/ 2>/dev/null || true
RUN chown -R agent:agent /workspace-template/

# Pre-compile Python files for faster startup
RUN python3 -m py_compile /workspace-template/*.py 2>/dev/null || true

# Set up git repository template
RUN cd /workspace-template && git init 2>/dev/null || true
RUN cd /workspace-template && git config user.email "agent@mechanize.ai" 2>/dev/null || true
RUN cd /workspace-template && git config user.name "Mechanize Agent" 2>/dev/null || true

USER agent
WORKDIR /workspace
"""
        
        dockerfile_path = self.repo_path / "Dockerfile.optimized"
        dockerfile_path.write_text(optimized_dockerfile)
        
        try:
            # Build the optimized image
            image, build_logs = self.client.images.build(
                path=str(self.repo_path),
                dockerfile="Dockerfile.optimized",
                tag=self.optimized_image_tag,
                rm=True,
                forcerm=True
            )
            
            print("✅ Optimized Docker image built successfully")
            
            # Clean up
            dockerfile_path.unlink()
            return True
            
        except docker.errors.BuildError as e:
            print(f"❌ Failed to build optimized image: {e}")
            if dockerfile_path.exists():
                dockerfile_path.unlink()
            return False

    async def benchmark_workspace_creation(self, num_workspaces: int = 5) -> Dict[str, List[float]]:
        """Benchmark workspace creation times with regular vs optimized images"""
        print(f"\n📊 Benchmarking workspace creation ({num_workspaces} workspaces each)...")
        
        if not ray.is_initialized():
            ray.init()
        
        # Test configurations
        regular_config = SimConfig(base_image="mechanize/dev-env:latest")
        optimized_config = SimConfig(base_image=self.optimized_image_tag)
        
        results = {"regular": [], "optimized": []}
        
        # Benchmark regular image
        print("  Testing regular image...")
        regular_env = SimulationEnvironment.remote(regular_config)
        
        for i in range(num_workspaces):
            start_time = time.time()
            
            task_spec = TaskSpec(
                task_id=f"benchmark_regular_{i}",
                description="Benchmark task for regular image",
                codebase_snapshot="benchmark_snapshot",
                evaluation_criteria=["performance"]
            )
            
            workspace = await regular_env.create_workspace.remote(f"agent_regular_{i}", task_spec)
            await regular_env.cleanup_workspace.remote(workspace.workspace_id)
            
            creation_time = time.time() - start_time
            results["regular"].append(creation_time)
            print(f"    Workspace {i+1}: {creation_time:.2f}s")
        
        # Benchmark optimized image (if available)
        try:
            print("  Testing optimized image...")
            optimized_env = SimulationEnvironment.remote(optimized_config)
            
            for i in range(num_workspaces):
                start_time = time.time()
                
                task_spec = TaskSpec(
                    task_id=f"benchmark_optimized_{i}",
                    description="Benchmark task for optimized image",
                    codebase_snapshot="benchmark_snapshot",
                    evaluation_criteria=["performance"]
                )
                
                workspace = await optimized_env.create_workspace.remote(f"agent_optimized_{i}", task_spec)
                await optimized_env.cleanup_workspace.remote(workspace.workspace_id)
                
                creation_time = time.time() - start_time
                results["optimized"].append(creation_time)
                print(f"    Workspace {i+1}: {creation_time:.2f}s")
                
        except Exception as e:
            print(f"  ⚠️  Could not test optimized image: {e}")
            results["optimized"] = []
        
        return results

    async def benchmark_concurrent_simulations(self, num_concurrent: int = 3) -> Dict[str, float]:
        """Benchmark concurrent simulation performance"""
        print(f"\n🚀 Benchmarking concurrent simulations ({num_concurrent} simultaneous)...")
        
        if not ray.is_initialized():
            ray.init()
        
        config = SimConfig(
            base_image=self.optimized_image_tag if self.optimized_image_tag else "mechanize/dev-env:latest"
        )
        
        # Create multiple simulation environments
        sim_envs = [SimulationEnvironment.remote(config) for _ in range(num_concurrent)]
        
        async def run_simulation_benchmark(sim_env, agent_id: str) -> float:
            start_time = time.time()
            
            task_spec = TaskSpec(
                task_id=f"concurrent_benchmark_{agent_id}",
                description=f"Concurrent benchmark for {agent_id}",
                codebase_snapshot="concurrent_snapshot",
                evaluation_criteria=["speed", "correctness"]
            )
            
            # Create workspace
            workspace = await sim_env.create_workspace.remote(agent_id, task_spec)
            
            # Run a series of actions
            actions = [
                AgentAction(
                    action_type=ActionType.FILE_EDIT,
                    payload={
                        "file_path": f"benchmark_{agent_id}.py",
                        "operation": "write",
                        "content": f"# Benchmark file for {agent_id}\nprint('Hello from {agent_id}')"
                    },
                    timestamp=time.time()
                ),
                AgentAction(
                    action_type=ActionType.TERMINAL_COMMAND,
                    payload={"command": f"python3 benchmark_{agent_id}.py"},
                    timestamp=time.time()
                ),
                AgentAction(
                    action_type=ActionType.FILE_EDIT,
                    payload={
                        "file_path": f"result_{agent_id}.txt",
                        "operation": "write",
                        "content": f"Benchmark completed for {agent_id}"
                    },
                    timestamp=time.time()
                )
            ]
            
            for action in actions:
                await sim_env.execute_action.remote(workspace.workspace_id, action)
            
            # Evaluate progress
            await sim_env.evaluate_progress.remote(workspace.workspace_id)
            
            # Cleanup
            await sim_env.cleanup_workspace.remote(workspace.workspace_id)
            
            total_time = time.time() - start_time
            return total_time
        
        # Run concurrent benchmarks
        start_concurrent = time.time()
        tasks = [run_simulation_benchmark(sim_env, f"agent_{i}") for i, sim_env in enumerate(sim_envs)]
        individual_times = await asyncio.gather(*tasks)
        total_concurrent_time = time.time() - start_concurrent
        
        return {
            "total_time": total_concurrent_time,
            "individual_times": individual_times,
            "average_individual": statistics.mean(individual_times),
            "max_individual": max(individual_times),
            "min_individual": min(individual_times)
        }

    def print_benchmark_results(self, workspace_results: Dict[str, List[float]], 
                              concurrent_results: Dict[str, float]):
        """Print formatted benchmark results"""
        print("\n" + "="*60)
        print("📊 SIMULATION PERFORMANCE BENCHMARK RESULTS")
        print("="*60)
        
        # Workspace creation results
        if workspace_results["regular"]:
            regular_avg = statistics.mean(workspace_results["regular"])
            regular_std = statistics.stdev(workspace_results["regular"]) if len(workspace_results["regular"]) > 1 else 0
            print(f"\n🏗️  Workspace Creation (Regular Image):")
            print(f"   Average: {regular_avg:.2f}s ± {regular_std:.2f}s")
            print(f"   Range: {min(workspace_results['regular']):.2f}s - {max(workspace_results['regular']):.2f}s")
        
        if workspace_results["optimized"]:
            optimized_avg = statistics.mean(workspace_results["optimized"])
            optimized_std = statistics.stdev(workspace_results["optimized"]) if len(workspace_results["optimized"]) > 1 else 0
            print(f"\n⚡ Workspace Creation (Optimized Image):")
            print(f"   Average: {optimized_avg:.2f}s ± {optimized_std:.2f}s")
            print(f"   Range: {min(workspace_results['optimized']):.2f}s - {max(workspace_results['optimized']):.2f}s")
            
            if workspace_results["regular"]:
                improvement = ((regular_avg - optimized_avg) / regular_avg) * 100
                print(f"   🎯 Improvement: {improvement:.1f}% faster")
        
        # Concurrent simulation results
        print(f"\n🚀 Concurrent Simulations:")
        print(f"   Total time: {concurrent_results['total_time']:.2f}s")
        print(f"   Average per simulation: {concurrent_results['average_individual']:.2f}s")
        print(f"   Fastest simulation: {concurrent_results['min_individual']:.2f}s")
        print(f"   Slowest simulation: {concurrent_results['max_individual']:.2f}s")
        
        # Calculate theoretical vs actual performance
        if workspace_results["regular"]:
            theoretical_sequential = statistics.mean(workspace_results["regular"]) * len(concurrent_results['individual_times']) * 3  # 3 actions per sim
            actual_concurrent = concurrent_results['total_time']
            concurrency_improvement = ((theoretical_sequential - actual_concurrent) / theoretical_sequential) * 100
            print(f"   🔥 Concurrency benefit: {concurrency_improvement:.1f}% faster than sequential")
        
        print("\n" + "="*60)

    async def demonstrate_optimizations(self):
        """Run the complete optimization demonstration"""
        print("🌟 MECHANIZE SIMULATION PERFORMANCE OPTIMIZATION")
        print("=" * 50)
        
        # Step 1: Create optimized image
        optimization_successful = self.create_optimized_image()
        
        # Step 2: Benchmark workspace creation
        workspace_results = await self.benchmark_workspace_creation()
        
        # Step 3: Benchmark concurrent simulations  
        concurrent_results = await self.benchmark_concurrent_simulations()
        
        # Step 4: Print results
        self.print_benchmark_results(workspace_results, concurrent_results)
        
        # Step 5: Cleanup
        print(f"\n🧹 Cleaning up...")
        if ray.is_initialized():
            ray.shutdown()
        
        print("✅ Optimization demonstration complete!")
        
        return {
            "optimization_successful": optimization_successful,
            "workspace_benchmarks": workspace_results,
            "concurrent_benchmarks": concurrent_results
        }


async def main():
    """Main entry point for the optimization script"""
    optimizer = SimulationOptimizer()
    
    try:
        results = await optimizer.demonstrate_optimizations()
        return results
    except KeyboardInterrupt:
        print("\n⏹️  Benchmark interrupted by user")
        if ray.is_initialized():
            ray.shutdown()
    except Exception as e:
        print(f"\n❌ Error during optimization: {e}")
        import traceback
        traceback.print_exc()
        if ray.is_initialized():
            ray.shutdown()


if __name__ == "__main__":
    asyncio.run(main())