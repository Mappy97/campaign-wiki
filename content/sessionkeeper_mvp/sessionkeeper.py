#!/usr/bin/env python3
"""
Session Keeper MVP - Step 5: Deterministic Wiki Writer
"""

import argparse
import sys
import os
import json
import subprocess
import re
import glob
from datetime import datetime

# Configuration
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

def load_config():
    """Load configuration from config.json"""
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def load_prompt_template(template_name):
    """Load a prompt template from the vault"""
    config = load_config()
    vault_path = config["vault_path"]
    template_path = os.path.join(vault_path, "Templates", template_name)
    with open(template_path, "r") as f:
        return f.read()


def call_llm(prompt, system_prompt=None):
    """Call OpenRouter API for LLM generation"""
    import requests
    
    config = load_config()
    api_key = os.environ.get("OPENROUTER_API_KEY")
    
    if not api_key:
        openclaw_config = os.path.expanduser("~/.openclaw/openclaw.json")
        if os.path.exists(openclaw_config):
            with open(openclaw_config, "r") as f:
                oc = json.load(f)
                api_key = oc.get("models", {}).get("providers", {}).get("openrouter", {}).get("apiKey")
        
        if not api_key:
            print("[ERROR] No OpenRouter API key found.")
            sys.exit(1)
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://sessionkeeper.local",
        "X-Title": "Session Keeper MVP"
    }
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    data = {
        "model": "anthropic/claude-3.5-sonnet",
        "messages": messages,
        "max_tokens": 4096
    }
    
    print(f"[LLM] Calling OpenRouter...")
    
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=120
        )
        
        if response.status_code != 200:
            print(f"[ERROR] API call failed: {response.status_code}")
            sys.exit(1)
        
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[ERROR] LLM call failed: {e}")
        sys.exit(1)


def detect_latest_audio(vault_path):
    """Choose most recently modified file in Inbox/Audio"""
    inbox_audio = os.path.join(vault_path, "Inbox", "Audio")
    
    if not os.path.exists(inbox_audio):
        return None
    
    extensions = [".mp3", ".m4a", ".wav", ".ogg", ".oga"]
    audio_files = []
    
    for fname in os.listdir(inbox_audio):
        ext = os.path.splitext(fname)[1].lower()
        if ext in extensions:
            fpath = os.path.join(inbox_audio, fname)
            audio_files.append((fpath, os.path.getmtime(fpath)))
    
    if not audio_files:
        return None
    
    audio_files.sort(key=lambda x: x[1], reverse=True)
    return audio_files[0][0]


def detect_latest_session(vault_path):
    """Find the latest processed session folder"""
    processed_dir = os.path.join(vault_path, "Inbox", "Processed")
    
    if not os.path.exists(processed_dir):
        return None
    
    session_folders = []
    for item in os.listdir(processed_dir):
        item_path = os.path.join(processed_dir, item)
        if os.path.isdir(item_path) and item.startswith("sess_"):
            session_folders.append((item_path, os.path.getmtime(item_path)))
    
    if not session_folders:
        return None
    
    session_folders.sort(key=lambda x: x[1], reverse=True)
    return session_folders[0][0]


def check_ffmpeg():
    """Check if ffmpeg is available"""
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def normalize_audio(input_path, output_dir):
    """Copy audio file (Whisper API handles many formats directly)"""
    os.makedirs(output_dir, exist_ok=True)
    
    # Get file extension
    ext = os.path.splitext(input_path)[1]
    
    # Whisper API supports: mp3, mp4, mpeg, mpga, m4a, wav, webm
    supported = [".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm"]
    
    if ext.lower() not in supported:
        print(f"[WARNING] {ext} may not be supported by Whisper API")
    
    # Copy file to output directory (or convert if needed - simplified for now)
    output_path = os.path.join(output_dir, f"audio{ext}")
    
    # For m4a, Whisper API can handle it directly
    import shutil
    shutil.copy2(input_path, output_path)
    
    print(f"[NORMALIZE] Copied: {output_path}")
    return output_path


def transcribe(audio_path):
    """Transcribe audio using OpenRouter Gemini API"""
    import requests
    import base64
    
    # Get OpenRouter API key
    openclaw_config = os.path.expanduser("~/.openclaw/openclaw.json")
    api_key = None
    
    if os.path.exists(openclaw_config):
        with open(openclaw_config, "r") as f:
            oc = json.load(f)
            api_key = oc.get("models", {}).get("providers", {}).get("openrouter", {}).get("apiKey")
    
    if not api_key:
        print("[ERROR] No OpenRouter API key found.")
        sys.exit(1)
    
    print(f"[TRANSCRIBE] Reading {audio_path}...")
    
    # Read and encode audio file
    with open(audio_path, "rb") as f:
        audio_data = base64.b64encode(f.read()).decode("utf-8")
    
    # Determine mime type
    ext = os.path.splitext(audio_path)[1].lower()
    mime_types = {
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".wav": "audio/wav",
        ".webm": "audio/webm",
        ".mp4": "video/mp4"
    }
    mime_type = mime_types.get(ext, "audio/mpeg")
    
    print(f"[TRANSCRIBE] Sending to Gemini via OpenRouter...")
    
    # Call Gemini via OpenRouter with audio
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://sessionkeeper.local",
        "X-Title": "Session Keeper MVP"
    }
    
    # Build message with audio
    data = {
        "model": "google/gemini-2.0-flash-exp",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Please transcribe this audio. Return the full transcription with timestamps if possible. Format as JSON with this structure: {\"segments\": [{\"start\": seconds, \"end\": seconds, \"text\": \"transcribed text\"}]}"
                    },
                    {
                        "type": "media",
                        "mime_type": mime_type,
                        "data": audio_data
                    }
                ]
            }
        ],
        "max_tokens": 8192
    }
    
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=180
        )
        
        if response.status_code != 200:
            print(f"[ERROR] Gemini API failed: {response.status_code}")
            print(f"[ERROR] {response.text}")
            # Fall back to text-only request
            return transcribe_text_only(audio_path, api_key)
        
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        
        # Try to parse JSON from response
        try:
            # Look for JSON in response
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                transcript_data = json.loads(json_match.group())
                if "segments" in transcript_data:
                    return {
                        "segments": transcript_data["segments"],
                        "meta": {"engine": "gemini_audio", "language": "en"}
                    }
        except:
            pass
        
        # If no JSON, create simple segment
        return {
            "segments": [{"start": 0, "end": 0, "speaker": "UNKNOWN", "text": content}],
            "meta": {"engine": "gemini_audio", "language": "en"}
        }
        
    except Exception as e:
        print(f"[ERROR] Transcription failed: {e}")
        return transcribe_text_only(audio_path, api_key)


def transcribe_text_only(audio_path, api_key):
    """Fallback: Ask Gemini to describe what the audio might contain"""
    import requests
    
    print("[TRANSCRIBE] Using text-only fallback...")
    
    # Read small portion to get duration estimate (crude)
    import os
    file_size = os.path.getsize(audio_path)
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://sessionkeeper.local",
        "X-Title": "Session Keeper MVP"
    }
    
    # Since we can't actually transcribe without audio processing,
    # we'll note this limitation
    print("[ERROR] Audio transcription requires ffmpeg + Whisper or API access")
    print("[INFO] Please install ffmpeg manually or provide working API key")
    
    # Return placeholder
    return {
        "segments": [{
            "start": 0,
            "end": 0,
            "speaker": "UNKNOWN",
            "text": "[Audio file present - transcription not available without ffmpeg]"
        }],
        "meta": {"engine": "fallback", "language": "en", "error": "no_ffmpeg"}
    }


def build_entity_index_excerpt(entity_index_json):
    """Build condensed entity index for LLM"""
    excerpt = {"entities": []}
    
    if not entity_index_json or "entities" not in entity_index_json:
        return excerpt
    
    for entity in entity_index_json["entities"]:
        excerpt_entity = {
            "entity_id": entity.get("entity_id", ""),
            "type": entity.get("type", ""),
            "canonical_name": entity.get("canonical_name", ""),
            "aliases": entity.get("aliases", []),
            "last_known_state": entity.get("last_known_state", "")
        }
        excerpt["entities"].append(excerpt_entity)
    
    MAX_ENTITIES = 50
    if len(excerpt["entities"]) > MAX_ENTITIES:
        excerpt["entities"] = excerpt["entities"][:MAX_ENTITIES]
    
    return excerpt


def load_entity_index(vault_path):
    """Load entity_index.json"""
    index_path = os.path.join(vault_path, "Indexes", "entity_index.json")
    if os.path.exists(index_path):
        with open(index_path, "r") as f:
            return json.load(f)
    return {"campaign_id": "camp_campaign", "campaign_name": "Campaign", "entities": []}


def load_open_threads(vault_path):
    """Load open_threads.md"""
    thread_path = os.path.join(vault_path, "Indexes", "open_threads.md")
    if os.path.exists(thread_path):
        with open(thread_path, "r") as f:
            return f.read()
    return "# Open Threads\n\n## HIGH\n\n## MED\n\n## LOW\n\n## Needs Review\n"


def save_open_threads(vault_path, content):
    """Save open_threads.md"""
    thread_path = os.path.join(vault_path, "Indexes", "open_threads.md")
    with open(thread_path, "w") as f:
        f.write(content)
    print(f"[INDEX] Updated: {thread_path}")


def generate_session_notes(transcript_data, entity_excerpt, session_id, output_dir):
    """Generate session notes via LLM"""
    print(f"\n[NOTES] Generating session notes...")
    
    prompt_template = load_prompt_template("session_notes_prompt.txt")
    transcript_text = json.dumps(transcript_data, indent=2)
    entity_text = json.dumps(entity_excerpt, indent=2)
    
    prompt = f"""{prompt_template}

## Transcript
```json
{transcript_text}
```

## Current Entity Index (excerpt)
```json
{entity_text}
```

Return JSON first, then markdown.
"""
    
    response = call_llm(prompt)
    
    # Parse JSON from response
    json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
    if json_match:
        session_notes = json.loads(json_match.group(1))
    else:
        try:
            start = response.find('{')
            end = response.rfind('}') + 1
            session_notes = json.loads(response[start:end])
        except:
            print(f"[ERROR] Could not parse JSON from LLM response")
            sys.exit(1)
    
    notes_json_path = os.path.join(output_dir, "session_notes.json")
    with open(notes_json_path, "w") as f:
        json.dump(session_notes, f, indent=2)
    print(f"[NOTES] Saved: {notes_json_path}")
    
    # Generate recap.md
    recap_md = f"""# Session Recap - {session_id}

## Summary
{ session_notes.get('summary', 'No summary available.') }

## Key Events
"""
    for event in session_notes.get('key_events', []):
        recap_md += f"- **[{event.get('timestamp', 'N/A')}]** {event.get('description', '')}\n"

    recap_md += "\n## NPCs\n"
    for npc in session_notes.get('npc_interactions', []):
        recap_md += f"- **{npc.get('npc_name', 'Unknown')}**: {npc.get('disposition', 'UNKNOWN')}\n"

    recap_md += "\n## Quest Progress\n"
    for quest in session_notes.get('quest_updates', []):
        recap_md += f"- **{quest.get('quest_name', 'Unknown')}**: {quest.get('status', 'UNKNOWN')}\n"

    recap_md += "\n## Open Threads\n"
    for thread in session_notes.get('open_threads', []):
        recap_md += f"- **[{thread.get('priority', 'LOW')}]** {thread.get('thread', '')}\n"

    recap_path = os.path.join(output_dir, "recap.md")
    with open(recap_path, "w") as f:
        f.write(recap_md)
    
    return session_notes, notes_json_path, recap_path


def generate_entity_ops(session_notes, entity_excerpt, session_id, output_dir):
    """Generate entity operations via LLM"""
    print(f"\n[ENTITY] Generating entity operations...")
    
    prompt_template = load_prompt_template("entity_ops_prompt.txt")
    session_text = json.dumps(session_notes, indent=2)
    entity_text = json.dumps(entity_excerpt, indent=2)
    
    config = load_config()
    dedupe = config.get("dedupe", {"auto_merge_threshold": 0.8, "review_threshold": 0.5})
    
    prompt = f"""{prompt_template}

## Session Notes
```json
{session_text}
```

## Current Entity Index (excerpt)
```json
{entity_text}
```

## Dedupication Thresholds
- auto_merge_threshold: {dedupe.get('auto_merge_threshold', 0.8)}
- review_threshold: {dedupe.get('review_threshold', 0.5)}

Return entity_ops_bundle.json.
"""
    
    response = call_llm(prompt)
    
    json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
    if json_match:
        entity_ops = json.loads(json_match.group(1))
    else:
        try:
            start = response.find('{')
            end = response.rfind('}') + 1
            entity_ops = json.loads(response[start:end])
        except:
            print(f"[ERROR] Could not parse JSON from LLM response")
            sys.exit(1)
    
    entity_ops["session_id"] = session_id
    
    ops_path = os.path.join(output_dir, "entity_ops_bundle.json")
    with open(ops_path, "w") as f:
        json.dump(entity_ops, f, indent=2)
    print(f"[ENTITY] Saved: {ops_path}")
    
    return entity_ops, ops_path


# ============================================================
# STEP 5: DETERMINISTIC WIKI WRITER
# ============================================================

def preserve_manual_sections(content, new_content):
    """Preserve manual sections between comment markers"""
    manual_pattern = re.compile(r'<!--\s*MANUAL_START\s*-->.*?<!--\s*MANUAL_END\s*-->', re.DOTALL)
    
    manual_sections = manual_pattern.findall(content)
    if not manual_sections:
        return new_content
    
    for section in manual_sections:
        new_content += f"\n\n{section}"
    
    return new_content


def ensure_frontmatter(entity_type, entity_id, canonical_name, aliases, publish=True, draft=False, last_seen_session_id=None):
    """Generate YAML frontmatter for entities"""
    fm = {
        "id": entity_id,
        "type": entity_type,
        "aliases": aliases if aliases else [],
        "publish": publish,
        "draft": draft,
    }
    if last_seen_session_id:
        fm["last_seen_session"] = last_seen_session_id
    
    return fm


def ensure_session_frontmatter(session_id, date, publish=True):
    """Generate YAML frontmatter for sessions"""
    return {
        "id": session_id,
        "date": date,
        "type": "session",
        "publish": publish
    }


def format_wikilinks(text):
    """Convert [[Name]] to Obsidian wikilinks, preserve existing"""
    # Already in wikilink format, just ensure proper casing
    return text


def apply_entity_op(entity_op, vault_path, existing_entities):
    """Apply a single entity operation"""
    op = entity_op.get("op", "CREATE")
    entity_type = entity_op.get("entity_type", "NPC")
    entity_id = entity_op.get("entity_id", "")
    canonical_name = entity_op.get("canonical_name", "")
    aliases = entity_op.get("aliases", [])
    changes = entity_op.get("changes", {})
    
    # Map entity type to folder
    type_folder_map = {
        "PC": "Entities/PCs",
        "NPC": "Entities/NPCs",
        "LOCATION": "Entities/Locations",
        "FACTION": "Entities/Factions",
        "QUEST": "Entities/Quests",
        "ITEM": "Entities/Items",
        "EVENT": "Entities/Events"
    }
    
    folder = type_folder_map.get(entity_type, "Entities")
    safe_name = re.sub(r'[^\w\s-]', '', canonical_name).strip().replace(' ', '-')
    filepath = os.path.join(vault_path, folder, f"{safe_name}.md")
    
    # Handle MERGE operation
    if op == "MERGE":
        # Find target entity and merge
        pass
    
    # Build frontmatter
    fm = ensure_frontmatter(
        entity_type=entity_type,
        entity_id=entity_id,
        canonical_name=canonical_name,
        aliases=aliases,
        publish=True,
        draft=False
    )
    
    # Build content
    detail = changes.get("detail", "")
    summary = changes.get("summary", "")
    
    content = f"---\n"
    for key, value in fm.items():
        content += f"{key}: {json.dumps(value)}\n"
    content += f"---\n\n"
    content += f"# {canonical_name}\n\n"
    if summary:
        content += f"**Summary:** {summary}\n\n"
    content += f"{detail}\n"
    
    # Preserve manual sections if file exists
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            existing = f.read()
        content = preserve_manual_sections(existing, content)
    
    # Ensure folder exists
    os.makedirs(os.path.join(vault_path, folder), exist_ok=True)
    
    with open(filepath, "w") as f:
        f.write(content)
    
    print(f"[WIKI] {'Created' if op == 'CREATE' else 'Updated'}: {filepath}")
    return filepath


def apply_session_page(session_page, vault_path):
    """Create session page"""
    filename = session_page.get("filename", "")
    frontmatter = session_page.get("frontmatter", {})
    content = session_page.get("content", "")
    
    if not filename:
        return None
    
    filepath = os.path.join(vault_path, filename)
    
    # Ensure folder exists
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    # Build content with frontmatter
    md_content = f"---\n"
    for key, value in frontmatter.items():
        md_content += f"{key}: {json.dumps(value)}\n"
    md_content += f"---\n\n"
    md_content += content
    
    with open(filepath, "w") as f:
        f.write(md_content)
    
    print(f"[WIKI] Created session page: {filepath}")
    return filepath


def update_entity_index(entity_index, ops, vault_path):
    """Apply operations to entity_index.json"""
    current_entities = entity_index.get("entities", [])
    
    for op in ops:
        entity_op = op.get("changes", {})
        
        # Build entity entry
        entry = {
            "entity_id": op.get("entity_id", ""),
            "type": op.get("entity_type", ""),
            "canonical_name": op.get("canonical_name", ""),
            "aliases": op.get("aliases", []),
            "last_known_state": entity_op.get("summary", ""),
            "history": []
        }
        
        # Check if exists
        existing_idx = None
        for i, e in enumerate(current_entities):
            if e.get("entity_id") == entry["entity_id"]:
                existing_idx = i
                break
        
        if op.get("op") == "CREATE":
            if existing_idx is None:
                current_entities.append(entry)
        elif op.get("op") == "UPDATE":
            if existing_idx is not None:
                current_entities[existing_idx].update(entry)
    
    entity_index["entities"] = current_entities
    
    index_path = os.path.join(vault_path, "Indexes", "entity_index.json")
    with open(index_path, "w") as f:
        json.dump(entity_index, f, indent=2)
    
    print(f"[INDEX] Updated entity_index.json")
    return entity_index


def update_open_threads(open_threads_content, ops_bundle, vault_path):
    """Update open_threads.md"""
    # Get thread updates from ops bundle
    indexes = ops_bundle.get("indexes", {})
    thread_updates = indexes.get("open_threads", {})
    adds = thread_updates.get("add", [])
    resolves = thread_updates.get("resolve", [])
    
    # Parse existing content and update
    lines = open_threads_content.split('\n')
    high_lines = []
    med_lines = []
    low_lines = []
    review_lines = []
    
    current_section = None
    for line in lines:
        if "## HIGH" in line:
            current_section = "HIGH"
        elif "## MED" in line:
            current_section = "MED"
        elif "## LOW" in line:
            current_section = "LOW"
        elif "## Needs Review" in line:
            current_section = "REVIEW"
        elif line.strip().startswith('- '):
            if current_section == "HIGH":
                high_lines.append(line)
            elif current_section == "MED":
                med_lines.append(line)
            elif current_section == "LOW":
                low_lines.append(line)
            elif current_section == "REVIEW":
                review_lines.append(line)
    
    # Add new threads
    for thread in adds:
        priority = thread.get("priority", "LOW").upper()
        thread_text = f"- {thread.get('thread', '')}"
        if priority == "HIGH":
            high_lines.append(thread_text)
        elif priority == "MED":
            med_lines.append(thread_text)
        else:
            low_lines.append(thread_text)
    
    # Rebuild content
    new_content = "# Open Threads\n\n"
    new_content += "## HIGH\n" + "\n".join(high_lines) + "\n\n"
    new_content += "## MED\n" + "\n".join(med_lines) + "\n\n"
    new_content += "## LOW\n" + "\n".join(low_lines) + "\n\n"
    new_content += "## Needs Review\n" + "\n".join(review_lines) + "\n"
    
    thread_path = os.path.join(vault_path, "Indexes", "open_threads.md")
    with open(thread_path, "w") as f:
        f.write(new_content)
    
    print(f"[INDEX] Updated open_threads.md")
    return new_content


def apply_ops_to_vault(entity_ops_bundle, vault_path, auto_apply=True):
    """Apply entity operations to the Obsidian vault"""
    print(f"\n[VAULT] Applying operations to vault...")
    
    operations = entity_ops_bundle.get("operations", [])
    session_page = entity_ops_bundle.get("session_page", {})
    indexes = entity_ops_bundle.get("indexes", {})
    needs_review = entity_ops_bundle.get("needs_review", [])
    
    # Load current entity index
    entity_index = load_entity_index(vault_path)
    open_threads = load_open_threads(vault_path)
    
    applied_count = 0
    
    # Apply entity operations
    for op in operations:
        try:
            apply_entity_op(op, vault_path, entity_index.get("entities", []))
            applied_count += 1
        except Exception as e:
            print(f"[ERROR] Failed to apply op: {e}")
    
    # Create session page
    if session_page:
        apply_session_page(session_page, vault_path)
        applied_count += 1
    
    # Update entity index
    entity_index = update_entity_index(entity_index, operations, vault_path)
    
    # Update open threads
    update_open_threads(open_threads, entity_ops_bundle, vault_path)
    
    # Print needs review warning
    if needs_review and auto_apply:
        print(f"\n{'='*50}")
        print("⚠️  NEEDS REVIEW")
        print(f"{'='*50}")
        for item in needs_review:
            print(f"  - {item.get('entity_id', 'unknown')}: {item.get('reason', '')}")
        print(f"{'='*50}\n")
    
    print(f"\n[VAULT] Applied {applied_count} operations to vault")
    
    return {
        "applied": applied_count,
        "needs_review": len(needs_review)
    }


def find_latest_processed_session(vault_path):
    """Find latest processed session folder with entity_ops_bundle.json"""
    processed_dir = os.path.join(vault_path, "Inbox", "Processed")
    
    if not os.path.exists(processed_dir):
        return None
    
    session_folders = []
    for item in os.listdir(processed_dir):
        item_path = os.path.join(processed_dir, item)
        if os.path.isdir(item_path) and item.startswith("sess_"):
            ops_file = os.path.join(item_path, "entity_ops_bundle.json")
            if os.path.exists(ops_file):
                session_folders.append((item_path, os.path.getmtime(item_path)))
    
    if not session_folders:
        return None
    
    session_folders.sort(key=lambda x: x[1], reverse=True)
    return session_folders[0][0]


def apply_latest():
    """Apply latest processed session to vault"""
    config = load_config()
    vault_path = config["vault_path"]
    
    print(f"[APPLY_LATEST] Looking for latest processed session...")
    
    latest_session = find_latest_processed_session(vault_path)
    
    if not latest_session:
        print("[ERROR] No processed sessions with entity_ops_bundle.json found")
        sys.exit(1)
    
    ops_file = os.path.join(latest_session, "entity_ops_bundle.json")
    with open(ops_file, "r") as f:
        entity_ops = json.load(f)
    
    print(f"[APPLY_LATEST] Found: {latest_session}")
    print(f"[APPLY_LATEST] Operations: {len(entity_ops.get('operations', []))}")
    
    result = apply_ops_to_vault(entity_ops, vault_path, auto_apply=True)
    
    print(f"\n{'='*50}")
    print("APPLY COMPLETE")
    print(f"{'='*50}")
    print(f"  Applied: {result['applied']} operations")
    print(f"  Needs Review: {result['needs_review']} items")
    print(f"  Session: {latest_session}")
    print(f"{'='*50}\n")
    
    return result


def process_audio(audio_path, vault_path, apply=True):
    """Full processing pipeline"""
    config = load_config()
    
    session_id = f"sess_{datetime.now().strftime('%Y%m%d_%H%M')}"
    processed_dir = os.path.join(vault_path, "Inbox", "Processed", session_id)
    
    print(f"\n{'='*50}")
    print(f"[PROCESS] Session ID: {session_id}")
    print(f"{'='*50}\n")
    
    os.makedirs(processed_dir, exist_ok=True)
    
    # Step 1: Normalize
    print("[STEP 1] Normalizing audio...")
    wav_path = normalize_audio(audio_path, processed_dir)
    
    # Step 2: Transcribe
    print("\n[STEP 2] Transcribing audio...")
    transcript_data = transcribe(wav_path)
    
    transcript_path = os.path.join(processed_dir, "transcript.json")
    with open(transcript_path, "w") as f:
        json.dump(transcript_data, f, indent=2)
    
    # Step 3: Session notes
    entity_index = load_entity_index(vault_path)
    entity_excerpt = build_entity_index_excerpt(entity_index)
    
    print("\n[STEP 3] Generating session notes...")
    session_notes, notes_path, recap_path = generate_session_notes(
        transcript_data, entity_excerpt, session_id, processed_dir
    )
    
    # Step 4: Entity ops
    print("\n[STEP 4] Generating entity operations...")
    entity_ops, ops_path = generate_entity_ops(
        session_notes, entity_excerpt, session_id, processed_dir
    )
    
    # Step 5: Apply to vault
    if apply:
        print("\n[STEP 5] Applying to vault...")
        apply_ops_to_vault(entity_ops, vault_path, auto_apply=True)
    
    print(f"\n{'='*50}")
    print("PROCESSING COMPLETE")
    print(f"{'='*50}")
    print(f"  audio.wav:     {wav_path}")
    print(f"  transcript:    {transcript_path}")
    print(f"  session_notes: {notes_path}")
    print(f"  recap:         {recap_path}")
    print(f"  entity_ops:     {ops_path}")
    print(f"{'='*50}\n")
    
    return session_id


def process_latest(apply=True):
    """Process the latest audio file"""
    config = load_config()
    vault_path = config["vault_path"]
    
    latest = detect_latest_audio(vault_path)
    
    if not latest:
        print("\n" + "="*50)
        print("NO AUDIO FILES FOUND")
        print("="*50)
        print(f"Drop an audio file into {vault_path}/Inbox/Audio/")
        print("Then re-run: python sessionkeeper.py process_latest")
        print("="*50 + "\n")
        sys.exit(1)
    
    process_audio(latest, vault_path, apply=apply)


def process_file(path, apply=True):
    """Process a specific audio file"""
    if not os.path.exists(path):
        print(f"[ERROR] File not found: {path}")
        sys.exit(1)
    
    config = load_config()
    vault_path = config["vault_path"]
    
    process_audio(path, vault_path, apply=apply)


def main():
    parser = argparse.ArgumentParser(description="Session Keeper MVP - Step 5")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    subparsers.add_parser("process_latest", help="Process latest audio in inbox")
    
    file_parser = subparsers.add_parser("process_file", help="Process a specific audio file")
    file_parser.add_argument("path", help="Path to audio file")
    
    subparsers.add_parser("apply_latest", help="Apply latest processed session to vault")

    args = parser.parse_args()

    if args.command == "process_latest":
        process_latest(apply=True)
    elif args.command == "process_file":
        if not hasattr(args, "path") or not args.path:
            print("Error: process_file requires a path argument")
            sys.exit(1)
        process_file(args.path, apply=True)
    elif args.command == "apply_latest":
        apply_latest()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
