# Script Version: 0.9.0 | Phase 4: Advanced Features
# Description: Added RefineQuestionAgent and dynamic depth support.

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
    def __init__(self, llm: ChatOpenAI, prompts: Dict, settings: Dict = None):
        self.llm = llm
        self.prompts = prompts
        self.settings = settings or {}
        self.params = self.settings.get("parameters", {})

class DecomposeTopicAgent(BaseAgent):
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
            messages = [SystemMessage(content=system_content), HumanMessage(content=user_content)]
            response = self.llm.invoke(messages)
            data = extract_json_from_text(response.content)
            if isinstance(data, dict) and "questions" in data: return data["questions"]
            if isinstance(data, list): return data
            return [{"id": 1, "question": f"General overview of {topic}", "priority": 1}]
        except Exception as e:
            print(f"[ERROR] [Decompose] Failed: {str(e)}")
            return [{"id": 1, "question": f"General overview of {topic}", "priority": 1}]

class RefineQuestionAgent(BaseAgent):
    def run(self, question: str) -> List[str]:
        print(f"[AGENT] [Refine] Generating variations for: {question}")
        p = self.prompts.get("refine_question", {})
        system_content = p.get("system", "You are a Research Supervisor.")
        user_template = p.get("user_template", "Original Question: {question}")
        
        try:
            messages = [SystemMessage(content=system_content), HumanMessage(content=user_template.format(question=question))]
            response = self.llm.invoke(messages)
            data = extract_json_from_text(response.content)
            if isinstance(data, dict) and "options" in data: return data["options"]
            if isinstance(data, list): return data
            return []
        except Exception as e:
            print(f"[ERROR] [Refine] Failed: {e}")
            return []

class InitialSearchAgent(BaseAgent):
    def __init__(self, llm: ChatOpenAI, prompts: Dict, source_manager: Any, settings: Dict = None):
        super().__init__(llm, prompts, settings)
        self.source_manager = source_manager

    def run(self, questions: List[Dict], depth: int = 1) -> List[Dict]:
        try:
            from ddgs import DDGS
        except ImportError:
            try:
                from duckduckgo_search import DDGS
            except ImportError:
                print("[ERROR] ddgs/duckduckgo_search not installed.")
                return []
            
        print(f"[AGENT] [Search] Generating queries for {len(questions)} questions (Depth: {depth})...")
        all_results = []
        p = self.prompts.get("search_query_generation", {})
        user_template = p.get("user_template", "Queries for: {question}")
        
        queries_per_q = self.params.get("search_queries_per_question", 3)
        results_per_q = self.params.get("search_results_per_query", 5)
        
        with DDGS() as ddgs:
            for q in questions:
                try:
                    # 1. Generate Initial Queries
                    user_content = user_template.format(question=q['question'])
                    response = self.llm.invoke([HumanMessage(content=user_content)])
                    queries = self._extract_queries(response.content)
                    
                    valid_queries = [s for s in queries if len(str(s).strip()) > 3][:queries_per_q]

                    for query in valid_queries:
                        self.source_manager._wait_for_slot()
                        print(f"[AGENT] [Search] Executing query (Depth 1): {query}")
                        
                        results = list(ddgs.text(query, max_results=results_per_q))
                        for r in results:
                            if isinstance(r, dict):
                                all_results.append(self._fmt_result(r, q['id']))

                        # 2. Recursive Depth (if enabled)
                        if depth > 1 and results:
                            top_result = results[0]
                            print(f"[AGENT] [Search] Recursion (Depth 2) on: {top_result.get('title')}")
                            
                            # Generate follow-up query based on top result
                            follow_up_query = f"{query} related to {top_result.get('title')}"
                            self.source_manager._wait_for_slot()
                            
                            sub_results = list(ddgs.text(follow_up_query, max_results=2))
                            for sub in sub_results:
                                all_results.append(self._fmt_result(sub, q['id']))
                                
                            if depth > 2 and sub_results:
                                # Depth 3 (Max)
                                sub_top = sub_results[0]
                                deep_query = f"{follow_up_query} {sub_top.get('title')}"
                                self.source_manager._wait_for_slot()
                                deep_results = list(ddgs.text(deep_query, max_results=1))
                                for d in deep_results:
                                    all_results.append(self._fmt_result(d, q['id']))

                except Exception as e:
                    print(f"[ERROR] [Search] Failed query for Q{q['id']}: {e}")
                
        return all_results

    def _extract_queries(self, content):
        queries = []
        try:
            data = extract_json_from_text(content)
            if isinstance(data, dict):
                for key in ["queries", "Queries", '"queries"']:
                    if key in data and isinstance(data[key], list):
                        queries = data[key]
                        break
            elif isinstance(data, list):
                queries = data
        except: pass
        
        if not queries:
            matches = re.findall(r'"([^"]+)"', content)
            if matches: queries = [m for m in matches if m.lower() not in ["queries", "query"]]
        if not queries:
            queries = [item.strip().strip('"').strip("'") for item in content.split(',')]
        return queries

    def _fmt_result(self, r, qid):
        return {
            "url": r.get('href'),
            "title": r.get('title'),
            "snippet": r.get('body'),
            "question_id": qid,
            "source_type": "web"
        }

class SourceQualityAgent(BaseAgent):
    def run(self, candidates: List[Dict]) -> Dict[str, Any]:
        print(f"[AGENT] [Quality] Assessing {len(candidates)} candidate sources...")
        scored_sources = []
        total_score = 0.0
        p = self.prompts.get("source_quality_assessment", {})
        user_template = p.get("user_template", "Score: {url}")
        
        max_assess = 20 
        for source in candidates[:max_assess]: 
            try:
                user_content = user_template.format(url=source['url'], title=source['title'], snippet=source['snippet'])
                response = self.llm.invoke([HumanMessage(content=user_content)])
                data = extract_json_from_text(response.content)
                if isinstance(data, list) and len(data) > 0: data = data[0]
                
                if isinstance(data, dict):
                    source.update(data)
                    if 'source_type' not in source: source['source_type'] = 'web'
                    scored_sources.append(source)
                    total_score += float(data.get('score', 0))
            except Exception as e:
                print(f"[ERROR] [Quality] Failed to score {source['url']}: {e}")
        
        avg_score = total_score / len(scored_sources) if scored_sources else 0.0
        return {"sources": scored_sources, "average_score": avg_score}

class AcademicSpecialistAgent(BaseAgent):
    def __init__(self, llm: ChatOpenAI, prompts: Dict, source_manager: Any, settings: Dict = None):
        super().__init__(llm, prompts, settings)
        self.source_manager = source_manager
        self.headers = {"User-Agent": "GauntletResearch/1.0 (Educational; Python)"}

    def _get_keywords(self, question: str) -> str:
        p = self.prompts.get("academic_keyword_extraction", {})
        system_content = p.get("system", "You are a Scholarly Librarian.")
        user_template = p.get("user_template", "Question: {question}")
        user_content = user_template.format(question=question)
        try:
            messages = [SystemMessage(content=system_content), HumanMessage(content=user_content)]
            response = self.llm.invoke(messages)
            content = response.content
            data = extract_json_from_text(content)
            if isinstance(data, dict) and "keywords" in data: content = data["keywords"]
            elif isinstance(data, list): content = " ".join(str(x) for x in data)
            tokens = re.findall(r'[a-zA-Z0-9]+', str(content))
            fillers = {'here', 'are', 'keywords', 'for', 'your', 'question', 'the', 'and', 'with', 'output'}
            clean_tokens = [t for t in tokens if t.lower() not in fillers]
            return "+".join(clean_tokens[:3]) 
        except Exception as e:
            print(f"[WARNING] [Academic] Keyword extraction failed: {e}")
            return "+".join(re.findall(r'\w+', question)[:3])

    def run(self, questions: List[Dict], depth: int = 1) -> List[Dict]:
        print(f"[AGENT] [Academic] Searching scholarly databases (Depth: {depth})...")
        academic_results = []
        max_results = self.params.get("academic_papers_per_query", 3)
        
        for q in questions[:4]:
            keywords = self._get_keywords(q['question'])
            if not keywords: continue
            
            arxiv_url = f"https://export.arxiv.org/api/query?search_query=all:{keywords}&start=0&max_results={max_results}"
            print(f"[AGENT] [Academic] Querying arXiv: {arxiv_url}")
            
            try:
                self.source_manager._wait_for_slot()
                with httpx.Client(timeout=20.0, headers=self.headers, follow_redirects=True) as client:
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
                        
                        # Recursive Depth for Academic (Simulated by broadening terms)
                        if depth > 1 and not entries:
                            # If no results, broaden automatically
                            broad_keywords = "+".join(keywords.split("+")[:2])
                            print(f"[AGENT] [Academic] Recursion (Depth 2): Broadening to {broad_keywords}")
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

            except Exception as e:
                print(f"[ERROR] [Academic] arXiv failed for {keywords}: {e}")

        return academic_results

class KnowledgeGraphAgent(BaseAgent):
    def run(self, fragments: List[str]) -> List[Dict]:
        print(f"[AGENT] [KnowledgeGraph] Structuring {len(fragments)} fragments...")
        p = self.prompts.get("knowledge_graph_extraction", {})
        system_content = p.get("system", "Extract entities.")
        user_template = p.get("user_template", "Context: {context}")
        context = "\n".join(fragments[:10])
        try:
            response = self.llm.invoke([SystemMessage(content=system_content), HumanMessage(content=user_template.format(context=context))])
            data = extract_json_from_text(response.content)
            if isinstance(data, dict) and "triplets" in data: return data["triplets"]
            return data if isinstance(data, list) else []
        except Exception as e:
            print(f"[ERROR] [KnowledgeGraph] Extraction failed: {e}")
            return []

class GapAnalyzerAgent(BaseAgent):
    def run(self, questions: List[Dict], fragments: List[str]) -> List[str]:
        print(f"[AGENT] [GapAnalyzer] Auditing research coverage...")
        p = self.prompts.get("gap_analysis", {})
        system_content = p.get("system", "Identify gaps.")
        user_template = p.get("user_template", "Gaps in: {questions}")
        context = "\n".join([f"- {f}" for f in fragments[:15]])
        q_list = "\n".join([f"{q['id']}. {q['question']}" for q in questions])
        try:
            response = self.llm.invoke([SystemMessage(content=system_content), HumanMessage(content=user_template.format(questions=q_list, context=context))])
            data = extract_json_from_text(response.content)
            if isinstance(data, dict) and "gaps" in data: return data["gaps"]
            return data if isinstance(data, list) else []
        except Exception as e:
            print(f"[ERROR] [GapAnalyzer] Failed: {e}")
            return []

class SectionWriterAgent(BaseAgent):
    def run(self, question: str, fragments: List[str]) -> str:
        print(f"[AGENT] [Writer] Drafting section for: {question[:50]}...")
        p = self.prompts.get("section_writer", {})
        system_content = p.get("system", "Write a research section.")
        user_template = p.get("user_template", "Question: {question}")
        user_content = user_template.format(question=question, fragments="\n".join(fragments))
        try:
            messages = [SystemMessage(content=system_content), HumanMessage(content=user_content)]
            response = self.llm.invoke(messages)
            try:
                data = json.loads(response.content)
                if isinstance(data, dict) and "section_text" in data: return data["section_text"]
            except: pass
            return response.content
        except Exception as e:
            return f"Error drafting section: {str(e)}"
