"""
Automatic Agent Discovery and Integration
Scans your agents/ directory and creates LangGraph-compatible wrappers
"""
import os
import sys
import importlib
import inspect
from pathlib import Path
from typing import Dict, Any, List, Callable
from core.state_schema import ESGState

class AgentDiscovery:
    def __init__(self, agents_directory: str = "agents"):
        self.agents_dir = Path(agents_directory)
        self.discovered_agents = {}
        self.agent_methods = {}
        
    def scan_agents(self) -> Dict[str, Any]:
        """
        Automatically discover all agent classes in agents/ directory
        """
        if not self.agents_dir.exists():
            print(f"⚠️  Agents directory '{self.agents_dir}' not found")
            return {}
        
        print(f"\n🔍 Scanning {self.agents_dir} for agent classes...")
        
        # Add agents directory to Python path
        sys.path.insert(0, str(self.agents_dir.parent))
        
        # Scan all Python files
        for py_file in self.agents_dir.glob("*.py"):
            if py_file.name.startswith("__"):
                continue
            
            module_name = f"agents.{py_file.stem}"
            
            try:
                # Import module
                module = importlib.import_module(module_name)
                
                # Find agent classes
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if name.endswith("Agent") and module.__name__ in obj.__module__:
                        agent_key = self._normalize_agent_name(name)
                        self.discovered_agents[agent_key] = {
                            "class": obj,
                            "module": module_name,
                            "file": str(py_file),
                            "methods": self._get_public_methods(obj)
                        }
                        print(f"  ✅ Found: {name} ({len(self.discovered_agents[agent_key]['methods'])} methods)")
                        
            except Exception as e:
                print(f"  ⚠️  Error loading {py_file.name}: {e}")
        
        print(f"\n📊 Total agents discovered: {len(self.discovered_agents)}")
        return self.discovered_agents
    
    def _normalize_agent_name(self, class_name: str) -> str:
        """Convert class name to standardized key (e.g., ClaimExtractionAgent -> claim_extraction)"""
        name = class_name.replace("Agent", "")
        # Convert CamelCase to snake_case
        import re
        name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        name = re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()
        return name
    
    def _get_public_methods(self, agent_class) -> List[str]:
        """Get all public methods from agent class"""
        methods = []
        for name, method in inspect.getmembers(agent_class, inspect.isfunction):
            if not name.startswith("_") and name != "run":
                methods.append(name)
        return methods
    
    def create_wrapper(self, agent_key: str, method_name: str = None) -> Callable:
        """
        Create LangGraph-compatible wrapper for an agent
        """
        if agent_key not in self.discovered_agents:
            raise ValueError(f"Agent '{agent_key}' not found")
        
        agent_info = self.discovered_agents[agent_key]
        agent_class = agent_info["class"]
        
        # Auto-detect main method if not specified
        if method_name is None:
            method_name = self._detect_main_method(agent_info)
        
        def wrapper_function(state: ESGState) -> ESGState:
            """Generated wrapper for {agent_key}"""
            try:
                # Instantiate agent
                agent = agent_class()
                
                # Call agent method with smart parameter passing
                result = self._call_agent_method(agent, method_name, state)
                
                # Extract confidence from result
                confidence = self._extract_confidence(result)
                
                # Update state
                state["agent_outputs"].append({
                    "agent": agent_key,
                    "output": result,
                    "confidence": confidence,
                    "method": method_name,
                    "timestamp": str(__import__('datetime').datetime.now())
                })
                
                # Special handling for specific agents
                if agent_key == "risk_scoring":
                    state = self._handle_risk_scoring(state, result)
                elif agent_key == "evidence_retrieval":
                    state = self._handle_evidence_retrieval(state, result)
                elif agent_key == "report_generation":
                    state = self._handle_report_generation(state, result)
                
            except Exception as e:
                print(f"⚠️  {agent_key} error: {e}")
                state["agent_outputs"].append({
                    "agent": agent_key,
                    "error": str(e),
                    "confidence": 0.0
                })
            
            return state
        
        wrapper_function.__name__ = f"{agent_key}_node"
        return wrapper_function
    
    def _detect_main_method(self, agent_info: Dict) -> str:
        """Auto-detect the main method to call"""
        methods = agent_info["methods"]
        
        # Priority order of common method names
        common_names = [
            "analyze", "process", "execute", "run", "extract", 
            "gather", "retrieve", "calculate", "score", "generate"
        ]
        
        # Check for exact matches
        for common in common_names:
            if common in methods:
                return common
        
        # Check for partial matches (e.g., "extract_claims" contains "extract")
        for common in common_names:
            for method in methods:
                if common in method.lower():
                    return method
        
        # Return first public method as fallback
        return methods[0] if methods else "run"
    
    def _call_agent_method(self, agent: Any, method_name: str, state: ESGState) -> Any:
        """
        Smart parameter passing based on method signature
        """
        method = getattr(agent, method_name)
        sig = inspect.signature(method)
        params = list(sig.parameters.keys())
        
        # Build arguments based on method signature
        kwargs = {}
        
        if "company" in params or "company_name" in params:
            kwargs["company"] = state["company"]
        
        if "claim" in params or "claims" in params:
            kwargs["claim"] = state["claim"]
        
        if "industry" in params:
            kwargs["industry"] = state["industry"]
        
        if "evidence" in params:
            kwargs["evidence"] = state["evidence"]
        
        if "state" in params:
            kwargs["state"] = state
        
        # Call with discovered parameters
        if kwargs:
            return method(**kwargs)
        else:
            # Try calling without arguments
            return method()
    
    def _extract_confidence(self, result: Any) -> float:
        """Extract confidence score from agent result"""
        if isinstance(result, dict):
            # Try common confidence keys
            for key in ["confidence", "confidence_score", "score", "certainty"]:
                if key in result:
                    return float(result[key])
        
        # Default confidence
        return 0.7
    
    def _handle_risk_scoring(self, state: ESGState, result: Any) -> ESGState:
        """Special handling for risk scoring agent"""
        if isinstance(result, dict):
            if "risk_level" in result:
                state["risk_level"] = result["risk_level"]
            elif "risk" in result:
                state["risk_level"] = result["risk"]
        return state
    
    def _handle_evidence_retrieval(self, state: ESGState, result: Any) -> ESGState:
        """Special handling for evidence retrieval agent"""
        if isinstance(result, dict) and "evidence" in result:
            if isinstance(result["evidence"], list):
                state["evidence"].extend(result["evidence"])
            else:
                state["evidence"].append(result["evidence"])
        elif isinstance(result, list):
            state["evidence"].extend(result)
        return state
    
    def _handle_report_generation(self, state: ESGState, result: Any) -> ESGState:
        """Special handling for report generation agent"""
        if isinstance(result, dict) and "report" in result:
            state["report"] = result["report"]
        elif isinstance(result, str):
            state["report"] = result
        return state
    
    def generate_integration_report(self) -> str:
        """Generate a report of discovered agents"""
        report = "\n" + "="*70 + "\n"
        report += "AGENT DISCOVERY REPORT\n"
        report += "="*70 + "\n\n"
        
        for agent_key, info in self.discovered_agents.items():
            report += f"📦 {agent_key}\n"
            report += f"   File: {info['file']}\n"
            report += f"   Class: {info['class'].__name__}\n"
            report += f"   Methods: {', '.join(info['methods'])}\n"
            report += f"   Main method: {self._detect_main_method(info)}\n\n"
        
        return report

# Singleton instance
_agent_discovery = None

def get_agent_discovery() -> AgentDiscovery:
    """Get or create agent discovery instance"""
    global _agent_discovery
    if _agent_discovery is None:
        _agent_discovery = AgentDiscovery()
        _agent_discovery.scan_agents()
    return _agent_discovery
