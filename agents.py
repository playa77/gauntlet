# Script Version: 0.4.1 | Phase 2: Orchestration
# Description: Specialized agents using externalized prompts and role-specific configurations.
# Implementation: Strictly separates prompt logic from Python code.

import json
import re
import time
import httpx
import urllib.parse
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

class BaseAgent:
    """Base class for all agents to handle LLM and externalized prompts."""
    def __init__(self, llm: ChatOpenAI, prompts: Dict):
        self.llm = llm
        self.prompts = prompts

class DecomposeTopicAgent(BaseAgent):
    """Breaks a broad research topic into specific, prioritized research questions."""
    def run(self, topic: str, constraints: Dict = None) -> List[Dict]:
        print(f"[AGENT] [Decompose] Decomposing topic: {topic}")
        p = self.prompts.get("decompose_topic", {})
        system_content = p.get("system", "You are a research architect.")
        user_template = p.get("user_template", "Topic: {topic}")
        
        user_content = user_template.format(
            topic=topic, 
            constraints=json.dumps(constraints or {})
        )
        
        try:
            messages = [
                SystemMessage(content=system_content),
                HumanMessage(content=user_content)
            ]
            response = self.llm.invoke(messages)
            content = response.content

            # Robust JSON extraction
            json_match = re.search(r'\[\s*\{.*\}\s*\]', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            return json.loads(content)
                
        except Exception as e:
            print(f"[ERROR] [Decompose] Failed: {str(e)}")
            return [{"id": 1, "question": f"General overview of {topic}", "priority": 1}]

class InitialSearchAgent(BaseAgent):
    """Generates search queries and retrieves candidate URLs using DuckDuckGo."""
    def __init__(self, llm: ChatOpenAI, prompts: Dict, source_manager: Any):
        super().__init__(llm, prompts)
        self.source_manager = source_manager

    def run(self, questions: List[Dict]) -> List[Dict]:
        from duckduckgo_search import DDGS
        print(f"[AGENT] [Search] Generating queries for {len(questions)} questions...")
        
        all_results = []
        p = self.prompts.get("search_query_generation", {})
        user_template = p.get("user_template", "Queries for: {question}")

        for q in questions:
            try:
                user_content = user_template.format(question=q['question'])
                response = self.llm.invoke([HumanMessage(content=user_content)])
                queries = [item.strip().strip('"') for item in response.content.split(',')]
                
                for query in queries:
                    self.source_manager._wait_for_slot()
                    print(f"[AGENT] [Search] Executing query: {query}")
                    with DDGS() as ddgs:
                        results = list(ddgs.text(query, max_results=5))
                        for r in results:
                            all_results.append({
                                "url": r['href'],
                                "title": r['title'],
                                "snippet": r['body'],
                                "question_id": q['id']
                            })
                    self.source_manager.last_request_completion_time = time.perf_counter()
            except Exception as e:
                print(f"[ERROR] [Search] Failed query for question {q['id']}: {e}")
                
        return all_results

class SourceQualityAgent(BaseAgent):
    """Evaluates the credibility and relevance of candidate sources."""
    def run(self, candidates: List[Dict]) -> Dict[str, Any]:
        print(f"[AGENT] [Quality] Assessing {len(candidates)} candidate sources...")
        scored_sources = []
        total_score = 0.0
        p = self.prompts.get("source_quality_assessment", {})
        user_template = p.get("user_template", "Score: {url}")

        for source in candidates[:10]: 
            try:
                user_content = user_template.format(
                    url=source['url'], 
                    title=source['title'], 
                    snippet=source['snippet']
                )
                response = self.llm.invoke([HumanMessage(content=user_content)])
                match = re.search(r'\{.*\}', response.content, re.DOTALL)
                if match:
                    data = json.loads(match.group(0))
                    source.update(data)
                    scored_sources.append(source)
                    total_score += float(data.get('score', 0))
            except Exception as e:
                print(f"[ERROR] [Quality] Failed to score {source['url']}: {e}")
        
        avg_score = total_score / len(scored_sources) if scored_sources else 0.0
        return {"sources": scored_sources, "average_score": avg_score}

class AcademicSpecialistAgent(BaseAgent):
    """Queries scholarly APIs (arXiv) to find peer-reviewed sources."""
    def __init__(self, llm: ChatOpenAI, prompts: Dict, source_manager: Any):
        super().__init__(llm, prompts)
        self.source_manager = source_manager

    def run(self, questions: List[Dict]) -> List[Dict]:
        print(f"[AGENT] [Academic] Searching scholarly databases...")
        academic_results = []
        
        for q in questions[:3]:
            query = q['question']
            encoded_query = urllib.parse.quote(query)
            
            # arXiv Search
            print(f"[AGENT] [Academic] Querying arXiv for: {query[:50]}...")
            arxiv_url = f"http://export.arxiv.org/api/query?search_query=all:{encoded_query}&start=0&max_results=3"
            try:
                self.source_manager._wait_for_slot()
                with httpx.Client(timeout=20.0) as client:
                    resp = client.get(arxiv_url)
                    self.source_manager.last_request_completion_time = time.perf_counter()
                    if resp.status_code == 200:
                        root = ET.fromstring(resp.text)
                        for entry in root.findall('{http://www.w3.org/2005/Atom}entry'):
                            academic_results.append({
                                "url": entry.find('{http://www.w3.org/2005/Atom}id').text,
                                "title": f"[arXiv] {entry.find('{http://www.w3.org/2005/Atom}title').text.strip()}",
                                "snippet": entry.find('{http://www.w3.org/2005/Atom}summary').text.strip()[:500],
                                "question_id": q['id'],
                                "source_type": "academic"
                            })
            except Exception as e:
                print(f"[ERROR] [Academic] arXiv failed: {e}")

        return academic_results

class GapAnalyzerAgent(BaseAgent):
    """Audits accumulated knowledge against research questions to identify missing info."""
    def run(self, questions: List[Dict], fragments: List[str]) -> List[str]:
        print(f"[AGENT] [GapAnalyzer] Auditing research coverage...")
        p = self.prompts.get("gap_analysis", {})
        system_content = p.get("system", "Identify gaps.")
        user_template = p.get("user_template", "Gaps in: {questions}")
        
        context = "\n".join([f"- {f}" for f in fragments[:15]])
        q_list = "\n".join([f"{q['id']}. {q['question']}" for q in questions])
        
        user_content = user_template.format(questions=q_list, context=context)
        
        try:
            response = self.llm.invoke([
                SystemMessage(content=system_content), 
                HumanMessage(content=user_content)
            ])
            match = re.search(r'\[.*\]', response.content, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            return []
        except Exception as e:
            print(f"[ERROR] [GapAnalyzer] Failed: {e}")
            return []

class SectionWriterAgent(BaseAgent):
    """Drafts research sections based on accumulated knowledge fragments."""
    def run(self, question: str, fragments: List[str]) -> str:
        print(f"[AGENT] [Writer] Drafting section for: {question[:50]}...")
        p = self.prompts.get("section_writer", {})
        system_content = p.get("system", "Write a research section.")
        user_template = p.get("user_template", "Question: {question}")
        
        user_content = user_template.format(
            question=question, 
            fragments="\n".join(fragments)
        )
        try:
            messages = [
                SystemMessage(content=system_content), 
                HumanMessage(content=user_content)
            ]
            response = self.llm.invoke(messages)
            return response.content
        except Exception as e:
            return f"Error drafting section: {str(e)}"
