import os
import logging
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
import gitlab
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP, Context

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

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
    
    gl = gitlab.Gitlab(f"https://{host}", private_token=token)
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
    
    return {
        "merge_request": mr.asdict(),
        "changes": mr.changes(),
        "commits": [c.asdict() for c in mr.commits(all=True)],
        "notes": [n.asdict() for n in mr.notes.list(all=True)]
    }

@mcp.tool()
def fetch_merge_request_diff(ctx: Context, project_id: str, merge_request_iid: str, file_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch the diff for a specific file in a merge request, or all files if none specified.
    
    Args:
        project_id: The GitLab project ID or URL-encoded path
        merge_request_iid: The merge request IID (project-specific ID)
        file_path: Optional specific file path to get diff for
    Returns:
        Dict containing the diff information
    """
    gl = ctx.request_context.lifespan_context
    project = gl.projects.get(project_id)
    mr = project.mergerequests.get(merge_request_iid)
    
    changes = mr.changes()
    files = changes.get("changes", [])
    
    if file_path:
        files = [f for f in files if f.get("new_path") == file_path or f.get("old_path") == file_path]
        if not files:
            raise ValueError(f"File '{file_path}' not found in the merge request changes")
            
    return {
        "merge_request_iid": merge_request_iid,
        "files": files
    }

@mcp.tool()
def fetch_commit_diff(ctx: Context, project_id: str, commit_sha: str, file_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch the diff for a specific commit, or for a specific file in that commit.
    
    Args:
        project_id: The GitLab project ID or URL-encoded path
        commit_sha: The commit SHA
        file_path: Optional specific file path to get diff for
    Returns:
        Dict containing the diff information
    """
    gl = ctx.request_context.lifespan_context
    project = gl.projects.get(project_id)
    commit = project.commits.get(commit_sha)
    
    try:
        diff_info = commit.diff()
    except Exception as e:
        logger.error(f"Failed to get diff for commit {commit_sha}: {e}")
        diff_info = []
    
    if file_path:
        diff_info = [d for d in diff_info if d.get("new_path") == file_path or d.get("old_path") == file_path]
        if not diff_info:
            raise ValueError(f"File '{file_path}' not found in the commit diff")
            
    return {
        "commit": commit.asdict(),
        "diffs": diff_info
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
                "position_type": "text",
                "base_sha": "...",
                "start_sha": "...",
                "head_sha": "...",
                "old_path": "path/to/file.py",
                "new_path": "path/to/file.py",
                "new_line": 15
            }
    Returns:
        Dict containing the created discussion information
    """
    gl = ctx.request_context.lifespan_context
    project = gl.projects.get(project_id)
    mr = project.mergerequests.get(merge_request_iid)
    
    discussion = mr.discussions.create({'body': body, 'position': position})
    
    return discussion.asdict()

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
