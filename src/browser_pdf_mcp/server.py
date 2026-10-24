"""
MCP Server for converting websites to PDF files using Playwright.
"""

import asyncio
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from browser_pdf_mcp import __version__

# Logging goes to stderr; stdout is reserved for the MCP protocol
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("browser-pdf-mcp")

NAVIGATION_TIMEOUT_MS = 60000

app = Server("browser-pdf-mcp", version=__version__)


def default_output_dir() -> Path:
    """Default output directory, overridable via BROWSER_PDF_OUTPUT_DIR."""
    env_dir = os.environ.get("BROWSER_PDF_OUTPUT_DIR")
    if env_dir:
        return Path(env_dir).expanduser()
    return Path.home() / "Downloads" / "mcp_pdfs"


def validate_url(url: str) -> tuple[bool, str]:
    """
    Validate that the URL is properly formatted.

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        result = urlparse(url)
        if not all([result.scheme, result.netloc]):
            return False, "Invalid URL: Missing scheme or domain"
        if result.scheme not in ["http", "https"]:
            return False, "Invalid URL: Only HTTP and HTTPS protocols are supported"
        return True, ""
    except Exception as e:
        return False, f"Invalid URL format: {str(e)}"


def sanitize_filename(filename: str) -> str:
    """
    Reduce a user-supplied filename to a safe basename ending in .pdf.

    Drops any directory components (so "../x" cannot escape the output
    directory) and replaces characters that are unsafe on common filesystems.
    """
    name = Path(filename.replace("\\", "/")).name
    if name.lower().endswith(".pdf"):
        name = name[:-4]
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    if not name:
        name = "page"
    return f"{name}.pdf"


def unique_path(path: Path) -> Path:
    """Return path, or path with a _1, _2, ... suffix if it already exists."""
    if not path.exists():
        return path
    counter = 1
    while True:
        candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


async def generate_pdf(
    url: str,
    output_path: str | None = None,
    filename: str | None = None
) -> dict[str, Any]:
    """
    Generate a PDF from a website using Playwright.

    Args:
        url: The website URL to convert
        output_path: Optional custom output directory
        filename: Optional custom filename (without extension)

    Returns:
        Dictionary with 'success', 'file_path', and optional 'error' keys
    """
    # Validate URL
    is_valid, error_msg = validate_url(url)
    if not is_valid:
        return {"success": False, "error": error_msg}

    # Determine output location
    if output_path:
        output_dir = Path(output_path).expanduser()
    else:
        output_dir = default_output_dir()

    # Create output directory if it doesn't exist
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return {"success": False, "error": f"Failed to create output directory: {str(e)}"}

    # Generate filename if not provided
    if not filename:
        # Use domain name as default filename
        parsed = urlparse(url)
        filename = parsed.netloc.replace("www.", "").replace(".", "_")

    # Never overwrite an existing PDF
    file_path = unique_path(output_dir / sanitize_filename(filename))

    try:
        async with async_playwright() as p:
            logger.info(f"Launching browser for URL: {url}")
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()

                # Wait for network idle so dynamic content is loaded; pages that
                # never go idle (long polling, analytics) fall back to the load event
                logger.info(f"Navigating to {url}")
                try:
                    await page.goto(url, wait_until="networkidle", timeout=NAVIGATION_TIMEOUT_MS)
                except PlaywrightTimeoutError:
                    logger.warning(f"Network never went idle for {url}, falling back to 'load'")
                    await page.goto(url, wait_until="load", timeout=NAVIGATION_TIMEOUT_MS)

                logger.info(f"Generating PDF: {file_path}")
                await page.pdf(
                    path=str(file_path),
                    format="A4",
                    print_background=True,
                    margin={
                        "top": "1cm",
                        "right": "1cm",
                        "bottom": "1cm",
                        "left": "1cm"
                    }
                )
            finally:
                await browser.close()

        logger.info(f"PDF generated successfully: {file_path}")
        return {
            "success": True,
            "file_path": str(file_path.absolute()),
            "url": url,
            "filename": file_path.name
        }

    except PlaywrightError as e:
        if "Executable doesn't exist" in str(e):
            # Point at this interpreter so the browser matches the installed Playwright version
            error_msg = (
                "Chromium is not installed for Playwright. "
                f"Run `{sys.executable} -m playwright install chromium` and try again."
            )
        else:
            error_msg = f"Playwright error: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="create_website_pdf",
            description=(
                "Convert a website to a PDF file. "
                "Captures the full scrollable content of the webpage, "
                "waits for network idle to ensure dynamic content is loaded, "
                "and saves the result as a multi-page A4 PDF. "
                "Existing files are never overwritten; a numeric suffix is added instead."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": (
                            "The full URL of the website to convert to PDF "
                            "(must include http:// or https://)"
                        )
                    },
                    "output_path": {
                        "type": "string",
                        "description": (
                            "Optional: Directory where the PDF should be saved. "
                            "Defaults to $BROWSER_PDF_OUTPUT_DIR or ~/Downloads/mcp_pdfs/"
                        )
                    },
                    "filename": {
                        "type": "string",
                        "description": (
                            "Optional: Filename for the PDF (without .pdf extension). "
                            "Defaults to the domain name."
                        )
                    }
                },
                "required": ["url"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls."""
    if name != "create_website_pdf":
        raise ValueError(f"Unknown tool: {name}")

    # Extract arguments
    url = arguments.get("url")
    output_path = arguments.get("output_path")
    filename = arguments.get("filename")

    if not url:
        return [TextContent(
            type="text",
            text="Error: URL is required"
        )]

    # Generate PDF
    result = await generate_pdf(url, output_path, filename)

    if result["success"]:
        response_text = (
            f"PDF generated successfully!\n\n"
            f"URL: {result['url']}\n"
            f"File: {result['file_path']}\n"
            f"Filename: {result['filename']}"
        )
    else:
        response_text = f"Failed to generate PDF: {result['error']}"

    return [TextContent(type="text", text=response_text)]


async def serve() -> None:
    """Run the MCP server over stdio."""
    logger.info("Starting Browser PDF MCP Server")
    logger.info(f"Default PDF output directory: {default_output_dir()}")

    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


def main() -> None:
    """Console script entry point."""
    asyncio.run(serve())


if __name__ == "__main__":
    main()
