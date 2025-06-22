from typing import Any, Dict, List
import httpx
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("visual_code_server")

async def get_code(url: str) -> str:
    """
    Fetch source code from a GitHub URL.
    
    Args:
        url: GitHub URL of the code file
    Returns:
        str: Source code content or error message
    """
    USER_AGENT = "visual-fastmcp/0.1"

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            # Convert GitHub URL to raw content URL
            raw_url = url.replace("github.com", "raw.githubusercontent.com")\
                        .replace("/blob/", "/")
            response = await client.get(raw_url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.text
        except Exception as e:
            return f"Error fetching code: {str(e)}"
        
@mcp.tool()
async def visualize_code(url: str) -> str:
    """
    Visualize the code extracted from a Github repository URL in the format of SVG code.

    Args:
        url: The GitHub repository URL
    
    Returns:
        SVG code that visualizes the code structure or hierarchy.
    """
    code = await get_code(url)
    if "error" in code.lower():
        return code
    
    # Return the code content for LLM to generate SVG
    return f"Please generate an SVG visualization for this code:\n\n{code}"

@mcp.tool()
async def daily_assistant(task_type: str, data: str = "") -> str:
    """
    Smart daily routine assistant that helps with various local tasks.
    
    Args:
        task_type: Type of task (schedule, reminder, note, habit, weather, focus)
        data: Task-specific data (JSON string or plain text)
    
    Returns:
        Result of the task operation
    """
    home_dir = Path.home()
    assistant_dir = home_dir / ".daily_assistant"
    assistant_dir.mkdir(exist_ok=True)
    
    if task_type == "schedule":
        return await _handle_schedule(assistant_dir, data)
    elif task_type == "reminder":
        return await _handle_reminder(assistant_dir, data)
    elif task_type == "note":
        return await _handle_note(assistant_dir, data)
    elif task_type == "habit":
        return await _handle_habit(assistant_dir, data)
    elif task_type == "focus":
        return await _handle_focus_session(assistant_dir, data)
    elif task_type == "summary":
        return await _get_daily_summary(assistant_dir)
    else:
        return f"Unknown task type: {task_type}. Available: schedule, reminder, note, habit, focus, summary"

async def _handle_schedule(assistant_dir: Path, data: str) -> str:
    """Handle scheduling tasks"""
    schedule_file = assistant_dir / "schedule.json"
    
    try:
        if data.strip():
            task_data = json.loads(data)
            schedule = _load_json_file(schedule_file)
            
            if "action" in task_data and task_data["action"] == "add":
                task_id = str(len(schedule.get("tasks", [])) + 1)
                schedule.setdefault("tasks", []).append({
                    "id": task_id,
                    "title": task_data.get("title", ""),
                    "time": task_data.get("time", ""),
                    "date": task_data.get("date", datetime.now().strftime("%Y-%m-%d")),
                    "completed": False
                })
                _save_json_file(schedule_file, schedule)
                return f"Task '{task_data.get('title')}' scheduled for {task_data.get('time')} on {task_data.get('date')}"
        
        # Return today's schedule
        schedule = _load_json_file(schedule_file)
        today = datetime.now().strftime("%Y-%m-%d")
        today_tasks = [t for t in schedule.get("tasks", []) if t.get("date") == today]
        
        if not today_tasks:
            return "No tasks scheduled for today"
        
        result = "Today's Schedule:\n"
        for task in sorted(today_tasks, key=lambda x: x.get("time", "")):
            status = "✓" if task.get("completed") else "○"
            result += f"{status} {task.get('time', 'No time')} - {task.get('title', 'Untitled')}\n"
        
        return result.strip()
    
    except Exception as e:
        return f"Schedule error: {str(e)}"

async def _handle_reminder(assistant_dir: Path, data: str) -> str:
    """Handle reminder tasks"""
    reminders_file = assistant_dir / "reminders.json"
    
    try:
        reminders = _load_json_file(reminders_file)
        
        if data.strip():
            reminder_data = json.loads(data)
            if "action" in reminder_data and reminder_data["action"] == "add":
                reminders.setdefault("items", []).append({
                    "text": reminder_data.get("text", ""),
                    "due": reminder_data.get("due", ""),
                    "created": datetime.now().isoformat()
                })
                _save_json_file(reminders_file, reminders)
                return f"Reminder set: {reminder_data.get('text')}"
        
        # Show active reminders
        active = reminders.get("items", [])
        if not active:
            return "No active reminders"
        
        result = "Active Reminders:\n"
        for i, reminder in enumerate(active, 1):
            result += f"{i}. {reminder.get('text', 'No text')} (Due: {reminder.get('due', 'No due date')})\n"
        
        return result.strip()
    
    except Exception as e:
        return f"Reminder error: {str(e)}"

async def _handle_note(assistant_dir: Path, data: str) -> str:
    """Handle quick notes"""
    notes_file = assistant_dir / "notes.json"
    
    try:
        notes = _load_json_file(notes_file)
        
        if data.strip():
            note_data = json.loads(data) if data.startswith("{") else {"text": data}
            notes.setdefault("entries", []).append({
                "text": note_data.get("text", data),
                "timestamp": datetime.now().isoformat(),
                "tags": note_data.get("tags", [])
            })
            _save_json_file(notes_file, notes)
            return "Note saved successfully"
        
        # Show recent notes
        recent = notes.get("entries", [])[-5:]
        if not recent:
            return "No notes found"
        
        result = "Recent Notes:\n"
        for note in reversed(recent):
            timestamp = datetime.fromisoformat(note["timestamp"]).strftime("%m/%d %H:%M")
            result += f"[{timestamp}] {note.get('text', 'No content')[:50]}...\n"
        
        return result.strip()
    
    except Exception as e:
        return f"Note error: {str(e)}"

async def _handle_habit(assistant_dir: Path, data: str) -> str:
    """Handle habit tracking"""
    habits_file = assistant_dir / "habits.json"
    
    try:
        habits = _load_json_file(habits_file)
        today = datetime.now().strftime("%Y-%m-%d")
        
        if data.strip():
            habit_data = json.loads(data)
            
            if "action" in habit_data and habit_data["action"] == "track":
                habit_name = habit_data.get("habit", "")
                habits.setdefault("tracking", {}).setdefault(habit_name, []).append(today)
                _save_json_file(habits_file, habits)
                return f"Habit '{habit_name}' tracked for today"
            
            elif "action" in habit_data and habit_data["action"] == "add":
                habit_name = habit_data.get("name", "")
                habits.setdefault("list", []).append(habit_name)
                _save_json_file(habits_file, habits)
                return f"Habit '{habit_name}' added to tracking list"
        
        # Show habit status
        tracking = habits.get("tracking", {})
        if not tracking:
            return "No habits being tracked"
        
        result = "Habit Status (Last 7 days):\n"
        for habit, dates in tracking.items():
            recent_dates = [d for d in dates if (datetime.now() - datetime.strptime(d, "%Y-%m-%d")).days <= 7]
            streak = len(recent_dates)
            result += f"{habit}: {streak}/7 days\n"
        
        return result.strip()
    
    except Exception as e:
        return f"Habit error: {str(e)}"

async def _handle_focus_session(assistant_dir: Path, data: str) -> str:
    """Handle focus/pomodoro sessions"""
    focus_file = assistant_dir / "focus.json"
    
    try:
        focus_data = _load_json_file(focus_file)
        
        if data.strip():
            session_data = json.loads(data)
            
            if "action" in session_data and session_data["action"] == "start":
                duration = session_data.get("duration", 25)
                task = session_data.get("task", "Focus session")
                
                session = {
                    "task": task,
                    "duration": duration,
                    "start_time": datetime.now().isoformat(),
                    "end_time": (datetime.now() + timedelta(minutes=duration)).isoformat()
                }
                
                focus_data.setdefault("sessions", []).append(session)
                _save_json_file(focus_file, focus_data)
                
                return f"Focus session started: {task} ({duration} minutes)\nEnd time: {datetime.now() + timedelta(minutes=duration)}"
        
        # Show today's focus sessions
        sessions = focus_data.get("sessions", [])
        today_sessions = [s for s in sessions if s.get("start_time", "").startswith(datetime.now().strftime("%Y-%m-%d"))]
        
        if not today_sessions:
            return "No focus sessions today"
        
        total_minutes = sum(s.get("duration", 0) for s in today_sessions)
        result = f"Today's Focus: {len(today_sessions)} sessions, {total_minutes} minutes\n\n"
        
        for session in today_sessions[-3:]:
            start = datetime.fromisoformat(session["start_time"]).strftime("%H:%M")
            result += f"[{start}] {session.get('task', 'Unknown')} ({session.get('duration', 0)}min)\n"
        
        return result.strip()
    
    except Exception as e:
        return f"Focus error: {str(e)}"

async def _get_daily_summary(assistant_dir: Path) -> str:
    """Get a summary of today's activities"""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        summary = f"Daily Summary for {today}\n" + "="*30 + "\n\n"
        
        # Schedule summary
        schedule = _load_json_file(assistant_dir / "schedule.json")
        today_tasks = [t for t in schedule.get("tasks", []) if t.get("date") == today]
        completed = len([t for t in today_tasks if t.get("completed")])
        summary += f"Tasks: {completed}/{len(today_tasks)} completed\n"
        
        # Focus summary
        focus_data = _load_json_file(assistant_dir / "focus.json")
        today_sessions = [s for s in focus_data.get("sessions", []) if s.get("start_time", "").startswith(today)]
        total_focus = sum(s.get("duration", 0) for s in today_sessions)
        summary += f"Focus: {len(today_sessions)} sessions, {total_focus} minutes\n"
        
        # Habits summary
        habits = _load_json_file(assistant_dir / "habits.json")
        habits_today = sum(1 for dates in habits.get("tracking", {}).values() if today in dates)
        summary += f"Habits: {habits_today} completed today\n"
        
        return summary
    
    except Exception as e:
        return f"Summary error: {str(e)}"

def _load_json_file(file_path: Path) -> Dict:
    """Load JSON file or return empty dict"""
    try:
        if file_path.exists():
            with open(file_path, 'r') as f:
                return json.load(f)
    except:
        pass
    return {}

def _save_json_file(file_path: Path, data: Dict) -> None:
    """Save data to JSON file"""
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)

if __name__ == "__main__":
    mcp.run(transport='stdio')