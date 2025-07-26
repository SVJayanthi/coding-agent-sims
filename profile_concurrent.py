#!/usr/bin/env python3
"""
Mechanize Simulation Environment - Concurrent Profiling Script

This script benchmarks the simulation environment with 100 concurrent simulations
to test scalability, performance, and resource utilization under heavy load.

Usage:
    python profile_concurrent.py [--num-concurrent 100] [--actions-per-sim 5] [--profile-memory]
"""

import asyncio
import time
import argparse
import sys
import statistics
import psutil
from typing import List, Dict, Any
import ray
from concurrent.futures import ThreadPoolExecutor
import threading
import json

from sim_env import SimulationEnvironment
from data_structures import SimConfig, TaskSpec, AgentAction, ActionType


class ConcurrentProfiler:
    def __init__(self, num_concurrent: int = 100, actions_per_sim: int = 5, profile_memory: bool = False):
        self.num_concurrent = num_concurrent
        self.actions_per_sim = actions_per_sim
        self.profile_memory = profile_memory
        self.results = {}
        self.system_stats = []
        self.monitoring_active = False
        
    def start_system_monitoring(self):
        """Start background system monitoring thread"""
        self.monitoring_active = True
        
        def monitor():
            while self.monitoring_active:
                try:
                    stats = {
                        'timestamp': time.time(),
                        'cpu_percent': psutil.cpu_percent(interval=0.1),
                        'memory_percent': psutil.virtual_memory().percent,
                        'memory_used_gb': psutil.virtual_memory().used / (1024**3),
                        'disk_io': psutil.disk_io_counters()._asdict() if psutil.disk_io_counters() else {},
                        'network_io': psutil.net_io_counters()._asdict() if psutil.net_io_counters() else {},
                        'num_processes': len(psutil.pids()),
                        'load_average': psutil.getloadavg() if hasattr(psutil, 'getloadavg') else [0, 0, 0]
                    }
                    self.system_stats.append(stats)
                    time.sleep(1)  # Monitor every second
                except Exception as e:
                    print(f"Monitoring error: {e}")
                    
        monitor_thread = threading.Thread(target=monitor, daemon=True)
        monitor_thread.start()
        
    def stop_system_monitoring(self):
        """Stop system monitoring"""
        self.monitoring_active = False
        
    async def create_simulation_task(self, sim_id: int, config: SimConfig) -> Dict[str, Any]:
        """Create and run a single simulation task"""
        start_time = time.time()
        task_results = {
            'sim_id': sim_id,
            'start_time': start_time,
            'workspace_creation_time': 0,
            'action_times': [],
            'total_time': 0,
            'success': False,
            'errors': [],
            'actions_completed': 0
        }
        
        try:
            # Create simulation environment
            sim_env = SimulationEnvironment.remote(config)
            
            # Create workspace
            workspace_start = time.time()
            task_spec = TaskSpec(
                task_id=f"concurrent_profile_{sim_id}",
                description=f"Concurrent profiling simulation {sim_id}",
                codebase_snapshot=f"profile_snapshot_{sim_id}",
                evaluation_criteria=["performance", "concurrency", "stability"]
            )
            
            workspace = await sim_env.create_workspace.remote(f"profile_agent_{sim_id}", task_spec)
            task_results['workspace_creation_time'] = time.time() - workspace_start
            
            # Execute actions
            actions = self.generate_test_actions(sim_id)
            
            for i, action in enumerate(actions[:self.actions_per_sim]):
                action_start = time.time()
                try:
                    result = await sim_env.execute_action.remote(workspace.workspace_id, action)
                    action_time = time.time() - action_start
                    task_results['action_times'].append({
                        'action_id': i,
                        'action_type': action.action_type.value,
                        'duration': action_time,
                        'success': result.success,
                        'error': result.error_message if not result.success else None
                    })
                    
                    if result.success:
                        task_results['actions_completed'] += 1
                    else:
                        task_results['errors'].append(f"Action {i}: {result.error_message}")
                        
                except Exception as e:
                    action_time = time.time() - action_start
                    task_results['action_times'].append({
                        'action_id': i,
                        'action_type': action.action_type.value,
                        'duration': action_time,
                        'success': False,
                        'error': str(e)
                    })
                    task_results['errors'].append(f"Action {i} exception: {e}")
            
            # Evaluate progress
            try:
                metrics = await sim_env.evaluate_progress.remote(workspace.workspace_id)
                task_results['completion_percentage'] = metrics.completion_percentage
                task_results['code_quality_score'] = metrics.code_quality_score
            except Exception as e:
                task_results['errors'].append(f"Evaluation error: {e}")
            
            # Cleanup
            try:
                await sim_env.cleanup_workspace.remote(workspace.workspace_id)
            except Exception as e:
                task_results['errors'].append(f"Cleanup error: {e}")
                
            task_results['success'] = len(task_results['errors']) == 0
            task_results['total_time'] = time.time() - start_time
            
        except Exception as e:
            task_results['errors'].append(f"Simulation {sim_id} failed: {e}")
            task_results['total_time'] = time.time() - start_time
            
        return task_results
        
    def generate_test_actions(self, sim_id: int) -> List[AgentAction]:
        """Generate test actions for the simulation"""
        return [
            # File creation
            AgentAction(
                action_type=ActionType.FILE_EDIT,
                payload={
                    "file_path": f"profile_test_{sim_id}.py",
                    "operation": "write",
                    "content": f"# Profile test file for simulation {sim_id}\nprint('Simulation {sim_id} running')\n\ndef test_function():\n    return {sim_id} * 2"
                },
                timestamp=time.time()
            ),
            # File read
            AgentAction(
                action_type=ActionType.FILE_EDIT,
                payload={
                    "file_path": f"profile_test_{sim_id}.py",
                    "operation": "read"
                },
                timestamp=time.time()
            ),
            # Terminal command
            AgentAction(
                action_type=ActionType.TERMINAL_COMMAND,
                payload={
                    "command": f"python3 profile_test_{sim_id}.py"
                },
                timestamp=time.time()
            ),
            # Create another file
            AgentAction(
                action_type=ActionType.FILE_EDIT,
                payload={
                    "file_path": f"results_{sim_id}.txt",
                    "operation": "write",
                    "content": f"Results for simulation {sim_id}\nStatus: Running\nTimestamp: {time.time()}"
                },
                timestamp=time.time()
            ),
            # List workspace contents
            AgentAction(
                action_type=ActionType.TERMINAL_COMMAND,
                payload={
                    "command": "ls -la /workspace/"
                },
                timestamp=time.time()
            ),
            # Git initialization (will fail but tests error handling)
            AgentAction(
                action_type=ActionType.GIT_OPERATION,
                payload={
                    "command": "git init && git config user.email 'test@example.com' && git config user.name 'Test User'"
                },
                timestamp=time.time()
            ),
            # Create test script
            AgentAction(
                action_type=ActionType.FILE_EDIT,
                payload={
                    "file_path": f"test_{sim_id}.sh",
                    "operation": "write",
                    "content": f"#!/bin/bash\necho 'Test script for simulation {sim_id}'\ndate\nwhoami\nls -la"
                },
                timestamp=time.time()
            ),
            # Make script executable and run it
            AgentAction(
                action_type=ActionType.TERMINAL_COMMAND,
                payload={
                    "command": f"chmod +x test_{sim_id}.sh && ./test_{sim_id}.sh"
                },
                timestamp=time.time()
            )
        ]
        
    async def run_concurrent_profile(self) -> Dict[str, Any]:
        """Run the concurrent profiling benchmark"""
        print(f"🚀 Starting concurrent profiling with {self.num_concurrent} simulations")
        print(f"📊 Actions per simulation: {self.actions_per_sim}")
        print(f"🔍 Memory profiling: {'Enabled' if self.profile_memory else 'Disabled'}")
        print("=" * 60)
        
        # Initialize Ray
        if not ray.is_initialized():
            ray.init(num_cpus=None, object_store_memory=2000000000)  # 2GB object store
            
        # Start system monitoring
        self.start_system_monitoring()
        
        # Configuration
        config = SimConfig(
            max_workspaces=self.num_concurrent + 10,  # Buffer for safety
            resource_limits={"memory_mb": 512, "cpu_cores": 1},  # Conservative limits
            base_image="mechanize/dev-env:latest"
        )
        
        # Record initial system state
        initial_stats = {
            'memory_used_gb': psutil.virtual_memory().used / (1024**3),
            'cpu_percent': psutil.cpu_percent(interval=1),
            'num_processes': len(psutil.pids()),
            'ray_cluster_resources': ray.cluster_resources()
        }
        
        print(f"📈 Initial system state:")
        print(f"   Memory used: {initial_stats['memory_used_gb']:.2f} GB")
        print(f"   CPU usage: {initial_stats['cpu_percent']:.1f}%")
        print(f"   Processes: {initial_stats['num_processes']}")
        print(f"   Ray resources: {initial_stats['ray_cluster_resources']}")
        print()
        
        # Start concurrent simulations
        start_time = time.time()
        print(f"⏱️  Starting {self.num_concurrent} concurrent simulations at {time.strftime('%H:%M:%S')}...")
        
        # Create tasks
        tasks = [
            self.create_simulation_task(i, config) 
            for i in range(self.num_concurrent)
        ]
        
        # Run with progress updates
        completed_tasks = []
        batch_size = 10  # Process in batches to avoid overwhelming the system
        
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            batch_start = time.time()
            
            print(f"📦 Processing batch {i//batch_size + 1}/{(len(tasks) + batch_size - 1)//batch_size} ({len(batch)} simulations)...")
            
            batch_results = await asyncio.gather(*batch, return_exceptions=True)
            completed_tasks.extend(batch_results)
            
            batch_time = time.time() - batch_start
            print(f"   ✅ Batch completed in {batch_time:.2f}s")
            
            # Brief pause between batches to let system stabilize
            if i + batch_size < len(tasks):
                await asyncio.sleep(1)
        
        total_time = time.time() - start_time
        
        # Stop monitoring
        self.stop_system_monitoring()
        
        # Process results
        successful_tasks = [task for task in completed_tasks if isinstance(task, dict) and task.get('success', False)]
        failed_tasks = [task for task in completed_tasks if isinstance(task, dict) and not task.get('success', False)]
        exception_tasks = [task for task in completed_tasks if not isinstance(task, dict)]
        
        # Calculate statistics
        if successful_tasks:
            workspace_creation_times = [task['workspace_creation_time'] for task in successful_tasks]
            total_times = [task['total_time'] for task in successful_tasks]
            actions_completed = [task['actions_completed'] for task in successful_tasks]
            
            # Action timing statistics
            all_action_times = []
            for task in successful_tasks:
                for action in task['action_times']:
                    if action['success']:
                        all_action_times.append(action['duration'])
        else:
            workspace_creation_times = total_times = actions_completed = all_action_times = []
        
        # System performance analysis
        if self.system_stats:
            peak_memory = max(stat['memory_used_gb'] for stat in self.system_stats)
            peak_cpu = max(stat['cpu_percent'] for stat in self.system_stats)
            avg_memory = statistics.mean(stat['memory_used_gb'] for stat in self.system_stats)
            avg_cpu = statistics.mean(stat['cpu_percent'] for stat in self.system_stats)
        else:
            peak_memory = peak_cpu = avg_memory = avg_cpu = 0
        
        # Compile results
        results = {
            'configuration': {
                'num_concurrent': self.num_concurrent,
                'actions_per_sim': self.actions_per_sim,
                'profile_memory': self.profile_memory,
                'total_time': total_time
            },
            'success_metrics': {
                'successful_simulations': len(successful_tasks),
                'failed_simulations': len(failed_tasks),
                'exception_simulations': len(exception_tasks),
                'success_rate': len(successful_tasks) / self.num_concurrent if self.num_concurrent > 0 else 0
            },
            'timing_metrics': {
                'total_execution_time': total_time,
                'avg_workspace_creation_time': statistics.mean(workspace_creation_times) if workspace_creation_times else 0,
                'avg_simulation_time': statistics.mean(total_times) if total_times else 0,
                'avg_action_time': statistics.mean(all_action_times) if all_action_times else 0,
                'max_simulation_time': max(total_times) if total_times else 0,
                'min_simulation_time': min(total_times) if total_times else 0,
                'simulations_per_second': self.num_concurrent / total_time if total_time > 0 else 0
            },
            'system_metrics': {
                'initial_memory_gb': initial_stats['memory_used_gb'],
                'peak_memory_gb': peak_memory,
                'avg_memory_gb': avg_memory,
                'memory_increase_gb': peak_memory - initial_stats['memory_used_gb'],
                'initial_cpu_percent': initial_stats['cpu_percent'],
                'peak_cpu_percent': peak_cpu,
                'avg_cpu_percent': avg_cpu,
                'initial_processes': initial_stats['num_processes'],
                'ray_resources': initial_stats['ray_cluster_resources']
            },
            'detailed_results': completed_tasks[:10] if self.profile_memory else [],  # Sample for debugging
            'system_timeline': self.system_stats[-60:] if self.profile_memory else []  # Last minute of data
        }
        
        self.results = results
        return results
        
    def print_results(self):
        """Print formatted benchmark results"""
        results = self.results
        if not results:
            print("❌ No results to display")
            return
            
        print("\n" + "="*80)
        print("🎯 CONCURRENT SIMULATION PROFILING RESULTS")
        print("="*80)
        
        # Configuration
        config = results['configuration']
        print(f"\n📋 Configuration:")
        print(f"   Concurrent simulations: {config['num_concurrent']}")
        print(f"   Actions per simulation: {config['actions_per_sim']}")
        print(f"   Total execution time: {config['total_time']:.2f}s")
        
        # Success metrics
        success = results['success_metrics']
        print(f"\n✅ Success Metrics:")
        print(f"   Successful simulations: {success['successful_simulations']}")
        print(f"   Failed simulations: {success['failed_simulations']}")
        print(f"   Exception simulations: {success['exception_simulations']}")
        print(f"   Success rate: {success['success_rate']:.1%}")
        
        # Timing metrics
        timing = results['timing_metrics']
        print(f"\n⏱️  Timing Metrics:")
        print(f"   Average workspace creation: {timing['avg_workspace_creation_time']:.2f}s")
        print(f"   Average simulation time: {timing['avg_simulation_time']:.2f}s")
        print(f"   Average action time: {timing['avg_action_time']:.3f}s")
        print(f"   Simulation time range: {timing['min_simulation_time']:.2f}s - {timing['max_simulation_time']:.2f}s")
        print(f"   Throughput: {timing['simulations_per_second']:.2f} simulations/second")
        
        # System metrics
        system = results['system_metrics']
        print(f"\n💻 System Performance:")
        print(f"   Memory usage: {system['initial_memory_gb']:.2f} → {system['peak_memory_gb']:.2f} GB (Δ{system['memory_increase_gb']:.2f} GB)")
        print(f"   CPU usage: {system['initial_cpu_percent']:.1f}% → {system['peak_cpu_percent']:.1f}% (avg: {system['avg_cpu_percent']:.1f}%)")
        print(f"   Process count: {system['initial_processes']} initial")
        print(f"   Ray cluster resources: {system['ray_resources']}")
        
        # Performance analysis
        print(f"\n📊 Performance Analysis:")
        if success['success_rate'] >= 0.95:
            print("   🟢 Excellent success rate (≥95%)")
        elif success['success_rate'] >= 0.80:
            print("   🟡 Good success rate (≥80%)")
        else:
            print("   🔴 Poor success rate (<80%)")
            
        if timing['simulations_per_second'] >= 10:
            print("   🟢 High throughput (≥10 sim/sec)")
        elif timing['simulations_per_second'] >= 5:
            print("   🟡 Moderate throughput (≥5 sim/sec)")
        else:
            print("   🔴 Low throughput (<5 sim/sec)")
            
        if system['memory_increase_gb'] < 1.0:
            print("   🟢 Low memory overhead (<1GB)")
        elif system['memory_increase_gb'] < 3.0:
            print("   🟡 Moderate memory overhead (<3GB)")
        else:
            print("   🔴 High memory overhead (≥3GB)")
            
        print("\n" + "="*80)
        
    def save_results(self, filename: str = None):
        """Save results to JSON file"""
        if not filename:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"concurrent_profile_results_{timestamp}.json"
            
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
            
        print(f"💾 Results saved to {filename}")


async def main():
    parser = argparse.ArgumentParser(description='Profile concurrent simulations')
    parser.add_argument('--num-concurrent', type=int, default=100,
                       help='Number of concurrent simulations (default: 100)')
    parser.add_argument('--actions-per-sim', type=int, default=5,
                       help='Number of actions per simulation (default: 5)')
    parser.add_argument('--profile-memory', action='store_true',
                       help='Enable detailed memory profiling (slower)')
    parser.add_argument('--save-results', type=str, default=None,
                       help='Save results to JSON file')
    
    args = parser.parse_args()
    
    print("🔬 Mechanize Concurrent Simulation Profiler")
    print("="*50)
    
    profiler = ConcurrentProfiler(
        num_concurrent=args.num_concurrent,
        actions_per_sim=args.actions_per_sim,
        profile_memory=args.profile_memory
    )
    
    try:
        # Run the profile
        await profiler.run_concurrent_profile()
        
        # Display results
        profiler.print_results()
        
        # Save results if requested
        if args.save_results or args.profile_memory:
            profiler.save_results(args.save_results)
            
    except KeyboardInterrupt:
        print("\n⏹️  Profiling interrupted by user")
    except Exception as e:
        print(f"\n❌ Profiling failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        if ray.is_initialized():
            ray.shutdown()
        print("\n🧹 Cleanup completed")


if __name__ == "__main__":
    asyncio.run(main())