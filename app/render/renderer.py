# app/render/renderer.py
"""Render the Jinja2 report template to HTML, then convert to PDF bytes
with WeasyPrint - see ADR-0002 for why this pipeline and not a headless
browser.

Windows note: Python 3.8+ dropped PATH-based DLL search for extension
modules, so WeasyPrint's GTK3 runtime DLLs (libgobject-2.0-0, etc.) are
not found automatically on Windows even when the runtime is installed
and on PATH. If WEASYPRINT_DLL_DIRECTORY is set, we register it with
os.add_dll_directory() before importing weasyprint. This is a no-op on
non-Windows platforms and a no-op on Windows machines where the env var
isn't set, so it does not change behavior anywhere else (Linux/Mac/CI,
or a Windows box where the DLLs are already discoverable another way)."""
import os  # os module, needed for sys.platform check, environ lookup, and add_dll_directory
import sys  # sys module, needed to check the running platform

if sys.platform == "win32":  # only attempt the DLL-directory bootstrap on Windows
    _dll_dir = os.environ.get("WEASYPRINT_DLL_DIRECTORY")  # read the optional env var pointing at the GTK3 runtime bin dir
    if _dll_dir:  # only register the directory if the env var is actually set
        os.add_dll_directory(_dll_dir)  # tell Windows' extension-module loader to also search this directory for DLLs

from pathlib import Path  # pathlib for building the templates directory path
from jinja2 import Environment, FileSystemLoader  # Jinja2 environment and filesystem template loader
from weasyprint import HTML  # WeasyPrint's HTML class, used to convert rendered HTML into PDF bytes

TEMPLATES_DIR = Path(__file__).parent / "templates"  # absolute path to this package's templates directory


def render_html(context: dict) -> str:  # render report.html with the given context dict
    """Render report.html with the given context dict (the shape produced
    by app.mapping.mapper.map_to_template_context)."""
    environment = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)  # build a Jinja2 environment scoped to the templates dir with HTML autoescaping on
    template = environment.get_template("report.html")  # load the report.html template from the environment
    return template.render(**context)  # render the template with the context dict unpacked as template variables


def html_to_pdf(html: str) -> bytes:  # convert an HTML string to PDF bytes
    """Convert an HTML string to PDF bytes via WeasyPrint."""
    return HTML(string=html).write_pdf()  # parse the HTML string and render it to PDF bytes


def render_pdf(context: dict) -> bytes:  # convenience wrapper: context dict straight to PDF bytes
    """Convenience wrapper: context dict straight to PDF bytes."""
    html = render_html(context)  # first render the context dict to an HTML string
    return html_to_pdf(html)  # then convert that HTML string to PDF bytes
