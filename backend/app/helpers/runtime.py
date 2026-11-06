"""Interpreter paths must retain virtualenv symlinks, which select site-packages."""
from pathlib import Path

def interpreter_path(value: str) -> str:
    return str(Path(value).expanduser().absolute())
