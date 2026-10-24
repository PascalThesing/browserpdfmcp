"""
Tests for the Browser PDF MCP Server.
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from browser_pdf_mcp.server import (
    app,
    default_output_dir,
    generate_pdf,
    sanitize_filename,
    unique_path,
    validate_url,
)


class TestURLValidation:
    """Tests for URL validation."""

    def test_valid_http_url(self):
        """Test that valid HTTP URLs are accepted."""
        is_valid, error = validate_url("http://example.com")
        assert is_valid is True
        assert error == ""

    def test_valid_https_url(self):
        """Test that valid HTTPS URLs are accepted."""
        is_valid, error = validate_url("https://example.com")
        assert is_valid is True
        assert error == ""

    def test_valid_url_with_path(self):
        """Test that URLs with paths are accepted."""
        is_valid, error = validate_url("https://example.com/path/to/page")
        assert is_valid is True
        assert error == ""

    def test_valid_url_with_query(self):
        """Test that URLs with query parameters are accepted."""
        is_valid, error = validate_url("https://example.com?param=value")
        assert is_valid is True
        assert error == ""

    def test_invalid_url_no_scheme(self):
        """Test that URLs without scheme are rejected."""
        is_valid, error = validate_url("example.com")
        assert is_valid is False
        assert "Missing scheme" in error

    def test_invalid_url_wrong_scheme(self):
        """Test that URLs with non-HTTP(S) schemes are rejected."""
        is_valid, error = validate_url("ftp://example.com")
        assert is_valid is False
        assert "HTTP and HTTPS" in error

    def test_invalid_url_malformed(self):
        """Test that malformed URLs are rejected."""
        is_valid, error = validate_url("not a url at all")
        assert is_valid is False
        assert "Invalid URL" in error

    def test_invalid_url_empty(self):
        """Test that empty URLs are rejected."""
        is_valid, error = validate_url("")
        assert is_valid is False
        assert "Invalid URL" in error


class TestPDFGeneration:
    """Tests for PDF generation functionality."""

    @pytest.mark.asyncio
    async def test_generate_pdf_with_invalid_url(self):
        """Test that invalid URLs return error."""
        result = await generate_pdf("not-a-valid-url")
        assert result["success"] is False
        assert "Invalid URL" in result["error"]

    @pytest.mark.asyncio
    async def test_generate_pdf_creates_output_directory(self):
        """Test that output directory is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "new_dir"
            assert not output_path.exists()

            # Mock Playwright to avoid actual browser launch
            with patch("browser_pdf_mcp.server.async_playwright") as mock_playwright:
                mock_browser = AsyncMock()
                mock_page = AsyncMock()

                mock_playwright.return_value.__aenter__.return_value.chromium.launch.return_value = mock_browser
                mock_browser.new_page.return_value = mock_page
                mock_page.goto.return_value = None
                mock_page.pdf.return_value = None
                mock_browser.close.return_value = None

                await generate_pdf(
                    "https://example.com",
                    output_path=str(output_path),
                    filename="test.pdf"
                )

                assert output_path.exists()

    @pytest.mark.asyncio
    async def test_generate_pdf_default_filename(self):
        """Test that default filename is generated from domain."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("browser_pdf_mcp.server.async_playwright") as mock_playwright:
                mock_browser = AsyncMock()
                mock_page = AsyncMock()

                mock_playwright.return_value.__aenter__.return_value.chromium.launch.return_value = mock_browser
                mock_browser.new_page.return_value = mock_page
                mock_page.goto.return_value = None
                mock_page.pdf.return_value = None
                mock_browser.close.return_value = None

                result = await generate_pdf(
                    "https://www.example.com",
                    output_path=tmpdir
                )

                assert result["success"] is True
                assert "example_com" in result["filename"]

    @pytest.mark.asyncio
    async def test_generate_pdf_adds_extension(self):
        """Test that .pdf extension is added if not provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("browser_pdf_mcp.server.async_playwright") as mock_playwright:
                mock_browser = AsyncMock()
                mock_page = AsyncMock()

                mock_playwright.return_value.__aenter__.return_value.chromium.launch.return_value = mock_browser
                mock_browser.new_page.return_value = mock_page
                mock_page.goto.return_value = None
                mock_page.pdf.return_value = None
                mock_browser.close.return_value = None

                result = await generate_pdf(
                    "https://example.com",
                    output_path=tmpdir,
                    filename="myfile"
                )

                assert result["success"] is True
                assert result["filename"] == "myfile.pdf"

    @pytest.mark.asyncio
    async def test_generate_pdf_playwright_error(self):
        """Test that Playwright errors are handled."""
        from playwright.async_api import Error as PlaywrightError

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("browser_pdf_mcp.server.async_playwright") as mock_playwright:
                mock_playwright.return_value.__aenter__.return_value.chromium.launch.side_effect = PlaywrightError("Browser launch failed")

                result = await generate_pdf(
                    "https://example.com",
                    output_path=tmpdir
                )

                assert result["success"] is False
                assert "Playwright error" in result["error"]

    @pytest.mark.asyncio
    async def test_generate_pdf_success(self):
        """Test successful PDF generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("browser_pdf_mcp.server.async_playwright") as mock_playwright:
                mock_browser = AsyncMock()
                mock_page = AsyncMock()

                mock_playwright.return_value.__aenter__.return_value.chromium.launch.return_value = mock_browser
                mock_browser.new_page.return_value = mock_page
                mock_page.goto.return_value = None
                mock_page.pdf.return_value = None
                mock_browser.close.return_value = None

                result = await generate_pdf(
                    "https://example.com",
                    output_path=tmpdir,
                    filename="test.pdf"
                )

                assert result["success"] is True
                assert "file_path" in result
                assert "test.pdf" in result["file_path"]
                assert result["url"] == "https://example.com"
                assert result["filename"] == "test.pdf"

                # Verify browser methods were called correctly
                mock_page.goto.assert_called_once_with(
                    "https://example.com",
                    wait_until="networkidle",
                    timeout=60000
                )
                mock_page.pdf.assert_called_once()
                mock_browser.close.assert_called_once()


    @pytest.mark.asyncio
    async def test_generate_pdf_does_not_overwrite(self):
        """Test that an existing file gets a numeric suffix instead of being overwritten."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "page.pdf").write_bytes(b"existing")
            with patch("browser_pdf_mcp.server.async_playwright") as mock_playwright:
                mock_browser = AsyncMock()
                mock_playwright.return_value.__aenter__.return_value.chromium.launch.return_value = mock_browser

                result = await generate_pdf(
                    "https://example.com",
                    output_path=tmpdir,
                    filename="page"
                )

                assert result["success"] is True
                assert result["filename"] == "page_1.pdf"
                assert (Path(tmpdir) / "page.pdf").read_bytes() == b"existing"

    @pytest.mark.asyncio
    async def test_generate_pdf_networkidle_fallback(self):
        """Test that a networkidle timeout falls back to the load event."""
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("browser_pdf_mcp.server.async_playwright") as mock_playwright:
                mock_browser = AsyncMock()
                mock_page = AsyncMock()
                mock_playwright.return_value.__aenter__.return_value.chromium.launch.return_value = mock_browser
                mock_browser.new_page.return_value = mock_page
                mock_page.goto.side_effect = [PlaywrightTimeoutError("idle timeout"), None]

                result = await generate_pdf("https://example.com", output_path=tmpdir)

                assert result["success"] is True
                assert mock_page.goto.call_count == 2
                assert mock_page.goto.call_args.kwargs["wait_until"] == "load"
                mock_browser.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_pdf_missing_browser(self):
        """Test that a missing Chromium install produces an actionable message."""
        from playwright.async_api import Error as PlaywrightError

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("browser_pdf_mcp.server.async_playwright") as mock_playwright:
                mock_playwright.return_value.__aenter__.return_value.chromium.launch.side_effect = (
                    PlaywrightError("Executable doesn't exist at /some/path")
                )

                result = await generate_pdf("https://example.com", output_path=tmpdir)

                assert result["success"] is False
                assert "playwright install chromium" in result["error"]


class TestFilenameHandling:
    """Tests for filename sanitization and output paths."""

    def test_sanitize_adds_extension(self):
        assert sanitize_filename("report") == "report.pdf"

    def test_sanitize_keeps_extension(self):
        assert sanitize_filename("report.pdf") == "report.pdf"

    def test_sanitize_strips_directories(self):
        assert sanitize_filename("../../etc/evil") == "evil.pdf"
        assert sanitize_filename("..\\..\\evil") == "evil.pdf"

    def test_sanitize_replaces_unsafe_characters(self):
        assert sanitize_filename('a:b*c?"d') == "a_b_c__d.pdf"

    def test_sanitize_empty_name(self):
        assert sanitize_filename("..") == "page.pdf"

    def test_unique_path_counts_up(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "x.pdf"
            assert unique_path(base) == base
            base.touch()
            (Path(tmpdir) / "x_1.pdf").touch()
            assert unique_path(base) == Path(tmpdir) / "x_2.pdf"

    def test_default_output_dir_env_override(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BROWSER_PDF_OUTPUT_DIR", str(tmp_path))
        assert default_output_dir() == tmp_path

    def test_default_output_dir_fallback(self, monkeypatch):
        monkeypatch.delenv("BROWSER_PDF_OUTPUT_DIR", raising=False)
        assert default_output_dir() == Path.home() / "Downloads" / "mcp_pdfs"


class TestMCPServer:
    """Tests for MCP server functionality."""

    def test_server_name(self):
        """Test that server name is set correctly."""
        assert app.name == "browser-pdf-mcp"

    def test_server_version(self):
        """Test that the server reports the package version, not the SDK version."""
        from browser_pdf_mcp import __version__

        assert app.version == __version__

    @pytest.mark.asyncio
    async def test_tool_registration(self):
        """Test that tools are registered via decorators."""
        # The decorators register handlers, we just verify the server is configured
        assert hasattr(app, 'list_tools')
        assert hasattr(app, 'call_tool')
        # The actual tool functionality is tested in integration tests


class TestIntegration:
    """Integration tests (these require Playwright to be installed)."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_real_pdf_generation(self):
        """
        Test actual PDF generation with a real website.
        This test requires Playwright browsers to be installed.
        Run with: pytest -m integration
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            result = await generate_pdf(
                "https://example.com",
                output_path=tmpdir,
                filename="integration_test"
            )

            assert result["success"] is True, f"PDF generation failed: {result.get('error', 'Unknown error')}"

            pdf_path = Path(result["file_path"])
            assert pdf_path.exists(), f"PDF file not found at {pdf_path}"
            assert pdf_path.stat().st_size > 0, "PDF file is empty"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
