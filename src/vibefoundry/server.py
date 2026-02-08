"""
FastAPI backend server for VibeFoundry IDE
"""

import os
import asyncio
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from vibefoundry.runner import discover_scripts, run_script, setup_project_structure, ScriptResult
from vibefoundry.metadata import generate_metadata
from vibefoundry.watcher import FileWatcher


# Global state
class AppState:
    project_folder: Optional[Path] = None
    watcher: Optional[FileWatcher] = None
    websocket_clients: list[WebSocket] = []


state = AppState()


# Request/Response models
class FolderSelectRequest(BaseModel):
    path: str


class RunScriptsRequest(BaseModel):
    scripts: list[str]


class ScriptResultResponse(BaseModel):
    script_path: str
    success: bool
    stdout: str
    stderr: str
    return_code: int
    error: Optional[str] = None
    timed_out: bool = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Check for project folder from environment
    project_path = os.environ.get("VIBEFOUNDRY_PROJECT_PATH")
    if project_path:
        folder = Path(project_path)
        if folder.exists() and folder.is_dir():
            state.project_folder = folder
            setup_project_structure(folder)
            generate_metadata(folder)
            state.watcher = FileWatcher(folder)
            state.watcher.scan_initial_state()

    yield
    # Cleanup
    if state.watcher:
        state.watcher.stop()


# Create FastAPI app
app = FastAPI(
    title="VibeFoundry IDE",
    version="0.1.0",
    lifespan=lifespan
)

# CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_static_dir() -> Path:
    """Get the path to bundled static files"""
    return Path(__file__).parent / "static"


# API Routes

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "project_folder": str(state.project_folder) if state.project_folder else None}


@app.post("/api/folder/select")
async def select_folder(request: FolderSelectRequest):
    """Set the project folder and initialize structure"""
    folder_path = Path(request.path)

    if not folder_path.exists():
        raise HTTPException(status_code=400, detail="Folder does not exist")

    if not folder_path.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")

    state.project_folder = folder_path

    # Setup folder structure
    folders = setup_project_structure(folder_path)

    # Stop existing watcher
    if state.watcher:
        state.watcher.stop()

    # Start new watcher
    state.watcher = FileWatcher(
        folder_path,
        on_data_change=lambda: asyncio.create_task(notify_data_change()),
        on_script_change=lambda p: asyncio.create_task(notify_script_change(p))
    )
    state.watcher.scan_initial_state()

    # Generate initial metadata
    generate_metadata(folder_path)

    return {
        "success": True,
        "name": folder_path.name,
        "project_folder": str(folder_path),
        "folders": {k: str(v) for k, v in folders.items()}
    }


@app.get("/api/folder/info")
async def get_folder_info():
    """Get current project folder info"""
    if not state.project_folder:
        return {"project_folder": None}

    return {
        "project_folder": str(state.project_folder),
        "name": state.project_folder.name
    }


@app.get("/api/scripts")
async def list_scripts():
    """List available scripts"""
    if not state.project_folder:
        raise HTTPException(status_code=400, detail="No project folder selected")

    scripts_folder = state.project_folder / "app_folder" / "scripts"
    scripts = discover_scripts(scripts_folder)

    return {
        "scripts": [
            {
                "path": str(s),
                "relative_path": str(s.relative_to(scripts_folder)),
                "name": s.name
            }
            for s in scripts
        ]
    }


@app.post("/api/scripts/run")
async def run_scripts(request: RunScriptsRequest):
    """Run selected scripts"""
    if not state.project_folder:
        raise HTTPException(status_code=400, detail="No project folder selected")

    results: list[ScriptResultResponse] = []

    for script_path in request.scripts:
        result = run_script(Path(script_path), state.project_folder)
        results.append(ScriptResultResponse(
            script_path=result.script_path,
            success=result.success,
            stdout=result.stdout,
            stderr=result.stderr,
            return_code=result.return_code,
            error=result.error,
            timed_out=result.timed_out
        ))

    # Regenerate metadata after running scripts
    generate_metadata(state.project_folder)

    return {"results": [r.model_dump() for r in results]}


@app.post("/api/metadata/generate")
async def regenerate_metadata():
    """Force metadata regeneration"""
    if not state.project_folder:
        raise HTTPException(status_code=400, detail="No project folder selected")

    input_meta, output_meta = generate_metadata(state.project_folder)

    return {
        "success": True,
        "input_metadata": input_meta,
        "output_metadata": output_meta
    }


@app.get("/api/watch/check")
async def check_for_changes():
    """Manually check for file changes"""
    if not state.watcher:
        return {"changes": False}

    input_changes, output_changes, script_changes = state.watcher.check_once()

    has_changes = bool(input_changes or output_changes or script_changes)

    if input_changes or output_changes:
        generate_metadata(state.project_folder)

    return {
        "changes": has_changes,
        "input_changes": [{"path": c.path, "type": c.change_type} for c in input_changes],
        "output_changes": [{"path": c.path, "type": c.change_type} for c in output_changes],
        "script_changes": [{"path": c.path, "type": c.change_type} for c in script_changes]
    }


# Filesystem browsing endpoints

@app.get("/api/fs/home")
async def get_home_directory():
    """Get user's home directory"""
    return {"path": str(Path.home())}


@app.get("/api/fs/list")
async def list_directory(path: str = ""):
    """List directories at a given path (for folder picker)"""
    if not path:
        path = str(Path.home())

    target = Path(path)

    if not target.exists():
        raise HTTPException(status_code=404, detail="Path does not exist")

    if not target.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")

    folders = []
    try:
        for item in sorted(target.iterdir()):
            # Only show directories, skip hidden files
            if item.is_dir() and not item.name.startswith('.'):
                folders.append({
                    "name": item.name,
                    "path": str(item)
                })
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")

    return {
        "current": str(target),
        "parent": str(target.parent) if target.parent != target else None,
        "folders": folders
    }


def build_file_tree(path: Path, base_path: Path) -> dict:
    """Build a file tree recursively"""
    rel_path = str(path.relative_to(base_path))
    is_file = path.is_file()
    node = {
        "name": path.name,
        "path": rel_path if rel_path != "." else path.name,
        "isDirectory": not is_file,
        "extension": path.suffix if is_file else None,
        "lastModified": path.stat().st_mtime if is_file else None,
    }

    if path.is_dir():
        children = []
        try:
            for item in sorted(path.iterdir()):
                # Skip hidden files
                if item.name.startswith('.'):
                    continue
                children.append(build_file_tree(item, base_path))
        except PermissionError:
            pass
        node["children"] = children

    return node


@app.get("/api/files/tree")
async def get_file_tree():
    """Get the complete file tree for the project"""
    if not state.project_folder:
        raise HTTPException(status_code=400, detail="No project folder selected")

    tree = build_file_tree(state.project_folder, state.project_folder)
    return {"tree": tree}


@app.get("/api/files/read")
async def read_file(path: str):
    """Read a file's content"""
    import pandas as pd

    if not state.project_folder:
        raise HTTPException(status_code=400, detail="No project folder selected")

    file_path = state.project_folder / path

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    if not file_path.is_file():
        raise HTTPException(status_code=400, detail="Path is not a file")

    # Security check - ensure path is within project folder
    try:
        file_path.resolve().relative_to(state.project_folder.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    # Determine file type and read accordingly
    ext = file_path.suffix.lower()
    binary_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.webp', '.pdf', '.zip', '.tar', '.gz'}
    dataframe_extensions = {'.csv', '.xlsx', '.xls'}

    if ext in dataframe_extensions:
        # Parse as dataframe and return columns + data
        # Virtual scrolling on frontend allows loading all rows
        try:
            if ext == '.csv':
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)

            # Convert to JSON-serializable format
            df = df.fillna('')
            columns = df.columns.tolist()
            data = df.to_dict(orient='records')

            return {
                "type": "dataframe",
                "columns": columns,
                "data": data,
                "filename": file_path.name,
                "rowCount": len(data),
                "truncated": False
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to parse file: {str(e)}")

    elif ext in binary_extensions:
        import base64
        content = base64.b64encode(file_path.read_bytes()).decode('utf-8')
        return {"content": content, "encoding": "base64", "filename": file_path.name}
    else:
        try:
            content = file_path.read_text(encoding='utf-8')
            return {"content": content, "encoding": "utf-8", "filename": file_path.name}
        except UnicodeDecodeError:
            import base64
            content = base64.b64encode(file_path.read_bytes()).decode('utf-8')
            return {"content": content, "encoding": "base64", "filename": file_path.name}


class WriteFileRequest(BaseModel):
    path: str
    content: str


@app.post("/api/files/write")
async def write_file(request: WriteFileRequest):
    """Write content to a file"""
    if not state.project_folder:
        raise HTTPException(status_code=400, detail="No project folder selected")

    file_path = state.project_folder / request.path

    # Security check - ensure path is within project folder
    try:
        file_path.resolve().relative_to(state.project_folder.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    # Create parent directories if needed
    file_path.parent.mkdir(parents=True, exist_ok=True)

    file_path.write_text(request.content, encoding='utf-8')

    return {"success": True, "path": request.path}


# Codespace sync endpoints

FORBIDDEN_SYNC_EXTENSIONS = {'.pdf', '.csv', '.xlsx', '.xls', '.xlsm', '.xlsb', '.ppt', '.pptx'}
PROTECTED_FILES = {'sync_server.py', 'metadatafarmer.py', 'CLAUDE.md'}
PROTECTED_DIRS = {'meta_data'}


class SyncPullRequest(BaseModel):
    codespace_url: str
    last_sync: dict = {}


class SyncPushRequest(BaseModel):
    codespace_url: str


@app.post("/api/sync/pull")
async def sync_pull_scripts(request: SyncPullRequest):
    """Pull scripts from codespace and save locally"""
    if not state.project_folder:
        raise HTTPException(status_code=400, detail="No project folder selected")

    synced_files = []
    new_last_sync = dict(request.last_sync)

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Get scripts list from codespace
        try:
            response = await client.get(f"{request.codespace_url}/scripts")
            response.raise_for_status()
            scripts = response.json().get("scripts", [])
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Failed to fetch scripts: {str(e)}")

        # Get or create local app_folder/scripts
        app_folder = state.project_folder / "app_folder"
        app_folder.mkdir(parents=True, exist_ok=True)

        for script in scripts:
            file_path = script.get("path") or script.get("name")
            server_mod = int(script.get("modified", 0))
            local_mod = int(request.last_sync.get(file_path, 0))

            # Download if new or modified
            if local_mod < server_mod:
                try:
                    script_response = await client.get(
                        f"{request.codespace_url}/scripts/{file_path}"
                    )
                    script_response.raise_for_status()
                    script_data = script_response.json()

                    # Write to local file
                    local_path = app_folder / file_path
                    local_path.parent.mkdir(parents=True, exist_ok=True)
                    local_path.write_text(script_data.get("content", ""), encoding="utf-8")

                    new_last_sync[file_path] = server_mod
                    synced_files.append(file_path)
                except Exception as e:
                    print(f"Failed to sync {file_path}: {e}")
            else:
                new_last_sync[file_path] = local_mod

    return {"synced_files": synced_files, "last_sync": new_last_sync}


@app.post("/api/sync/push")
async def sync_push_scripts(request: SyncPushRequest):
    """Push local scripts to codespace"""
    if not state.project_folder:
        raise HTTPException(status_code=400, detail="No project folder selected")

    pushed_files = []
    app_folder = state.project_folder / "app_folder"

    if not app_folder.exists():
        return {"pushed_files": []}

    def collect_files(folder: Path, prefix: str = "") -> list:
        """Recursively collect files to push"""
        files = []
        try:
            for item in folder.iterdir():
                if item.name.startswith('.'):
                    continue
                if item.is_dir():
                    if item.name not in PROTECTED_DIRS and item.name != "node_modules":
                        sub_prefix = f"{prefix}/{item.name}" if prefix else item.name
                        files.extend(collect_files(item, sub_prefix))
                else:
                    if item.name in PROTECTED_FILES:
                        continue
                    ext = item.suffix.lower()
                    if ext in FORBIDDEN_SYNC_EXTENSIONS:
                        continue
                    rel_path = f"{prefix}/{item.name}" if prefix else item.name
                    try:
                        content = item.read_text(encoding="utf-8")
                        files.append({"path": rel_path, "content": content})
                    except Exception:
                        pass
        except PermissionError:
            pass
        return files

    files_to_push = collect_files(app_folder)

    async with httpx.AsyncClient(timeout=30.0) as client:
        for file in files_to_push:
            try:
                response = await client.post(
                    f"{request.codespace_url}/scripts/{file['path']}",
                    json={"content": file["content"]}
                )
                response.raise_for_status()
                pushed_files.append(file["path"])
            except Exception as e:
                print(f"Failed to push {file['path']}: {e}")

    return {"pushed_files": pushed_files}


@app.post("/api/sync/metadata")
async def sync_metadata_to_codespace(request: SyncPushRequest):
    """Push local metadata to codespace"""
    if not state.project_folder:
        raise HTTPException(status_code=400, detail="No project folder selected")

    meta_folder = state.project_folder / "app_folder" / "meta_data"

    input_metadata = ""
    output_metadata = ""

    input_file = meta_folder / "input_metadata.txt"
    output_file = meta_folder / "output_metadata.txt"

    if input_file.exists():
        input_metadata = input_file.read_text(encoding="utf-8")
    if output_file.exists():
        output_metadata = output_file.read_text(encoding="utf-8")

    if not input_metadata and not output_metadata:
        return {"success": True, "synced": False}

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{request.codespace_url}/metadata",
                json={
                    "input_metadata": input_metadata,
                    "output_metadata": output_metadata
                }
            )
            response.raise_for_status()
            return {"success": True, "synced": True}
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Failed to sync metadata: {str(e)}")


@app.post("/api/sync/full")
async def sync_full(request: SyncPullRequest):
    """Full bidirectional sync: pull scripts, push metadata"""
    if not state.project_folder:
        raise HTTPException(status_code=400, detail="No project folder selected")

    # Pull scripts
    pull_result = await sync_pull_scripts(request)

    # Push metadata
    push_request = SyncPushRequest(codespace_url=request.codespace_url)
    try:
        metadata_result = await sync_metadata_to_codespace(push_request)
        metadata_synced = metadata_result.get("synced", False)
    except Exception:
        metadata_synced = False

    return {
        "scripts_sync": {
            "synced_files": pull_result["synced_files"],
            "last_sync": pull_result["last_sync"]
        },
        "metadata_sync": metadata_synced
    }


# GitHub OAuth endpoints (Device Flow - no client secret needed)

class DeviceCodeRequest(BaseModel):
    client_id: str
    scope: str = ""


class TokenPollRequest(BaseModel):
    client_id: str
    device_code: str
    grant_type: str = "urn:ietf:params:oauth:grant-type:device_code"


@app.post("/api/github/device-code")
async def github_device_code(request: DeviceCodeRequest):
    """Initiate GitHub device flow authentication"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://github.com/login/device/code",
            data={
                "client_id": request.client_id,
                "scope": request.scope,
            },
            headers={"Accept": "application/json"},
        )

        return JSONResponse(
            status_code=response.status_code if response.is_success else response.status_code,
            content=response.json()
        )


@app.post("/api/github/token")
async def github_token(request: TokenPollRequest):
    """Poll for GitHub access token"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": request.client_id,
                "device_code": request.device_code,
                "grant_type": request.grant_type,
            },
            headers={"Accept": "application/json"},
        )

        return JSONResponse(
            status_code=200,
            content=response.json()
        )


# WebSocket for real-time updates

@app.websocket("/ws/watch")
async def websocket_watch(websocket: WebSocket):
    """WebSocket for file change notifications"""
    await websocket.accept()
    state.websocket_clients.append(websocket)

    try:
        while True:
            # Keep connection alive, wait for messages
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                # Handle any incoming messages (e.g., ping)
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # Send keepalive
                await websocket.send_text('{"type": "keepalive"}')
    except WebSocketDisconnect:
        state.websocket_clients.remove(websocket)
    except Exception:
        if websocket in state.websocket_clients:
            state.websocket_clients.remove(websocket)


async def notify_data_change():
    """Notify all WebSocket clients of data change"""
    if state.project_folder:
        generate_metadata(state.project_folder)

    message = '{"type": "data_change"}'
    disconnected = []

    for client in state.websocket_clients:
        try:
            await client.send_text(message)
        except Exception:
            disconnected.append(client)

    for client in disconnected:
        state.websocket_clients.remove(client)


async def notify_script_change(script_path: Path):
    """Notify all WebSocket clients of script change"""
    message = f'{{"type": "script_change", "path": "{script_path}"}}'
    disconnected = []

    for client in state.websocket_clients:
        try:
            await client.send_text(message)
        except Exception:
            disconnected.append(client)

    for client in disconnected:
        state.websocket_clients.remove(client)


# Serve static files (React app)

@app.get("/")
async def serve_index():
    """Serve the React app index.html"""
    static_dir = get_static_dir()
    index_path = static_dir / "index.html"

    if not index_path.exists():
        return JSONResponse(
            status_code=503,
            content={
                "error": "Frontend not built",
                "message": "Run 'npm run build' in the frontend directory first"
            }
        )

    return FileResponse(index_path)


# Mount static files for assets (at module load time)
_static_dir = get_static_dir()
_assets_dir = _static_dir / "assets"
if _assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")


def create_app() -> FastAPI:
    """Factory function for creating the app"""
    return app
