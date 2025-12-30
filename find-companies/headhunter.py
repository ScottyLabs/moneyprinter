import os
import time
import json
import requests
import pandas as pd
from datetime import datetime
from exa_py import Exa
from openai import OpenAI
from urllib.parse import urlparse
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()

EXA_API_KEY = os.getenv("EXA_API_KEY", "YOUR_EXA_KEY")
APOLLO_API_KEY = os.getenv("APOLLO_API_KEY", "YOUR_APOLLO_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "YOUR_OPENROUTER_KEY")

# Titles we want to email
TARGET_TITLES = [
    "Developer Relations", "DevRel", "University Recruiter", 
    "Campus Recruiter", "Head of Engineering", "Founder", "CTO",
    "Developer Advocate", "Partnerships", "Sponsorships"
]

# --- EXA TOOLS (callable by the LLM) ---

def search_similar_companies(seed_url: str, num_results: int = 15) -> list[dict]:
    """
    Uses Exa's Neural Search to find companies similar to a seed URL.
    Returns a list of company domains with their titles and descriptions.
    """
    print(f"\n🤖 [Exa Tool] Searching for companies similar to {seed_url}...")
    
    exa = Exa(EXA_API_KEY)
    
    response = exa.find_similar(
        url=seed_url,
        num_results=num_results,
        exclude_source_domain=True,
        category="company"
    )
    
    companies = []
    for result in response.results:
        domain = urlparse(result.url).netloc.replace("www.", "")
        companies.append({
            "domain": domain,
            "title": result.title,
            "url": result.url
        })
        print(f"   Found: {domain} - {result.title}")
    
    return companies


def search_companies_by_query(query: str, num_results: int = 15) -> list[dict]:
    """
    Uses Exa's Neural Search to find companies matching a text query.
    Returns a list of company domains with their titles and descriptions.
    """
    print(f"\n🤖 [Exa Tool] Searching for: {query}...")
    
    exa = Exa(EXA_API_KEY)
    
    response = exa.search(
        query=query,
        num_results=num_results,
        type="neural",
        category="company",
    )
    
    companies = []
    for result in response.results:
        domain = urlparse(result.url).netloc.replace("www.", "")
        companies.append({
            "domain": domain,
            "title": result.title,
            "url": result.url
        })
        print(f"   Found: {domain} - {result.title}")
    
    return companies


# --- TOOL DEFINITIONS FOR OPENAI ---

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_similar_companies",
            "description": "Find companies similar to a given company URL. Use this when the user mentions a specific company they want to find similar ones to, or when looking for companies in a similar space/vibe as a known company.",
            "parameters": {
                "type": "object",
                "properties": {
                    "seed_url": {
                        "type": "string",
                        "description": "The URL of the company to find similar companies to (e.g., 'https://vercel.com')"
                    },
                    "num_results": {
                        "type": "integer",
                        "description": "Number of similar companies to find (default: 15)",
                        "default": 15
                    }
                },
                "required": ["seed_url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_companies_by_query",
            "description": "Search for companies matching a text description. Use this when the user describes what kind of companies they're looking for (e.g., 'developer tools startups', 'companies that sponsor hackathons', 'API-first companies').",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A text description of the type of companies to find"
                    },
                    "num_results": {
                        "type": "integer",
                        "description": "Number of companies to find (default: 15)",
                        "default": 15
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "evaluate_companies",
            "description": "Evaluate a list of discovered companies to filter out unknown ones and provide rationale for good matches. Call this AFTER you have searched for companies. The tool will return which companies are good fits (with rationale) and which were rejected (with reasons). Use the rejection feedback to refine your search strategy if needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "companies": {
                        "type": "array",
                        "description": "Array of company objects to evaluate. Each should have 'domain', 'title', and 'url' fields.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "domain": {"type": "string"},
                                "title": {"type": "string"},
                                "url": {"type": "string"}
                            }
                        }
                    }
                },
                "required": ["companies"]
            }
        }
    }
]

SYSTEM_PROMPT = """You are a helpful assistant that finds potential sponsor companies for hackathons and tech events.

You have access to these tools:
1. search_similar_companies: Find companies similar to a known company URL
2. search_companies_by_query: Search for companies by text description
3. evaluate_companies: Evaluate discovered companies to filter out bad matches and get rationale for good ones

YOUR WORKFLOW:
1. Analyze the user's request to understand what kind of companies they're looking for
2. Use search tools to find potential companies (you can make multiple searches)
3. IMPORTANT: Call evaluate_companies with ALL the companies you've found so far
4. Review the evaluation feedback - if many companies were rejected, consider doing additional targeted searches
5. You may call evaluate_companies multiple times as you refine your search
6. When you're satisfied with the results, summarize what you found

The evaluate_companies tool will:
- Filter out companies the evaluator doesn't recognize
- Filter out hackathon platforms and other hackathons (we want sponsors, not platforms)
- Provide rationale and confidence for each good match
- Give you feedback on why companies were rejected (use this to improve your search!)

Think strategically about good search queries. For hackathon sponsors, consider:
- Developer tools and API companies (they often give credits)
- Cloud infrastructure providers (AWS, GCP, DigitalOcean, etc.)
- DevOps and monitoring tools
- Companies known for university/developer programs

Always aim for QUALITY over quantity - it's better to have 10 well-vetted companies than 50 unknown ones."""


def execute_tool_call(tool_name: str, arguments: dict, user_prompt: str = "") -> dict | list[dict]:
    """Execute a tool call and return results."""
    if tool_name == "search_similar_companies":
        return search_similar_companies(
            seed_url=arguments["seed_url"],
            num_results=arguments.get("num_results", 15)
        )
    elif tool_name == "search_companies_by_query":
        return search_companies_by_query(
            query=arguments["query"],
            num_results=arguments.get("num_results", 15)
        )
    elif tool_name == "evaluate_companies":
        return evaluate_companies_tool(
            user_prompt=user_prompt,
            companies=arguments["companies"]
        )
    else:
        return []


def run_agent(user_prompt: str) -> list[dict]:
    """
    Run the LLM agent with the user's prompt.
    Returns a list of evaluated companies (with rationale).
    """
    client = OpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1"
    )
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]
    
    all_companies = []  # Raw discovered companies
    evaluated_companies = []  # Companies that passed evaluation
    
    print("\n" + "="*60)
    print("🧠 Agent is thinking...")
    print("="*60)
    
    while True:
        response = client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto"
        )
        
        message = response.choices[0].message
        
        # If the agent wants to use tools
        if message.tool_calls:
            messages.append(message)
            
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)
                
                print(f"\n📞 Agent calling: {tool_name}")
                if tool_name != "evaluate_companies":
                    print(f"   Arguments: {json.dumps(arguments, indent=2)}")
                else:
                    print(f"   Evaluating {len(arguments.get('companies', []))} companies...")
                
                results = execute_tool_call(tool_name, arguments, user_prompt)
                
                # Track results based on tool type
                if tool_name == "evaluate_companies":
                    # Store the approved companies
                    if isinstance(results, dict) and "approved" in results:
                        evaluated_companies.extend(results["approved"])
                else:
                    # Search tools return list of companies
                    if isinstance(results, list):
                        all_companies.extend(results)
                
                # Add tool result to conversation
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(results) if isinstance(results, (dict, list)) else str(results)
                })
        else:
            # Agent is done, print final message
            if message.content:
                print("\n" + "="*60)
                print("🤖 Agent Summary:")
                print("="*60)
                print(message.content)
            break
    
    # Deduplicate evaluated companies by domain
    seen = set()
    unique_evaluated = []
    for company in evaluated_companies:
        domain = company.get("domain", "")
        if domain and domain not in seen:
            seen.add(domain)
            unique_evaluated.append(company)
    
    return unique_evaluated


def evaluate_companies_tool(user_prompt: str, companies: list[dict]) -> dict:
    """
    Tool version of evaluate_companies that returns structured feedback
    including rejected companies with reasons.
    """
    print("\n" + "="*60)
    print("🔍 Evaluating companies...")
    print("="*60)
    
    if not companies:
        return {
            "approved": [],
            "rejected": [],
            "feedback": "No companies to evaluate."
        }
    
    client = OpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1"
    )
    
    # Build the company list for evaluation
    company_list = "\n".join([
        f"- {c.get('domain', 'unknown')}: {c.get('title', 'Unknown')} ({c.get('url', '')})"
        for c in companies
    ])
    
    eval_prompt = f"""The user is looking for: {user_prompt}

Here is a list of companies that were found:
{company_list}

For each company, evaluate whether it's a good fit for the user's request.

IMPORTANT RULES:
1. EXCLUDE any company you don't recognize or haven't heard of
2. EXCLUDE hackathon websites/platforms (like devpost, hackathon.io, mlh.io)
3. EXCLUDE other hackathons (like VTHacks, HackPSU, etc.)
4. For each company you KEEP, provide a short rationale

Respond with a JSON object with two arrays:
{{
  "approved": [
    {{
      "domain": "example.com",
      "title": "Example Company",
      "url": "https://example.com",
      "rationale": "Why this company is a good fit (1-2 sentences)",
      "confidence": "high" | "medium" | "low"
    }}
  ],
  "rejected": [
    {{
      "domain": "bad.com",
      "reason": "Why this was rejected (e.g., 'Unknown company', 'This is a hackathon platform', 'This is another hackathon')"
    }}
  ]
}}

Respond with ONLY the JSON object, no other text."""

    response = client.chat.completions.create(
        model="google/gemini-2.0-flash-001",
        messages=[
            {"role": "user", "content": eval_prompt}
        ],
        max_tokens=4000
    )
    
    response_text = response.choices[0].message.content.strip()
    
    try:
        # Handle markdown code blocks if present
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        
        result = json.loads(response_text)
        approved = result.get("approved", [])
        rejected = result.get("rejected", [])
        
        print(f"\n✅ Approved {len(approved)} companies:")
        for company in approved:
            confidence_emoji = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(company.get("confidence", "medium"), "⚪")
            print(f"   {confidence_emoji} {company.get('domain', 'unknown')}: {company.get('rationale', 'No rationale')[:50]}...")
        
        if rejected:
            print(f"\n❌ Rejected {len(rejected)} companies:")
            # Group rejections by reason
            rejection_reasons = {}
            for r in rejected:
                reason = r.get("reason", "Unknown reason")
                if reason not in rejection_reasons:
                    rejection_reasons[reason] = []
                rejection_reasons[reason].append(r.get("domain", "unknown"))
            
            for reason, domains in rejection_reasons.items():
                print(f"   • {reason}: {', '.join(domains[:3])}{'...' if len(domains) > 3 else ''}")
        
        # Add feedback summary for the agent
        feedback = f"Approved {len(approved)} companies, rejected {len(rejected)}."
        if rejected:
            # Summarize rejection patterns
            unknown_count = sum(1 for r in rejected if "unknown" in r.get("reason", "").lower() or "recognize" in r.get("reason", "").lower())
            platform_count = sum(1 for r in rejected if "platform" in r.get("reason", "").lower() or "hackathon" in r.get("reason", "").lower())
            if unknown_count > 0:
                feedback += f" {unknown_count} were unknown companies - try searching for more well-known companies."
            if platform_count > 0:
                feedback += f" {platform_count} were hackathon platforms/events - we want sponsors, not platforms."
        
        return {
            "approved": approved,
            "rejected": rejected,
            "feedback": feedback
        }
        
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing evaluation response: {e}")
        return {
            "approved": [],
            "rejected": [],
            "feedback": f"Error evaluating companies: {e}"
        }


def evaluate_companies(user_prompt: str, companies: list[dict]) -> list[dict]:
    """
    Use the LLM to evaluate each company, filtering out unknown ones
    and providing a rationale for why each remaining company is a good fit.
    """
    print("\n" + "="*60)
    print("🔍 Evaluating companies...")
    print("="*60)
    
    client = OpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1"
    )
    
    # Build the company list for evaluation
    company_list = "\n".join([
        f"- {c['domain']}: {c['title']} ({c['url']})"
        for c in companies
    ])
    
    eval_prompt = f"""The user is looking for: {user_prompt}

Here is a list of companies that were found:
{company_list}

For each company, evaluate whether it's a good fit for the user's request.

IMPORTANT RULES:
1. EXCLUDE any company you don't recognize or haven't heard of - only include companies you have actual knowledge about
2. EXCLUDE hackathon websites/platforms (like devpost, hackathon.io, mlh.io) - we want sponsors, not hackathon platforms
3. EXCLUDE other hackathons (like VTHacks, HackPSU, etc.)
4. For each company you KEEP, provide a short rationale (1-2 sentences) explaining why they're a good fit

Respond with a JSON array of objects, each with these fields:
- "domain": the company domain
- "title": the company name
- "url": the company URL
- "rationale": why this company is a good fit (1-2 sentences)
- "confidence": "high", "medium", or "low" based on how confident you are they'd be interested

Only include companies you genuinely recognize and believe would be good sponsorship targets.
Respond with ONLY the JSON array, no other text."""

    response = client.chat.completions.create(
        model="google/gemini-2.0-flash-001",
        messages=[
            {"role": "user", "content": eval_prompt}
        ],
        max_tokens=4000
    )
    
    response_text = response.choices[0].message.content.strip()
    
    # Parse the JSON response
    try:
        # Handle markdown code blocks if present
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        
        evaluated = json.loads(response_text)
        
        print(f"\n✅ Kept {len(evaluated)} companies after evaluation")
        for company in evaluated:
            confidence_emoji = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(company.get("confidence", "medium"), "⚪")
            print(f"   {confidence_emoji} {company['domain']}: {company.get('rationale', 'No rationale')[:60]}...")
        
        return evaluated
        
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing LLM response: {e}")
        print("Raw response:", response_text[:500])
        # Fall back to original list without rationale
        return companies


def generate_filename(user_prompt: str) -> str:
    """
    Use the LLM to generate a short filename summary of the user's prompt.
    Returns a sanitized filename string.
    """
    client = OpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1"
    )
    
    response = client.chat.completions.create(
        model="openai/gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Generate a very short (3-5 words max) filename-safe summary of the user's search query. Use lowercase with underscores. No file extension. Example: 'developer_tools_startups' or 'cloud_api_companies'. Respond with ONLY the filename, nothing else."},
            {"role": "user", "content": user_prompt}
        ],
        max_tokens=50
    )
    
    filename = response.choices[0].message.content.strip()
    # Sanitize: remove any characters that aren't alphanumeric or underscore
    filename = ''.join(c if c.isalnum() or c == '_' else '_' for c in filename)
    return filename


def save_search_results(user_prompt: str, companies: list[dict], filename: str, conversation: list[dict] = None, filepath: str = None) -> str:
    """
    Save search results to a JSON file.
    Returns the filepath of the saved file.
    
    If filepath is provided, updates that file instead of creating a new one.
    conversation is a list of {"role": "user"/"assistant", "content": ...} messages.
    """
    # Ensure searches directory exists
    searches_dir = os.path.join(os.path.dirname(__file__), "searches")
    os.makedirs(searches_dir, exist_ok=True)
    
    if filepath is None:
        # Create timestamped filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        full_filename = f"{timestamp}_{filename}.json"
        filepath = os.path.join(searches_dir, full_filename)
    
    # Build the data to save
    data = {
        "initial_prompt": user_prompt,
        "timestamp": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
        "company_count": len(companies),
        "companies": companies,
        "conversation": conversation or [{"role": "user", "content": user_prompt}]
    }
    
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\n💾 Saved to: {filepath}")
    return filepath


def refine_with_chat(companies: list[dict], user_prompt: str, conversation: list[dict], filepath: str) -> list[dict]:
    """
    Allow user to refine the company list through natural language chat.
    Returns the refined list of companies.
    """
    client = OpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1"
    )
    
    print("\n" + "="*60)
    print("💬 REFINEMENT MODE")
    print("="*60)
    print("Describe changes you want to make to the list.")
    print("Examples: 'remove companies I haven't heard of', 'only keep cloud providers',")
    print("          'add more AI companies', 'remove #3 and #7'")
    print("Type 'done' when finished, 'show' to see current list.")
    print("-" * 60)
    
    while True:
        user_input = input("\n💭 You: ").strip()
        
        if not user_input:
            continue
        
        if user_input.lower() == 'done':
            print("Exiting refinement mode.")
            break
        
        if user_input.lower() == 'show':
            display_companies(companies)
            continue
        
        # Build the company list for the LLM
        company_list = "\n".join([
            f"{i+1}. {c.get('domain', 'unknown')}: {c.get('title', 'Unknown')} - {c.get('rationale', 'No rationale')[:50]}"
            for i, c in enumerate(companies)
        ])
        
        refine_prompt = f"""You are helping refine a list of potential hackathon sponsor companies.

Original search: {user_prompt}

Current company list:
{company_list}

User's modification request: {user_input}

Apply the user's requested changes to the list. Return a JSON object with:
{{
  "companies": [... the modified list, each with domain, title, url, rationale, confidence ...],
  "changes_made": "Brief description of what you changed",
  "should_search_more": true/false (if user asked to add more companies)
}}

IMPORTANT:
- If user asks to remove companies, remove them from the list
- If user asks to keep only certain types, filter accordingly
- If user asks to add more, set should_search_more to true
- Preserve the original rationale/confidence for companies you keep
- Return ONLY the JSON, no other text."""

        response = client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[{"role": "user", "content": refine_prompt}],
            max_tokens=4000
        )
        
        response_text = response.choices[0].message.content.strip()
        
        try:
            # Handle markdown code blocks
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
            
            result = json.loads(response_text)
            new_companies = result.get("companies", companies)
            changes = result.get("changes_made", "No changes")
            should_search = result.get("should_search_more", False)
            
            # Update companies
            companies = new_companies
            
            # Add to conversation
            conversation.append({"role": "user", "content": user_input})
            conversation.append({"role": "assistant", "content": changes})
            
            print(f"🤖 Assistant: {changes}")
            print(f"   Current list: {len(companies)} companies")
            
            # Save updated results
            save_search_results(user_prompt, companies, "", conversation, filepath)
            
            if should_search:
                print("   (You can search for more companies by typing 'done' and starting a new search)")
        
        except json.JSONDecodeError as e:
            print(f"❌ Error processing request: {e}")
            print("Please try rephrasing your request.")
    
    return companies


# --- CONTACT ENRICHMENT (Exa-based LinkedIn search) ---

def find_linkedin_contacts(company_name: str, domain: str) -> list[dict]:
    """
    Uses Exa to search for LinkedIn profiles of relevant contacts at a company.
    Targets DevRel, recruiters, and C-suite.
    """
    print(f"🔎 Searching LinkedIn for contacts at {company_name}...")
    
    exa = Exa(EXA_API_KEY)
    
    # Search queries targeting different roles
    role_queries = [
        f"{company_name} Developer Relations DevRel",
        f"{company_name} Developer Advocate",
        f"{company_name} University Recruiter Campus Recruiter",
        f"{company_name} CTO CEO Founder",
        f"{company_name} Partnerships Sponsorships",
    ]
    
    all_contacts = []
    seen_urls = set()
    
    for query in role_queries:
        try:
            response = exa.search(
                query=query,
                num_results=3,
                type="neural",
                category="people"
            )
            
            for result in response.results:
                print(result)
                # Only keep LinkedIn profile URLs
                if "linkedin.com/in/" in result.url and result.url not in seen_urls:
                    seen_urls.add(result.url)
                    
                    # Try to extract name and title from the result title
                    title_parts = result.title.split(" - ") if result.title else ["Unknown"]
                    name = title_parts[0].strip() if title_parts else "Unknown"
                    role = title_parts[1].strip() if len(title_parts) > 1 else "Unknown Role"
                    
                    all_contacts.append({
                        "Company": company_name,
                        "Domain": domain,
                        "Name": name,
                        "Title": role,
                        "LinkedIn": result.url,
                        "Email": ""  # Not available from LinkedIn search
                    })
        except Exception as e:
            print(f"   ⚠️ Search error: {e}")
            continue
        
        time.sleep(0.5)  # Rate limit between queries
    
    return all_contacts


def display_companies(companies: list[dict]) -> None:
    """Display the list of companies for approval."""
    print("\n" + "="*60)
    print("📋 DISCOVERED COMPANIES")
    print("="*60)
    
    for i, company in enumerate(companies, 1):
        confidence = company.get('confidence', '')
        confidence_emoji = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(confidence, "")
        
        print(f"\n{i}. {confidence_emoji} {company['domain']}")
        print(f"   {company['title']}")
        print(f"   {company['url']}")
        if company.get('rationale'):
            print(f"   💡 {company['rationale']}")
    
    print("\n" + "="*60)
    print(f"Total: {len(companies)} companies")
    print("="*60)


def get_user_approval(companies: list[dict]) -> list[dict]:
    """
    Get user approval for the company list.
    Returns the approved list of companies.
    """
    while True:
        print("\nOptions:")
        print("  [y] Approve all and proceed to find emails")
        print("  [n] Cancel and exit")
        print("  [e] Edit list (remove specific companies)")
        print("  [r] Re-run with a new prompt")
        
        choice = input("\nYour choice: ").strip().lower()
        
        if choice == 'y':
            return companies
        elif choice == 'n':
            print("Cancelled.")
            return []
        elif choice == 'e':
            print("\nEnter company numbers to REMOVE (comma-separated), or 'done' to finish:")
            while True:
                edit_input = input("> ").strip()
                if edit_input.lower() == 'done':
                    break
                try:
                    indices = [int(x.strip()) - 1 for x in edit_input.split(",")]
                    companies = [c for i, c in enumerate(companies) if i not in indices]
                    display_companies(companies)
                except ValueError:
                    print("Invalid input. Enter numbers separated by commas.")
            return companies
        elif choice == 'r':
            return None  # Signal to re-run
        else:
            print("Invalid choice. Please enter y, n, e, or r.")


def list_saved_searches() -> list[dict]:
    """
    List all saved search files with their metadata.
    Returns a list of dicts with filepath, filename, prompt, company_count, timestamp.
    """
    searches_dir = os.path.join(os.path.dirname(__file__), "searches")
    if not os.path.exists(searches_dir):
        return []
    
    searches = []
    for filename in sorted(os.listdir(searches_dir), reverse=True):  # Most recent first
        if filename.endswith('.json'):
            filepath = os.path.join(searches_dir, filename)
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                searches.append({
                    "filepath": filepath,
                    "filename": filename,
                    "prompt": data.get("initial_prompt", "Unknown")[:60],
                    "company_count": data.get("company_count", 0),
                    "timestamp": data.get("last_updated", data.get("timestamp", "Unknown"))
                })
            except (json.JSONDecodeError, IOError):
                continue
    
    return searches


def load_search(filepath: str) -> tuple[str, list[dict], list[dict], str]:
    """
    Load a saved search file.
    Returns (initial_prompt, companies, conversation, filepath).
    """
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    return (
        data.get("initial_prompt", ""),
        data.get("companies", []),
        data.get("conversation", []),
        filepath
    )


def browse_searches() -> tuple[str, list[dict], list[dict], str] | None:
    """
    Interactive browser for saved searches.
    Returns (prompt, companies, conversation, filepath) if user selects one, else None.
    """
    searches = list_saved_searches()
    
    if not searches:
        print("\n📂 No saved searches found.")
        return None
    
    print("\n" + "="*60)
    print("📂 SAVED SEARCHES")
    print("="*60)
    
    for i, search in enumerate(searches, 1):
        timestamp = search['timestamp'][:16] if len(search['timestamp']) > 16 else search['timestamp']
        print(f"\n{i}. [{timestamp}] {search['company_count']} companies")
        print(f"   {search['prompt']}...")
    
    print("\n" + "-"*60)
    print("Enter a number to resume, or 'back' to return to menu.")
    
    while True:
        choice = input("\n> ").strip().lower()
        
        if choice == 'back' or choice == 'b':
            return None
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(searches):
                return load_search(searches[idx]["filepath"])
            else:
                print(f"Please enter a number between 1 and {len(searches)}.")
        except ValueError:
            print("Invalid input. Enter a number or 'back'.")


def main():
    print("\n" + "="*60)
    print("💰 MONEYPRINTER - Hackathon Sponsor Finder")
    print("="*60)
    print("\nThis tool helps you find potential sponsors for your hackathon.")
    print("The AI agent will search for companies, evaluate them, and then")
    print("you can refine the list through natural language chat.\n")
    
    while True:
        # Startup menu
        print("="*60)
        print("MAIN MENU")
        print("="*60)
        print("\n  [n] New search")
        print("  [b] Browse saved searches")
        print("  [q] Quit")
        
        menu_choice = input("\nYour choice: ").strip().lower()
        
        if menu_choice == 'q' or menu_choice == 'quit':
            print("\nGoodbye! 👋")
            break
        
        if menu_choice == 'b':
            result = browse_searches()
            if result is None:
                continue
            
            user_prompt, companies, conversation, filepath = result
            print(f"\n📂 Loaded: {len(companies)} companies")
            print(f"   Original prompt: {user_prompt[:60]}...")
            display_companies(companies)
            
            # Go straight to refinement
            print("\nOptions:")
            print("  [c] Chat to refine the list")
            print("  [y] Proceed to find emails")
            print("  [n] Back to menu")
            
            choice = input("\nYour choice: ").strip().lower()
            
            if choice == 'c':
                companies = refine_with_chat(companies, user_prompt, conversation, filepath)
                display_companies(companies)
                proceed = input("\nProceed to find emails? (y/n): ").strip().lower()
                if proceed != 'y':
                    continue
            elif choice == 'n' or choice != 'y':
                continue
            
            # Proceed to Apollo enrichment (same code as new search)
            _run_contact_enrichment(companies)
            continue
        
        if menu_choice != 'n' and menu_choice != 'new':
            print("Invalid choice.")
            continue
        
        # NEW SEARCH FLOW
        print("\n" + "-" * 60)
        user_prompt = input("🎯 What companies are you looking for?\n> ").strip()
        
        if not user_prompt:
            print("Please enter a prompt.")
            continue
        
        if user_prompt.lower() in ['quit', 'exit', 'q']:
            print("Goodbye!")
            break
        
        # Run the LLM agent (now includes evaluation as a tool)
        companies = run_agent(user_prompt)
        
        if not companies:
            print("\n❌ No companies found or none passed evaluation. Try a different prompt.")
            continue
        
        # Display results
        display_companies(companies)
        
        # Save initial search results
        print("\n📝 Generating filename for search results...")
        filename = generate_filename(user_prompt)
        conversation = [{"role": "user", "content": user_prompt}]
        filepath = save_search_results(user_prompt, companies, filename, conversation)
        
        # Refinement options
        print("\nOptions:")
        print("  [c] Chat to refine the list")
        print("  [y] Approve and proceed to find emails")
        print("  [n] Cancel and start over")
        
        choice = input("\nYour choice: ").strip().lower()
        
        if choice == 'c':
            companies = refine_with_chat(companies, user_prompt, conversation, filepath)
            display_companies(companies)
            
            proceed = input("\nProceed to find emails? (y/n): ").strip().lower()
            if proceed != 'y':
                print("Saved. Returning to menu.")
                continue
        elif choice == 'n':
            print("Cancelled.")
            continue
        elif choice != 'y':
            print("Invalid choice, returning to menu.")
            continue
        
        _run_contact_enrichment(companies)


def _run_contact_enrichment(companies: list[dict]):
    """Find LinkedIn contacts for a list of companies using Exa search."""
    print("\n" + "="*60)
    print("📎 ENRICHMENT PHASE - Finding LinkedIn contacts...")
    print("="*60)
    print("Searching for DevRel, Recruiters, and C-Suite on LinkedIn...\n")
    
    all_contacts = []
    for company in companies:
        company_name = company.get("title", company.get("domain", ""))
        domain = company.get("domain", "")
        if not domain:
            continue
        
        contacts = find_linkedin_contacts(company_name, domain)
        if contacts:
            print(f"   ✅ Found {len(contacts)} contacts at {company_name}")
            all_contacts.extend(contacts)
        else:
            print(f"   ⚠️  No LinkedIn profiles found for {company_name}")
        
        time.sleep(1)  # Rate limit safety
    
    # Output results
    print("\n" + "="*60)
    print("📊 RESULTS")
    print("="*60)
    
    if all_contacts:
        df = pd.DataFrame(all_contacts)
        csv_filename = "sponsor_contacts.csv"
        df.to_csv(csv_filename, index=False)
        print(f"\n🎉 Success! Found {len(all_contacts)} contacts across {len(companies)} companies.")
        print(f"📁 Saved to {csv_filename}")
        print("\nPreview:")
        print(df[["Company", "Name", "Title", "LinkedIn"]].head(15).to_string(index=False))
    else:
        print("\n⚠️  No LinkedIn contacts found.")
        print("   You may need to search manually for these companies.")


if __name__ == "__main__":
    main()