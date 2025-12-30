#!/usr/bin/env python3
"""
AI-Enabled Email Outreach System

Generates personalized emails and outputs a mail merge CSV for use with
MassMail services (Mailchimp, GMass, etc.)

Template syntax:
- {column_name} - pulls value from CSV column (supports aliases like {name}, {company_name})
- {{prompt}} - sends prompt to LLM with user profile context
"""

import os
import re
import csv
import json
import argparse
from datetime import datetime
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_CSV = PROJECT_ROOT / "searches" / "people" / "people_enriched.csv"

# Column aliases - map simple names to actual CSV column names
COLUMN_ALIASES = {
    "name": ["First Name (Linkedin)", "First Name", "Full Name (Linkedin)"],
    "first_name": ["First Name (Linkedin)", "First Name"],
    "last_name": ["Last Name (Linkedin)", "Last Name"],
    "full_name": ["Full Name (Linkedin)", "Name"],
    "company": ["Company"],
    "company_name": ["Company"],
    "email": ["Email (FullEnrich)"],
    "title": ["Title", "Job Title (Linkedin)", "Headline (Linkedin)"],
    "linkedin": ["LinkedIn Profile Url", "LinkedIn", "Linkedin Url"],
    "location": ["Location (Linkedin)"],
    "headline": ["Headline (Linkedin)"],
    "summary": ["summary (Linkedin)"],
    "company_description": ["Company Description (Linkedin)"],
    "industry": ["Company Industry (Linkedin)"],
    "domain": ["Domain"],
}


def resolve_column(column_name: str, row: dict) -> str:
    """Resolve a column name (possibly an alias) to its value."""
    if column_name in row:
        return row[column_name] or ""
    
    alias_key = column_name.lower().replace(" ", "_")
    if alias_key in COLUMN_ALIASES:
        for real_col in COLUMN_ALIASES[alias_key]:
            if real_col in row and row[real_col]:
                return row[real_col]
    
    for key in row.keys():
        if key.lower() == column_name.lower():
            return row[key] or ""
    
    return ""


def load_contacts(csv_path: str) -> list[dict]:
    """Load contacts from CSV file."""
    contacts = []
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            email = row.get("Email (FullEnrich)", "").strip()
            if email and "@" in email:
                contacts.append(row)
    return contacts


def build_profile_context(row: dict) -> str:
    """Build a rich context string from the contact's profile for LLM prompts."""
    parts = []
    
    name = row.get("First Name (Linkedin)", row.get("First Name", ""))
    company = row.get("Company", "")
    title = row.get("Title", row.get("Job Title (Linkedin)", ""))
    headline = row.get("Headline (Linkedin)", "")
    
    if name: parts.append(f"Name: {name}")
    if company: parts.append(f"Company: {company}")
    if title: parts.append(f"Title: {title}")
    if headline: parts.append(f"LinkedIn Headline: {headline}")
    
    company_desc = row.get("Company Description (Linkedin)", "")
    company_industry = row.get("Company Industry (Linkedin)", "")
    
    if company_desc: parts.append(f"Company Description: {company_desc[:500]}")
    if company_industry: parts.append(f"Industry: {company_industry}")
    
    summary = row.get("summary (Linkedin)", "")
    if summary: parts.append(f"LinkedIn Summary: {summary[:500]}")
    
    return "\n".join(parts)


def process_llm_prompt(prompt: str, profile_context: str, email_context: str = "") -> str:
    """Send a prompt to the LLM with the user's profile and email context."""
    client = OpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1"
    )
    
    system_prompt = f"""You are helping write personalized outreach emails for hackathon sponsorship.

RECIPIENT PROFILE:
{profile_context}

EMAIL TEMPLATE (for context - do not repeat information already in the email):
{email_context}

Write naturally and professionally. Keep responses concise (1-3 sentences max unless asked for more).
Do not use placeholder brackets or variables - write the actual content.
Do not repeat information that's already in the email template.
Do not be overly flattering or use excessive exclamation marks."""

    response = client.chat.completions.create(
        model="google/gemini-2.0-flash-001",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        max_tokens=500
    )
    
    return response.choices[0].message.content.strip()


def substitute_variables(template: str, row: dict) -> str:
    """Substitute {column_name} variables with CSV values."""
    def replace_match(match):
        column_name = match.group(1)
        value = resolve_column(column_name, row)
        return value if value else f"[Missing: {column_name}]"
    
    pattern = r'(?<!\{)\{([^{}]+)\}(?!\})'
    return re.sub(pattern, replace_match, template)


def process_llm_prompts(template: str, row: dict, original_template: str = "") -> str:
    """Process {{prompt}} variables by sending them to the LLM."""
    profile_context = build_profile_context(row)
    email_context = original_template or template
    
    def replace_match(match):
        prompt = match.group(1).strip()
        print(f"   🤖 Generating: {prompt[:50]}...")
        return process_llm_prompt(prompt, profile_context, email_context)
    
    pattern = r'\{\{(.+?)\}\}'
    return re.sub(pattern, replace_match, template, flags=re.DOTALL)


def generate_email(template: str, row: dict) -> tuple[str, str]:
    """Generate a personalized email. Returns (subject, body)."""
    # First pass: substitute CSV variables
    result = substitute_variables(template, row)
    # Second pass: process LLM prompts with original template for context
    result = process_llm_prompts(result, row, original_template=template)
    
    lines = result.strip().split('\n')
    subject = ""
    body_start = 0
    
    for i, line in enumerate(lines):
        if line.lower().startswith("subject:"):
            subject = line[8:].strip()
            body_start = i + 1
            break
    
    body = '\n'.join(lines[body_start:]).strip()
    return subject, body


def preview_email(contact: dict, subject: str, body: str) -> str:
    """Display email preview and get user action."""
    print("\n" + "=" * 70)
    print("📧 EMAIL PREVIEW")
    print("=" * 70)
    
    name = contact.get("Full Name (Linkedin)", contact.get("Name", "Unknown"))
    company = contact.get("Company", "Unknown")
    email = contact.get("Email (FullEnrich)", "")
    
    print(f"To: {name} <{email}>")
    print(f"Company: {company}")
    print("-" * 70)
    print(f"Subject: {subject}")
    print("-" * 70)
    print(body)
    print("=" * 70)
    
    print("\nOptions: [a]pprove  [s]kip  [r]egenerate  [q]uit")
    
    while True:
        choice = input("Choice: ").strip().lower()
        if choice in ['a', 's', 'r', 'q']:
            return choice
        print("Enter a, s, r, or q.")


def run_emailer(
    csv_path: str = None,
    template_path: str = None,
    output_path: str = None
):
    """
    Main workflow - generates personalized emails and outputs a mail merge CSV.
    """
    # Load template
    if not template_path:
        print("❌ No template provided. Use --template")
        return
    
    with open(template_path, 'r') as f:
        template = f.read()
    
    # Load contacts
    csv_file = csv_path or str(DEFAULT_CSV)
    print(f"📂 Loading contacts from: {csv_file}")
    contacts = load_contacts(csv_file)
    print(f"   Found {len(contacts)} contacts with emails")
    
    if not contacts:
        print("✅ No contacts to process!")
        return
    
    # Prepare output
    output_file = output_path or str(SCRIPT_DIR / f"mail_merge_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    
    approved_emails = []
    
    for i, contact in enumerate(contacts):
        email = contact.get("Email (FullEnrich)", "")
        name = contact.get("Full Name (Linkedin)", contact.get("Name", "Unknown"))
        company = contact.get("Company", "Unknown")
        
        print(f"\n\n{'='*70}")
        print(f"📋 Contact {i+1}/{len(contacts)}: {name} @ {company}")
        print("=" * 70)
        
        print("\n🔄 Generating personalized email...")
        
        try:
            subject, body = generate_email(template, contact)
        except Exception as e:
            print(f"❌ Error: {e}")
            continue
        
        action = preview_email(contact, subject, body)
        
        if action == 'q':
            print("\n👋 Quitting...")
            break
        elif action == 's':
            print("⏭️ Skipped")
            continue
        elif action == 'r':
            print("🔄 Regenerating...")
            try:
                subject, body = generate_email(template, contact)
                action = preview_email(contact, subject, body)
                if action != 'a':
                    continue
            except Exception as e:
                print(f"❌ Error: {e}")
                continue
        
        if action == 'a':
            approved_emails.append({
                "email": email,
                "name": name,
                "company": company,
                "subject": subject,
                "body": body
            })
            print("✅ Approved!")
    
    # Write output CSV
    if approved_emails:
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=["email", "name", "company", "subject", "body"])
            writer.writeheader()
            writer.writerows(approved_emails)
        
        print(f"\n\n{'='*70}")
        print("📊 SUMMARY")
        print("=" * 70)
        print(f"   Approved: {len(approved_emails)}")
        print(f"   Output: {output_file}")
        print("\n💡 Import this CSV into your mail merge service (GMass, Mailchimp, etc.)")
    else:
        print("\n❌ No emails approved.")


def main():
    parser = argparse.ArgumentParser(description="AI-Enabled Email Outreach - Mail Merge Generator")
    parser.add_argument("--csv", help="Path to CSV file with contacts")
    parser.add_argument("--template", required=True, help="Path to email template file")
    parser.add_argument("--output", help="Output path for mail merge CSV")
    
    args = parser.parse_args()
    
    run_emailer(
        csv_path=args.csv,
        template_path=args.template,
        output_path=args.output
    )


if __name__ == "__main__":
    main()
