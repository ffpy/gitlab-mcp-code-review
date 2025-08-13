import os
import logging
import toml
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
import gitlab
import fnmatch
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP, Context

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Load configuration from TOML file
try:
    with open("config.toml", "r") as f:
        config = toml.load(f)
except FileNotFoundError:
    config = {}
except Exception as e:
    logging.error(f"Error loading config.toml: {e}")
    config = {}

@asynccontextmanager
async def gitlab_lifespan(server: FastMCP) -> AsyncIterator[gitlab.Gitlab]:
    """Manage GitLab connection details"""
    host = os.getenv("GITLAB_HOST", "gitlab.com")
    token = os.getenv("GITLAB_TOKEN", "")
    
    if not token:
        logger.error("Missing required environment variable: GITLAB_TOKEN")
        raise ValueError(
            "Missing required environment variable: GITLAB_TOKEN. "
            "Please set this in your environment or .env file."
        )
    
    gl = gitlab.Gitlab(f"https://{host}", private_token=token, timeout=120)
    try:
        logger.info("GitLab client initialized")
        yield gl
    except Exception as e:
        logger.error(f"An error occurred during GitLab client initialization: {e}")
        raise
    finally:
        logger.info("GitLab client session closed.")

# Create MCP server
mcp = FastMCP(
    "GitLab MCP for Code Review",
    lifespan=gitlab_lifespan,
    dependencies=["python-dotenv", "requests", "python-gitlab"]
)

def is_path_excluded(file_path: str, patterns: List[str]) -> bool:
    """Check if a file path matches any of the exclusion patterns."""
    for pattern in patterns:
        if pattern.endswith('/'):
            if file_path.startswith(pattern) or f"/{pattern}" in file_path:
                return True
        elif fnmatch.fnmatch(file_path, pattern):
            return True
    return False

@mcp.tool()
def fetch_merge_request(ctx: Context, project_id: str, merge_request_iid: str) -> Dict[str, Any]:
    """
    Fetch a GitLab merge request and its contents.
    
    Args:
        project_id: The GitLab project ID or URL-encoded path
        merge_request_iid: The merge request IID (project-specific ID)
    Returns:
        Dict containing the merge request information
    """
    gl = ctx.request_context.lifespan_context
    project = gl.projects.get(project_id)
    mr = project.mergerequests.get(merge_request_iid)

    # 精简 merge_request 信息
    mr_data = mr.asdict()
    slim_mr = {
        "id": mr_data.get("id"),
        "iid": mr_data.get("iid"),
        "project_id": mr_data.get("project_id"),
        "title": mr_data.get("title"),
        "description": mr_data.get("description"),
        "state": mr_data.get("state"),
        "author": mr_data.get("author", {}).get("name"),
        "source_branch": mr_data.get("source_branch"),
        "target_branch": mr_data.get("target_branch"),
    }

    # 获取并过滤 changes
    original_changes_data = mr.changes()
    all_changes = original_changes_data.get("changes", [])

    exclude_patterns = config.get("exclude_patterns", [])

    filtered_changes_list = []
    for change in all_changes:
        file_path = change.get("new_path")
        if not is_path_excluded(file_path, exclude_patterns):
            slim_change = {
                "new_path": change.get("new_path"),
                "old_path": change.get("old_path"),
                "new_file": change.get("new_file"),
                "renamed_file": change.get("renamed_file"),
                "deleted_file": change.get("deleted_file"),
                "diff": change.get("diff")
            }
            filtered_changes_list.append(slim_change)
    
    # 创建一个只包含必要字段的精简版 changes 对象
    slim_changes_obj = {
        "diff_refs": original_changes_data.get("diff_refs"),
        "changes": filtered_changes_list
    }

    # 精简 commits
    commits = [
        {
            "id": c.id,
            "short_id": c.short_id,
            "title": c.title,
            "author_name": c.author_name,
        }
        for c in mr.commits(all=True)
    ]

    def slim_note(note):
        if not isinstance(note, dict):
            note = note.asdict()
        author = note.get("author", {})
        return {
            "id": note.get("id"),
            "type": note.get("type"),
            "body": note.get("body"),
            "system": note.get("system"),
            "author": author.get("name"),
            "position": note.get("position", {}),
        }

    # 精简 discussions 和其下的 notes
    all_discussions = mr.discussions.list(all=True)

    discussions = []
    for d in all_discussions:
        # d.attributes['notes'] 包含了该 discussion 下的所有 note 信息
        slim_notes_list = [slim_note(n) for n in d.attributes.get('notes', [])]
        discussions.append({
            "id": d.id,
            "individual_note": d.individual_note,
            "notes": slim_notes_list
        })

    return {
        "merge_request": slim_mr,
        "changes": slim_changes_obj,
        "commits": commits,
        "discussions": discussions,
    }

@mcp.tool()
def compare_versions(ctx: Context, project_id: str, from_sha: str, to_sha: str) -> Dict[str, Any]:
    """
    Compare two commits/branches/tags to see the differences between them.
    
    Args:
        project_id: The GitLab project ID or URL-encoded path
        from_sha: The source commit/branch/tag
        to_sha: The target commit/branch/tag
    Returns:
        Dict containing the comparison information
    """
    gl = ctx.request_context.lifespan_context
    project = gl.projects.get(project_id)
    
    try:
        result = project.repository_compare(from_sha, to_sha)
    except Exception as e:
        logger.error(f"Failed to compare {from_sha} and {to_sha}: {e}")
        result = {}
    
    return result

@mcp.tool()
def add_merge_request_comment(ctx: Context, project_id: str, merge_request_iid: str, body: str) -> Dict[str, Any]:
    """
    Add a general comment to a merge request.
    
    Args:
        project_id: The GitLab project ID or URL-encoded path
        merge_request_iid: The merge request IID (project-specific ID)
        body: The comment text
    Returns:
        Dict containing the created comment information
    """
    gl = ctx.request_context.lifespan_context
    project = gl.projects.get(project_id)
    mr = project.mergerequests.get(merge_request_iid)
    
    note = mr.notes.create({'body': body})
    
    return note.asdict()

@mcp.tool()
def add_merge_request_discussion(ctx: Context, project_id: str, merge_request_iid: str, body: str, position: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add a discussion to a merge request at a specific position in a file.
    
    Args:
        project_id: The GitLab project ID or URL-encoded path
        merge_request_iid: The merge request IID (project-specific ID)
        body: The discussion text
        position: Position data for the discussion.
            Example:
            {
                "position_type": "text", // Required, Type of the position reference. Allowed values: text, image, or file. file introduced in GitLab 16.4.
                "base_sha": "...", // Required, Base commit SHA in the source branch.
                "start_sha": "...", // Required, SHA referencing commit in target branch.
                "head_sha": "...", // Required, SHA referencing HEAD of this merge request.
                "old_path": "path/to/file.py", // Required, File path before change.
                "new_path": "path/to/file.py", // Required, File path after change.
                "new_line": 15, // For text diff notes, the line number after change.
                "old_line": 10 // For text diff notes, the line number before change.
            }
    Returns:
        Dict containing the created discussion information
    """
    gl = ctx.request_context.lifespan_context
    project = gl.projects.get(project_id)
    mr = project.mergerequests.get(merge_request_iid)
    
    discussion_data = {'body': body, 'position': position}
    logger.info(f"Creating discussion with data: {discussion_data}")
    
    try:
        discussion = mr.discussions.create(discussion_data)
        logger.info(f"Successfully created discussion: {discussion.id}")
        return discussion.asdict()
    except gitlab.exceptions.GitlabHttpError as e:
        logger.error(f"GitLab API error while creating discussion: {e.error_message}", exc_info=True)
        logger.error(f"Response body: {e.response_body}")
        raise e


@mcp.tool()
def reply_to_merge_request_discussion(ctx: Context, project_id: str, merge_request_iid: str, discussion_id: str, body: str) -> Dict[str, Any]:
    """
    Reply to a merge request discussion.
    
    Args:
        project_id: The GitLab project ID or URL-encoded path
        merge_request_iid: The merge request IID (project-specific ID)
        discussion_id: The ID of the discussion to reply to
        body: The reply text
    Returns:
        Dict containing the created note information
    """
    gl = ctx.request_context.lifespan_context
    project = gl.projects.get(project_id)
    mr = project.mergerequests.get(merge_request_iid)
    discussion = mr.discussions.get(discussion_id)
    
    note = discussion.notes.create({'body': body})
    
    return note.asdict()


@mcp.tool()
def resolve_merge_request_discussion(ctx: Context, project_id: str, merge_request_iid: str, discussion_id: str, resolved: bool = True) -> Dict[str, Any]:
    """
    Resolve or unresolve a merge request discussion.
    
    Args:
        project_id: The GitLab project ID or URL-encoded path
        merge_request_iid: The merge request IID (project-specific ID)
        discussion_id: The ID of the discussion
        resolved: True to resolve, False to unresolve
    Returns:
        Dict containing the updated discussion information
    """
    gl = ctx.request_context.lifespan_context
    project = gl.projects.get(project_id)
    mr = project.mergerequests.get(merge_request_iid)
    discussion = mr.discussions.get(discussion_id)
    
    discussion.resolved = resolved
    discussion.save()
    
    return discussion.asdict()


@mcp.tool()
def delete_merge_request_discussion(ctx: Context, project_id: str, merge_request_iid: str, discussion_id: str) -> Dict[str, Any]:
    """
    Delete a merge request discussion.
    
    Args:
        project_id: The GitLab project ID or URL-encoded path
        merge_request_iid: The merge request IID (project-specific ID)
        discussion_id: The ID of the discussion to delete
    Returns:
        Dict containing the status of the deletion
    """
    gl = ctx.request_context.lifespan_context
    project = gl.projects.get(project_id)
    mr = project.mergerequests.get(merge_request_iid)
    discussion = mr.discussions.get(discussion_id)
    
    # To delete a discussion, we delete its first note.
    # If the discussion only has one note, the discussion will be deleted.
    if discussion.notes:
        first_note_id = discussion.notes[0]['id']
        discussion.notes.delete(first_note_id)
        return {"status": "success", "deleted_note_id": first_note_id}
    
    return {"status": "failed", "message": "Discussion has no notes to delete."}

@mcp.tool()
def approve_merge_request(ctx: Context, project_id: str, merge_request_iid: str, approvals_required: Optional[int] = None) -> Dict[str, Any]:
    """
    Approve a merge request.
    
    Args:
        project_id: The GitLab project ID or URL-encoded path
        merge_request_iid: The merge request IID (project-specific ID)
        approvals_required: Optional number of required approvals to set
    Returns:
        Dict containing the approval information
    """
    gl = ctx.request_context.lifespan_context
    project = gl.projects.get(project_id)
    mr = project.mergerequests.get(merge_request_iid)
    
    mr.approve()
    
    if approvals_required is not None:
        mr.approvals.post({'approvals_required': approvals_required})
        
    return mr.asdict()

@mcp.tool()
def unapprove_merge_request(ctx: Context, project_id: str, merge_request_iid: str) -> Dict[str, Any]:
    """
    Unapprove a merge request.
    
    Args:
        project_id: The GitLab project ID or URL-encoded path
        merge_request_iid: The merge request IID (project-specific ID)
    Returns:
        Dict containing the unapproval information
    """
    gl = ctx.request_context.lifespan_context
    project = gl.projects.get(project_id)
    mr = project.mergerequests.get(merge_request_iid)
    
    try:
        mr.unapprove()
    except Exception as e:
        logger.error(f"Failed to unapprove merge request {merge_request_iid}: {e}")
    
    return mr.asdict()

@mcp.tool()
def get_project_merge_requests(ctx: Context, project_id: str, state: str = "all", limit: int = 20) -> List[Dict[str, Any]]:
    """
    Get all merge requests for a project.
    
    Args:
        project_id: The GitLab project ID or URL-encoded path
        state: Filter merge requests by state (all, opened, closed, merged, or locked)
        limit: Maximum number of merge requests to return
    Returns:
        List of merge request objects
    """
    gl = ctx.request_context.lifespan_context
    project = gl.projects.get(project_id)
    
    mrs = project.mergerequests.list(state=state, per_page=limit)
    
    return [mr.asdict() for mr in mrs]

@mcp.tool()
def search_projects(ctx: Context, project_name: str = None) -> List[Dict[str, Any]]:
    """
    Search for GitLab projects by name.

    Args:
        project_name: The name of the project to search for. If None, returns all projects.
    Returns:
        A list of projects matching the search criteria.
    """
    gl = ctx.request_context.lifespan_context
    
    projects = gl.projects.list(search=project_name)
    
    return [p.asdict() for p in projects]

if __name__ == "__main__":
    try:
        logger.info("Starting GitLab Review MCP server")
        # Initialize and run the server
        mcp.run(transport='stdio')
    except Exception as e:
        logger.error(f"Failed to start MCP server: {str(e)}")
        raise 
