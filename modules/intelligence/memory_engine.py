import json
import os
import time
from datetime import datetime
from pathlib import Path

class MemoryEngine:
    """
    JARVIS Neural Memory Engine.
    Handles episodic memory storage and long-term context retrieval.
    """
    def __init__(self, memory_path="memory/intelligence/episodic_memory.json"):
        self.memory_path = Path(memory_path)
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
        self.memories = self._load_memory()

    def _load_memory(self):
        if self.memory_path.exists():
            try:
                with open(self.memory_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def save(self):
        with open(self.memory_path, 'w', encoding='utf-8') as f:
            json.dump(self.memories, f, indent=2)

    def add_episodic_memory(self, user_input, jarvis_output, tags=None):
        """Adds a new memory fragment."""
        entry = {
            "id": int(time.time()),
            "timestamp": datetime.now().isoformat(),
            "user": user_input,
            "assistant": jarvis_output,
            "tags": tags or []
        }
        self.memories.append(entry)
        # Keep only last 100 entries for performance (v1.0 threshold)
        if len(self.memories) > 100:
            self.memories = self.memories[-100:]
        self.save()
        return entry

    def retrieve_context(self, query, top_k=3):
        """Retrieves relevant memories based on keyword matching."""
        if not self.memories:
            return []
        
        query_words = set(query.lower().split())
        scored_memories = []
        
        for mem in self.memories:
            content = (mem['user'] + " " + mem['assistant']).lower()
            score = sum(1 for word in query_words if word in content)
            if score > 0:
                scored_memories.append((score, mem))
        
        # Sort by score (desc) then by timestamp (desc)
        scored_memories.sort(key=lambda x: (x[0], x[1]['timestamp']), reverse=True)
        return [m[1] for m in scored_memories[:top_k]]

    def get_summary_for_prompt(self, query):
        """Formats retrieved memories for injection into the LLM context."""
        contexts = self.retrieve_context(query)
        if not contexts:
            return ""
        
        summary = "\n--- RELEVANT NEURAL MEMORY ---\n"
        for ctx in contexts:
            summary += f"[{ctx['timestamp'][:10]}] User: {ctx['user']}\nJARVIS: {ctx['assistant']}\n"
        summary += "------------------------------\n"
        return summary

if __name__ == "__main__":
    # Test Memory Engine
    engine = MemoryEngine(memory_path="/tmp/test_memory.json")
    engine.add_episodic_memory("Remind me that I like dark coffee", "Understood. Neural link updated.")
    print(engine.get_summary_for_prompt("What do I like to drink?"))
