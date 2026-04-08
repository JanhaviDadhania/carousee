"""
carousee — generate carousel slides from a plain text script.
"""

from carousee.composer import compose_all
from carousee.parser import load_script, parse_script, save_yaml

__version__ = "0.1.4"
__all__ = ["compose_all", "load_script", "parse_script", "save_yaml"]
