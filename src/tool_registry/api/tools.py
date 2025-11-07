from typing import Any, Optional, Iterator
from fastapi import APIRouter, Request, HTTPException
from pathlib import Path
import json
from dataclasses import dataclass

router = APIRouter()


# Small helper dataclass to produce the standardized tool summary dict
@dataclass
class ToolSummary:
    key: str
    value: str
    props: dict

    def to_dict(self) -> dict:
        # Ensure props is a dict-like object
        props = self.props or {}
        return {
            self.key: self.value,
            "toolLabel": props.get("toolLabel", ""),
            "toolDescription": props.get("toolDescription", "")
        }


# Returns a list of all supported tools (each item contains `toolURI`, `toolLabel`, `toolDescription`).
@router.get("/", description="List all supported tools. Each item contains 'toolURI', 'toolLabel', and 'toolDescription'.")
async def get_all_tools():
    """
    Handle GET requests to retrieve a list of all supported tools.

    Returns:
        list[dict]: A list of dictionaries, each containing the 'toolURI', 'toolLabel',
        and 'toolDescription' of a supported tool.
    """
    return await get_tools()

# Returns a single tool matching `identifier
# Supports:
#  - `edc:fil.<...>` -> match by file type (`typeURI`)
#  - `edc:tool.<...>` -> match by tool URI (`toolURI`)
@router.get("/{identifier}", description="Retrieve a single tool matching the provided filter. Supports 'edc:fil.*' (typeURI) and 'edc:tool.*' (toolURI).")
# async def get_tools_by_identifier(request: Request, identifier: Optional[str] = None):
async def get_tools_by_identifier(identifier: str):
    """
    Handle GET requests to retrieve tools or identifier them based on a specific URI.

    This endpoint supports two routes:
    1. `/` - Returns a list of all tools.
    2. `/{identifier}` - Filters tools based on the provided `identifier` parameter.

    Args:
        request (Request): The incoming HTTP request object.
        identifier (Optional[str]): A string used to filter tools. It can start with:
            - "edc:fil." to filter by file type (typeURI).
            - "edc:tool." to filter by tool URI (toolURI).

    Returns:
        list[dict] or dict: A list of all tools if no identifier is provided, or a single
        tool matching the identifier criteria. Returns an empty dictionary if no match is found.
    """
    # if not identifier:
    #     return await get_tools()
    # if identifier.startswith("edc:fil."):
    #     return await find_tool(match_type="typeURI", match_value=identifier)

    if identifier.startswith("edc:tool."):
        results = await find_tool(match_type="toolURI", match_value=identifier)
        if not results:
            raise HTTPException(status_code=404, detail="Tool not found")
        return results
    else:
        raise HTTPException(status_code=400, detail="Invalid identifier format")


@router.get("/search", Description="Search for tools given query parameters.")
async def search_tools(toolURI: Optional[str] = None, typeURI: Optional[str] = None) -> list[Any]:
    """
    Search for tools based on provided query parameters.

    Args:
        toolURI (Optional[str]): The tool URI to search for.
        typeURI (Optional[str]): The type URI to search for.

    Returns:
        list[dict]: A list of ToolSummary dicts matching the search criteria.
    """
    matches: list[Any] = []

    if toolURI:
        result = await find_tool(match_type="toolURI", match_value=toolURI)
        if result:
            matches.append(result)

    if typeURI:
        result = await find_tool(match_type="typeURI", match_value=typeURI)
        if result:
            matches.append(result)

    if not matches:
        raise HTTPException(status_code=404, detail="No matching tools found")

    return matches


async def get_tools() -> list[Any]:
    tools = []
    for data in _iter_tool_data():
        tool_uri = data.get("toolURI")
        props = data.get("toolProperties", {})
        tool_label = props.get("toolLabel") or ""
        tool_description = props.get("toolDescription") or ""
        if tool_uri:
            # Use ToolSummary to keep the output format consistent
            tools.append(ToolSummary("toolURI", tool_uri, props).to_dict())
    return tools


async def find_tool(match_type: str, match_value: str) -> dict:
    """
    Generic finder for tools.

    match_type: "toolURI" or "typeURI"
    match_value: value to match (e.g. "edc:tool.443..." or "edc:fil.0CC5...")
    """
    for data in _iter_tool_data():
        if match_type == "toolURI":
            if data.get("toolURI") == match_value:
                props = data.get("toolProperties", {})
                return ToolSummary("toolURI", match_value, props).to_dict()

        elif match_type == "typeURI":
            type_entries = data.get("typeURI", [])
            for entry in type_entries:
                entry_val = entry.get("typeURI") if isinstance(entry, dict) else entry
                if entry_val == match_value:
                    props = data.get("toolProperties", {})
                    return ToolSummary("typeURI", match_value, props).to_dict()

    return {}


    # New endpoint: find tools that accept a given input extension
@router.get("/input/{ext}", description="List tools that accept the given input file extension (e.g. 'csv', 'tsv').")
async def get_tools_by_input_extension(ext: str) -> list[Any]:
    """Return a list of ToolSummary dicts for tools that declare an input with the provided extension.

    The extension comparison is case-insensitive and a leading dot is ignored (so '.csv' and 'csv' are treated the same).
    """
    norm = (ext or "").lower().lstrip('.')
    matches: list[Any] = []

    for data in _iter_tool_data():
        filetypes = data.get("fileTypes", {})
        inputs = filetypes.get("input", []) if isinstance(filetypes, dict) else []
        for item in inputs:
            item_ext = (item.get("extension") or "").lower().lstrip('.') if isinstance(item, dict) else ""
            if item_ext == norm:
                tool_uri = data.get("toolURI")
                props = data.get("toolProperties", {})
                if tool_uri:
                    matches.append(ToolSummary("toolURI", tool_uri, props).to_dict())
                    break  # one match per tool is enough
    return matches


def _get_supported_tools_base() -> Path:
    # lazy import to avoid circular import with `src.main`
    from src.main import app_settings
    base = Path(app_settings.SUPPORTED_TOOLS_DIR)
    print("SUPPORTED_TOOLS_DIR", base)
    return base


def _iter_tool_data() -> Iterator[dict]:
    """Yield parsed JSON dicts for each .json tool file in the supported-tools dir."""
    base = _get_supported_tools_base()
    if not base.exists() or not base.is_dir():
        return
    for path in sorted(base.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        yield data
