import os
import sys
import subprocess
import gc
import mesa
import psutil

def get_memory_mb():
    """Precise RSS memory tracking using psutil."""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024

class ChurnAgent(mesa.Agent):
    """A lightweight agent designed strictly for footprint testing."""
    def __init__(self, model):
        super().__init__(model)
    
    def step(self):
        pass

class StressTestModel(mesa.Model):
    """Stress test model targeting Mesa 3.5.0 infrastructure."""
    def __init__(self, agent_count=10000):
        super().__init__()
        self.agent_count = agent_count
        self.churned_agents = []

    def churn_logic(self):
        self.churned_agents.clear()
        # Step 1: High-volume Creation using Batching
        with mesa.signals.batch():
            for _ in range(self.agent_count):
                self.churned_agents.append(ChurnAgent(self))
                
        # Step 2: Immediate Deletion using Suppression
        with mesa.signals.suppress():
            for agent in self.churned_agents:
                agent.remove()
        self.churned_agents.clear()

    def step(self):
        self.churn_logic()
        super().step()

def run_suite(steps=50, agent_count=10000):
    model = StressTestModel(agent_count)
    print(f"{'Step':<8} | {'Memory (MB)':<15} | {'GC Freed (MB)':<15}")
    print("-" * 45)
    
    for i in range(1, steps + 1):
        mem_before = get_memory_mb()
        model.step()
        mem_after = get_memory_mb()
        gc.collect()
        mem_after_gc = get_memory_mb()
        
        if i % 10 == 0 or i == 1:
            print(f"{i:<8} | {mem_after_gc:<15.2f} | {mem_after - mem_after_gc:<15.2f}")

if __name__ == '__main__':
    run_suite()
