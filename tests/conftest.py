"""Rende importabile frank_core (che vive in .claude/) nei test."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / ".claude"))
