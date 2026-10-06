# -*- coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path
from functools import cached_property

_dir_here = Path(__file__).absolute().parent
PACKAGE_NAME = _dir_here.name


class PathEnum:
    """
    Centralized enumeration of all project paths with absolute path references.

    Provides IDE-autocomplete-friendly access to all project directories and files using
    absolute paths to eliminate current directory dependencies and ensure consistent path
    resolution across different execution contexts and DevOps workflows.
    """
    @cached_property
    def dir_home(self):
        return Path.home()

    dir_project_root = _dir_here.parent
    dir_tmp = dir_project_root / "tmp"

    # Source Code
    dir_package = _dir_here
    path_version_py = dir_package / "_version.py"
    path_pyproject_toml = dir_project_root / "pyproject.toml"
    path_requirements_txt = dir_project_root / "requirements.txt"
    path_authors = dir_project_root / "AUTHORS.rst"
    path_license = dir_project_root / "LICENSE"
    path_release_history = dir_project_root / "release-history.rst"

    # Virtual Environment
    dir_venv = dir_project_root / ".venv"
    dir_venv_bin = dir_venv / "bin"
    path_venv_bin_pip = dir_venv_bin / "pip"
    path_venv_bin_python = dir_venv_bin / "python"
    path_venv_bin_pytest = dir_venv_bin / "pytest"

    # Test
    dir_htmlcov = dir_project_root / "htmlcov"
    path_cov_index_html = dir_htmlcov / "index.html"
    dir_unit_test = dir_project_root / "tests"
    dir_test_data = dir_unit_test / "data"
    dir_test_list_objects_folder = dir_test_data / "list_objects_folder"
    dir_test_upload_dir_folder = dir_test_data / "upload_dir_folder"
    dir_int_test = dir_project_root / "tests_int"
    dir_load_test = dir_project_root / "tests_load"

    # Documentation
    dir_docs_source = dir_project_root / "docs" / "source"
    dir_docs_build_html = dir_project_root / "docs" / "build" / "html"

    # Build
    dir_build = dir_project_root / "build"
    dir_dist = dir_project_root / "dist"


path_enum = PathEnum()
"""
Single entry point for all project paths with absolute path references.
"""
