# Script Version: 0.6.8 | Phase 2: Orchestration
# Description: Specialized agents with robust scholarly query cleaning.
# Implementation: Fixed AcademicAgent system prompt usage and cleaned up SearchAgent.

import json
import re
import time
import httpx
import urllib.parse
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from utils import extract_json_from_text

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
            data = extract_json_from_text(response.content)
            
            if isinstance(data, dict) and "questions" in data:
                return data["questions"]
            if isinstance(data, list):
                return data
            
            print(f"[WARNING] [Decompose] Invalid JSON structure. Using fallback.")
            return [{"id": 1, "question": f"General overview of {topic}", "priority": 1}]
                
        except Exception as e:
            print(f"[ERROR] [Decompose] Failed: {str(e)}")
            return [{"id": 1, "question": f"General overview of {topic}", "priority": 1}]

class InitialSearchAgent(BaseAgent):
    """Generates search queries and retrieves candidate URLs using ddgs."""
    def __init__(self, llm: ChatOpenAI, prompts: Dict, source_manager: Any):
        super().__init__(llm, prompts)
        self.source_manager = source_manager

    def run(self, questions: List[Dict]) -> List[Dict]:
        try:
            from ddgs import DDGS
        except ImportError:
            try:
                from duckduckgo_search import DDGS
            except ImportError:
                print("[ERROR] ddgs/duckduckgo_search not installed.")
                return []
            
        print(f"[AGENT] [Search] Generating queries for {len(questions)} questions...")
        
        all_results = []
        p = self.prompts.get("search_query_generation", {})
        user_template = p.get("user_template", "Queries for: {question}")

        with DDGS() as ddgs:
            for q in questions:
                try:
                    user_content = user_template.format(question=q['question'])
                    response = self.llm.invoke([HumanMessage(content=user_content)])
                    content = response.content
                    
                    queries = []
                    
                    # Strategy 1: JSON Extraction
                    try:
                        data = extract_json_from_text(content)
                        if isinstance(data, dict):
                            for key in ["queries", "Queries", '"queries"']:
                                if key in data and isinstance(data[key], list):
                                    queries = data[key]
                                    break
                        elif isinstance(data, list):
                            queries = data
                    except Exception:
                        pass

                    # Strategy 2: Regex Extraction
                    if not queries:
                        matches = re.findall(r'"([^"]+)"', content)
                        if matches:
                            queries = [m for m in matches if m.lower() not in ["queries", "query"]]

                    # Strategy 3: Comma Split
                    if not queries:
                        queries = [item.strip().strip('"').strip("'") for item in content.split(',')]

                    # Validation
                    valid_queries = []
                    for x in queries:
                        if isinstance(x, (str, int, float)):
                            s = str(x).strip()
                            if len(s) > 3:
                                valid_queries.append(s)
                    
                    if not valid_queries:
                        print(f"[WARNING] [Search] No valid queries found for Q{q['id']}")
                        continue

                    for query in valid_queries[:2]:
                        self.source_manager._wait_for_slot()
                        print(f"[AGENT] [Search] Executing query: {query}")
                        
                        results = list(ddgs.text(query, max_results=5))
                        for r in results:
                            if isinstance(r, dict):
                                all_results.append({
                                    "url": r.get('href'),
                                    "title": r.get('title'),
                                    "snippet": r.get('body'),
                                    "question_id": q['id'],
                                    "source_type": "web"
                                })
                            
                except Exception as e:
                    print(f"[ERROR] [Search] Failed query for Q{q['id']}: {type(e).__name__}: {e}")
                
        return all_results

class SourceQualityAgent(BaseAgent):
    """Evaluates the credibility and relevance of candidate sources."""
    def run(self, candidates: List[Dict]) -> Dict[str, Any]:
        print(f"[AGENT] [Quality] Assessing {len(candidates)} candidate sources...")
        scored_sources = []
        total_score = 0.0
        p = self.prompts.get("source_quality_assessment", {})
        user_template = p.get("user_template", "Score: {url}")

        for source in candidates[:15]: 
            try:
                user_content = user_template.format(
                    url=source['url'], 
                    title=source['title'], 
                    snippet=source['snippet']
                )
                response = self.llm.invoke([HumanMessage(content=user_content)])
                data = extract_json_from_text(response.content)
                
                if isinstance(data, list) and len(data) > 0:
                    data = data[0]
                
                if isinstance(data, dict):
                    source.update(data)
                    if 'source_type' not in source:
                        source['source_type'] = 'web'
                    scored_sources.append(source)
                    total_score += float(data.get('score', 0))
                else:
                    pass
                    
            except Exception as e:
                print(f"[ERROR] [Quality] Failed to score {source['url']}: {e}")
        
        avg_score = total_score / len(scored_sources) if scored_sources else 0.0
        return {"sources": scored_sources, "average_score": avg_score}

class AcademicSpecialistAgent(BaseAgent):
    """Queries scholarly APIs (arXiv) using LLM-optimized keywords."""
    def __init__(self, llm: ChatOpenAI, prompts: Dict, source_manager: Any):
        super().__init__(llm, prompts)
        self.source_manager = source_manager
        self.headers = {"User-Agent": "GauntletResearch/1.0 (Educational; Python)"}

    def _get_keywords(self, question: str) -> str:
        """Uses LLM to extract optimized keywords and cleans them for URL safety."""
        p = self.prompts.get("academic_keyword_extraction", {})
        system_content = p.get("system", "You are a Scholarly Librarian.")
        user_template = p.get("user_template", "Question: {question}")
        
        user_content = user_template.format(question=question)
        
        try:
            # FIX: Include SystemMessage so the LLM knows its role and JSON constraints
            messages = [
                SystemMessage(content=system_content),
                HumanMessage(content=user_content)
            ]
            response = self.llm.invoke(messages)
            
            content = response.content
            data = extract_json_from_text(content)
            if isinstance(data, dict) and "keywords" in data:
                content = data["keywords"]
            elif isinstance(data, list):
                content = " ".join(str(x) for x in data)
                
            tokens = re.findall(r'[a-zA-Z0-9]+', str(content))
            
            fillers = {
                'here', 'are', 'keywords', 'for', 'your', 'question', 'the', 'and', 'with', 
                'output', 'example', 'is', 'a', 'of', 'to', 'in', 'on', 'at', 'by', 'from',
                'what', 'how', 'why', 'which', 'that', 'this', 'these', 'those', 'can'
            }
            
            clean_tokens = [t for t in tokens if t.lower() not in fillers]
            return "+".join(clean_tokens[:3]) 
        except Exception as e:
            print(f"[WARNING] [Academic] Keyword extraction failed, using fallback: {e}")
            return "+".join(re.findall(r'\w+', question)[:3])

    def run(self, questions: List[Dict]) -> List[Dict]:
        print(f"[AGENT] [Academic] Searching scholarly databases...")
        academic_results = []
        
        for q in questions[:4]:
            keywords = self._get_keywords(q['question'])
            if not keywords: continue
            
            # Use HTTPS and follow redirects
            arxiv_url = f"https://export.arxiv.org/api/query?search_query=all:{keywords}&start=0&max_results=3"
            print(f"[AGENT] [Academic] Querying arXiv: {arxiv_url}")
            
            try:
                self.source_manager._wait_for_slot()
                with httpx.Client(timeout=20.0, headers=self.headers, follow_redirects=True) as client:
                    resp = client.get(arxiv_url)
                    
                    if resp.status_code == 200:
                        root = ET.fromstring(resp.text)
                        entries = root.findall('{http://www.w3.org/2005/Atom}entry')
                        
                        if not entries and "+" in keywords:
                            broad_keywords = "+".join(keywords.split("+")[:2])
                            print(f"[AGENT] [Academic] No results. Broadening to: {broad_keywords}")
                            arxiv_url = f"https://export.arxiv.org/api/query?search_query=all:{broad_keywords}&start=0&max_results=2"
                            resp = client.get(arxiv_url)
                            if resp.status_code == 200:
                                root = ET.fromstring(resp.text)
                                entries = root.findall('{http://www.w3.org/2005/Atom}entry')

                        for entry in entries:
                            academic_results.append({
                                "url": entry.find('{http://www.w3.org/2005/Atom}id').text,
                                "title": f"[arXiv] {entry.find('{http://www.w3.org/2005/Atom}title').text.strip()}",
                                "snippet": entry.find('{http://www.w3.org/2005/Atom}summary').text.strip()[:500],
                                "question_id": q['id'],
                                "source_type": "academic"
                            })
                    else:
                        print(f"[ERROR] [Academic] arXiv returned status {resp.status_code}")
            except Exception as e:
                print(f"[ERROR] [Academic] arXiv failed for {keywords}: {e}")

        return academic_results

class KnowledgeGraphAgent(BaseAgent):
    """Extracts structured entities and relationships from raw fragments."""
    def run(self, fragments: List[str]) -> List[Dict]:
        print(f"[AGENT] [KnowledgeGraph] Structuring {len(fragments)} fragments...")
        p = self.prompts.get("knowledge_graph_extraction", {})
        system_content = p.get("system", "Extract entities and relationships.")
        user_template = p.get("user_template", "Context: {context}")
        
        context = "\n".join(fragments[:10])
        try:
            response = self.llm.invoke([
                SystemMessage(content=system_content),
                HumanMessage(content=user_template.format(context=context))
            ])
            data = extract_json_from_text(response.content)
            
            if isinstance(data, dict) and "triplets" in data:
                return data["triplets"]
            return data if isinstance(data, list) else []
        except Exception as e:
            print(f"[ERROR] [KnowledgeGraph] Extraction failed: {e}")
            return []

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
            data = extract_json_from_text(response.content)
            
            if isinstance(data, dict) and "gaps" in data:
                return data["gaps"]
            return data if isinstance(data, list) else []
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
            
            try:
                data = json.loads(response.content)
                if isinstance(data, dict) and "section_text" in data:
                    return data["section_text"]
            except:
                pass
                
            return response.content
        except Exception as e:
            return f"Error drafting section: {str(e)}"
