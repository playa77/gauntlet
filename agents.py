# Script Version: 0.2.5 | Phase 1: Agent Foundation
# Description: Specialized agents for the research workflow.
# Implementation: Enhanced JSON extraction logic for modern LLM behavior.

import json
import re
from typing import List, Dict
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

class DecomposeTopicAgent:
    """
    Breaks a broad research topic into specific, prioritized research questions.
    """
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm

    def run(self, topic: str, constraints: Dict = None) -> List[Dict]:
        print(f"[AGENT] Decomposing topic: {topic}")
        
        system_prompt = (
            "You are a Senior Research Architect. Your task is to take a broad research topic "
            "and decompose it into 5-10 specific, non-overlapping research questions. "
            "Each question must be designed to uncover deep insights, methodology, or expert perspectives. "
            "Prioritize questions from foundational to advanced. "
            "Output MUST be a valid JSON list of objects with 'id', 'question', and 'priority' (1-5)."
        )
        
        user_prompt = f"Topic: {topic}\nConstraints: {json.dumps(constraints or {})}\n\nProvide the JSON list now:"
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            response = self.llm.invoke(messages)
            content = response.content

            # 1. Try extracting from Markdown JSON blocks first
            json_block_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if json_block_match:
                try:
                    questions = json.loads(json_block_match.group(1))
                    print(f"[INFO] Extracted JSON from markdown block.")
                    return questions
                except json.JSONDecodeError:
                    pass

            # 2. Fallback to general list extraction
            json_match = re.search(r'\[\s*\{.*\}\s*\]', content, re.DOTALL)
            if json_match:
                questions = json.loads(json_match.group(0))
                print(f"[INFO] Generated {len(questions)} research questions.")
                return questions
            else:
                # 3. Final attempt: direct parse
                return json.loads(content)
                
        except Exception as e:
            print(f"[ERROR] DecomposeTopicAgent failed: {str(e)}")
            # Return a safe fallback to prevent workflow crash
            return [{"id": 1, "question": f"General overview of {topic}", "priority": 1}]
