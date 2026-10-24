# Browser PDF MCP

[![CI](https://github.com/PascalThesing/browserpdfmcp/actions/workflows/ci.yml/badge.svg)](https://github.com/PascalThesing/browserpdfmcp/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A small [Model Context Protocol](https://modelcontextprotocol.io) server that lets an AI agent save any web page as a
PDF file, in one tool call.

```
Agent: create_website_pdf(url="https://arxiv.org/abs/1706.03762",
                          output_path="~/research/transformers",
                          filename="2017_vaswani_attention-is-all-you-need")
  →    ~/research/transformers/2017_vaswani_attention-is-all-you-need.pdf
```

## Why this server

- **One call, one file.** You pass in a URL and get back the absolute path of a finished PDF. There's no browser
  session to manage and no navigate-then-export sequence.
- **Light on context.** It exposes a single tool with three parameters, so it adds almost nothing to the agent's prompt
  and fits alongside search and fetch tools.
- **The agent decides where files go.** It chooses the folder and filename for each PDF, so it can build an organised
  source library while it works. Existing files are never overwritten.
- **Handles dynamic pages.** It waits for network idle so JavaScript-rendered content is included, and falls back to
  the `load` event for pages that never go idle.
- **Easy to install.** It's plain Python run with `uvx`, with no repo checkout and no hardcoded paths.

## Quick start

You need [uv](https://docs.astral.sh/uv/) and Python 3.10 or newer.

**1. Install the browser (once):**

```bash
uvx playwright install chromium
```

**2. Add the server to your MCP client.**

Claude Code:

```bash
claude mcp add browser-pdf -- uvx --from git+https://github.com/PascalThesing/browserpdfmcp browser-pdf-mcp
```

Claude Desktop, Cursor, VS Code and other JSON-configured clients:

```json
{
  "mcpServers": {
    "browser-pdf": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/PascalThesing/browserpdfmcp", "browser-pdf-mcp"],
      "env": {
        "BROWSER_PDF_OUTPUT_DIR": "~/Documents/web-pdfs"
      }
    }
  }
}
```

Claude Desktop config locations:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

Restart the client after you change its config.

**3. Ask for a PDF:**

```
Save https://example.com as a PDF
```

## Tool reference

### `create_website_pdf`

| Parameter     | Required | Description |
|---------------|----------|-------------|
| `url`         | yes      | Full `http://` or `https://` URL of the page. |
| `output_path` | no       | Directory to save into (`~` is expanded and missing directories are created). Defaults to the output directory below. |
| `filename`    | no       | Filename without `.pdf`. Defaults to the domain name, e.g. `example_com`. Directory parts and unsafe characters are removed. If the file exists, `_1`, `_2`, … is appended. |

The PDF is A4 with 1 cm margins and printed backgrounds. The tool returns the absolute file path.

### Configuration

| Environment variable     | Default               | Description |
|--------------------------|-----------------------|-------------|
| `BROWSER_PDF_OUTPUT_DIR` | `~/Downloads/mcp_pdfs` | Default output directory when the agent doesn't pass `output_path`. |

## Use cases

### Agent literature research with a PDF source library

Have an agent research a topic and keep a PDF of every source it uses. The PDFs are a snapshot of each page as it was
when the agent read it, which you can check, annotate or cite later.

```
Research recent approaches to retrieval-augmented generation for long documents.
Find 8-10 relevant papers and high-quality blog posts. For each source you use:
  - save it with create_website_pdf into ~/research/rag-long-docs/
  - name the file <year>_<first-author-or-site>_<short-title>
Then write a short literature overview and a bibliography that lists each
source's title, URL and local PDF path.
```

Good variations:
- **Systematic reviews:** Ask the agent to save every candidate page into `included/` or `excluded/` folders as it
  screens them, so you can audit its decisions.
- **Competitor or market research:** Product, pricing and changelog pages, one folder per company.
- **Related-work sections:** The agent collects the papers' landing pages and blog explanations, and you get a folder
  you can drop straight into your reference manager.

### Archiving sources and citations

Web pages change and disappear. Save the exact version you cited in a report, thesis, ticket or article:

```
For every link in report.md, save the page as a PDF into ./sources/ and add the
local path next to each citation.
```

### Documentation snapshots

Freeze the docs for the library version you depend on, or build an offline reading set:

```
Save the "Getting started", "Configuration" and "API reference" pages of the
docs at https://docs.example.com into ~/docs/example-v2/
```

### Evidence and compliance capture

Keep dated copies of terms of service, privacy policies, pricing pages or public statements:

```
Save the current terms of service and privacy policy of example.com into
~/evidence/example/ with today's date in the filename.
```

### Feeding PDF-based tools

Many tools take PDFs more readily than URLs: reference managers such as Zotero, notebook and Q&A tools, e-readers,
and RAG ingestion pipelines. An agent can collect pages and hand the folder straight to them.

### Offline reading packs

```
Find the five best long-form articles about the history of Unix and save them as
PDFs into ~/reading/unix/ so I can read them on the train.
```

## Limitations

- **No logins.** The browser starts fresh every time, so pages behind a login or paywall render as their logged-out
  version.
- **Cookie banners and pop-ups** can appear in the PDF.
- **Print layout.** Pages render using their print CSS (A4). Some sites look different from the screen version or
  hide content when printed.
- **Bot protection** on some sites may block headless browsers.
- Navigation times out after 60 seconds.

## Development

```bash
git clone https://github.com/PascalThesing/browserpdfmcp
cd browserpdfmcp
uv sync
uv run playwright install chromium

uv run pytest                  # unit tests (mocked browser)
uv run pytest -m integration   # real browser, needs network
uv run ruff check
```

The repository ships a `.mcp.json` that runs the local checkout with `uv run browser-pdf-mcp`, so Claude Code and
VS Code pick up your working copy when opened in this folder.

To try the server interactively, use the [MCP Inspector](https://github.com/modelcontextprotocol/inspector):

```bash
npx @modelcontextprotocol/inspector uv run browser-pdf-mcp
```

### Project structure

```
browserpdfmcp/
├── src/browser_pdf_mcp/
│   ├── __init__.py
│   └── server.py        # MCP server and PDF generation
├── tests/
│   └── test_server.py
├── .github/workflows/ci.yml
├── .mcp.json            # dev config for MCP clients in this folder
├── pyproject.toml
└── LICENSE
```

## Troubleshooting

**"Chromium is not installed for Playwright"**: run exactly the command printed in the error message. It installs
the browser build that matches the Playwright version the server uses, which can differ from what a separate
`uvx playwright install chromium` picked. On a fresh Linux machine, add `--with-deps` to install system libraries too.

**The server doesn't appear in the client**: check that `uvx` is on the `PATH` the client sees. GUI apps often have a
smaller `PATH`, so use the absolute path (`which uvx`) as `command`. Restart the client and check its MCP logs.

**The PDF is blank or incomplete**: the site may need a login, block headless browsers, or render content only on
user interaction. See [Limitations](#limitations).

## License

[MIT](LICENSE)
