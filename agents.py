# Script Version: 0.2.9 | Phase 1: Agent Foundation (Final)
# Description: Specialized agents for the research workflow.
# Implementation: Includes Semantic Scholar for 2025 academic coverage.

import json
import re
import time
import httpx
import urllib.parse
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

class DecomposeTopicAgent:
    """
    Breaks a broad research topic into specific, prioritized research questions.
    """
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm

    def run(self, topic: str, constraints: Dict = None) -> List[Dict]:
        print(f"[AGENT] [Decompose] Decomposing topic: {topic}")
        
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

            json_block_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if json_block_match:
                return json.loads(json_block_match.group(1))

            json_match = re.search(r'\[\s*\{.*\}\s*\]', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            
            return json.loads(content)
                
        except Exception as e:
            print(f"[ERROR] [Decompose] Failed: {str(e)}")
            return [{"id": 1, "question": f"General overview of {topic}", "priority": 1}]

class InitialSearchAgent:
    """
    Generates search queries and retrieves candidate URLs using DuckDuckGo.
    """
    def __init__(self, llm: ChatOpenAI, source_manager: Any):
        self.llm = llm
        self.source_manager = source_manager

    def run(self, questions: List[Dict]) -> List[Dict]:
        from duckduckgo_search import DDGS
        print(f"[AGENT] [Search] Generating queries for {len(questions)} questions...")
        
        all_results = []
        for q in questions:
            query_prompt = (
                f"Generate 3 diverse, highly specific search queries to answer this research question: "
                f"'{q['question']}'. Focus on finding academic papers and expert reports. "
                "Output as a simple comma-separated list."
            )
            
            try:
                response = self.llm.invoke([HumanMessage(content=query_prompt)])
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

class SourceQualityAgent:
    """
    Evaluates the credibility and relevance of candidate sources.
    """
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm

    def run(self, candidates: List[Dict]) -> List[Dict]:
        print(f"[AGENT] [Quality] Assessing {len(candidates)} candidate sources...")
        scored_sources = []
        for source in candidates[:15]: 
            prompt = (
                "Evaluate the following source for a deep research project. "
                "Assign a quality score from 0.0 to 1.0. "
                "Output ONLY a JSON object with 'score' (float) and 'reason' (string).\n\n"
                f"URL: {source['url']}\nTitle: {source['title']}\nSnippet: {source['snippet']}"
            )
            try:
                response = self.llm.invoke([HumanMessage(content=prompt)])
                match = re.search(r'\{.*\}', response.content, re.DOTALL)
                if match:
                    data = json.loads(match.group(0))
                    source.update(data)
                    if source.get('score', 0) >= 0.5:
                        scored_sources.append(source)
            except Exception as e:
                print(f"[ERROR] [Quality] Failed to score {source['url']}: {e}")
        return scored_sources

class AcademicSpecialistAgent:
    """
    Queries scholarly APIs (arXiv, Semantic Scholar) to find peer-reviewed sources.
    """
    def __init__(self, llm: ChatOpenAI, source_manager: Any):
        self.llm = llm
        self.source_manager = source_manager

    def run(self, questions: List[Dict]) -> List[Dict]:
        print(f"[AGENT] [Academic] Searching scholarly databases...")
        academic_results = []
        
        for q in questions[:3]:
            query = q['question']
            encoded_query = urllib.parse.quote(query)
            
            # 1. arXiv Search
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
                            title = entry.find('{http://www.w3.org/2005/Atom}title').text
                            summary = entry.find('{http://www.w3.org/2005/Atom}summary').text
                            pdf_link = ""
                            for link in entry.findall('{http://www.w3.org/2005/Atom}link'):
                                if link.attrib.get('title') == 'pdf':
                                    pdf_link = link.attrib.get('href')
                            academic_results.append({
                                "url": pdf_link or entry.find('{http://www.w3.org/2005/Atom}id').text,
                                "title": f"[arXiv] {title.strip()}",
                                "snippet": summary.strip()[:500],
                                "question_id": q['id'],
                                "source_type": "academic"
                            })
            except Exception as e:
                print(f"[ERROR] [Academic] arXiv failed: {e}")

            # 2. Semantic Scholar Search (2025 Standard)
            print(f"[AGENT] [Academic] Querying Semantic Scholar for: {query[:50]}...")
            ss_url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={encoded_query}&limit=3&fields=title,abstract,url,openAccessPdf"
            try:
                self.source_manager._wait_for_slot()
                with httpx.Client(timeout=20.0) as client:
                    resp = client.get(ss_url)
                    self.source_manager.last_request_completion_time = time.perf_counter()
                    if resp.status_code == 200:
                        data = resp.json()
                        for paper in data.get('data', []):
                            pdf_info = paper.get('openAccessPdf')
                            academic_results.append({
                                "url": pdf_info.get('url') if pdf_info else paper.get('url'),
                                "title": f"[SemanticScholar] {paper.get('title')}",
                                "snippet": paper.get('abstract', 'No abstract available.')[:500],
                                "question_id": q['id'],
                                "source_type": "academic"
                            })
            except Exception as e:
                print(f"[ERROR] [Academic] Semantic Scholar failed: {e}")

        return academic_results

class SectionWriterAgent:
    """
    Drafts research sections based on accumulated knowledge fragments.
    """
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm

    def run(self, question: str, fragments: List[str]) -> str:
        print(f"[AGENT] [Writer] Drafting section for: {question[:50]}...")
        system_prompt = (
            "You are a Professional Research Synthesizer. Write a detailed, formal research section "
            "based ONLY on the provided knowledge fragments. Use academic tone. "
            "Include inline citations in [Source X] format."
        )
        user_prompt = f"Research Question: {question}\n\nKnowledge Fragments:\n" + "\n".join(fragments)
        try:
            messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
            response = self.llm.invoke(messages)
            return response.content
        except Exception as e:
            return f"Error drafting section: {str(e)}"
