# Copyright 2021 DeepL GmbH (https://www.deepl.com)
# Use of this source code is governed by an MIT
# license that can be found in the LICENSE file.

from click.testing import CliRunner
from .conftest import *
from deepl import __main__
import pathlib
import pytest
import re


@pytest.fixture
def runner(server):
    env = {
        "DEEPL_SERVER_URL": server.server_url,
        "DEEPL_AUTH_KEY": server.auth_key,
    }
    return CliRunner(env=env)


def test_help(runner):
    result = runner.invoke(deepl.__main__, "--help")
    assert result.exit_code == 0, f"exit: {result.exit_code}\n {result.output}"
    assert "usage" in result.output


def test_version(runner):
    result = runner.invoke(deepl.__main__, "--version")
    assert result.exit_code == 0, f"exit: {result.exit_code}\n {result.output}"
    assert "deepl-python v" in result.output
    version_regex = re.compile(r"deepl-python v\d+\.\d+\.\d+")
    assert version_regex.match(result.output) is not None


def test_verbose(runner):
    # verbose = info
    result = runner.invoke(deepl.__main__, "--verbose usage")
    assert result.exit_code == 0, f"exit: {result.exit_code}\n {result.output}"
    assert "Request to DeepL API" in result.output

    # verbose = debug
    result = runner.invoke(deepl.__main__, "-vv usage")
    assert result.exit_code == 0, f"exit: {result.exit_code}\n {result.output}"
    assert "Request to DeepL API" in result.output
    assert "Request details" in result.output


def test_no_auth(runner):
    result = runner.invoke(
        deepl.__main__, "usage", env={"DEEPL_AUTH_KEY": None}
    )
    assert result.exit_code == 1, f"exit: {result.exit_code}\n {result.output}"
    assert "DEEPL_AUTH_KEY" in result.output


def test_no_command(runner):
    result = runner.invoke(deepl.__main__, "")
    assert result.exit_code == 1, f"exit: {result.exit_code}\n {result.output}"
    assert "command is required" in result.output


def test_usage(runner):
    result = runner.invoke(deepl.__main__, "usage")
    assert result.exit_code == 0, f"exit: {result.exit_code}\n {result.output}"
    assert "Usage this billing period" in result.output


def test_languages(runner):
    result = runner.invoke(deepl.__main__, "languages")
    assert result.exit_code == 0, f"exit: {result.exit_code}\n {result.output}"
    assert "Source languages" in result.output
    assert "Target languages" in result.output
    assert "DE: German" in result.output
    assert "EN: English" in result.output


def test_text(runner):
    result = runner.invoke(
        deepl.__main__, 'text --to DE "proton beam" --show-detected-source'
    )
    assert result.exit_code == 0, f"exit: {result.exit_code}\n {result.output}"
    assert example_text["DE"] in result.output
    assert "Detected source" in result.output


def test_text_stdin(runner):
    result = runner.invoke(
        deepl.__main__,
        "text --to DE --show-detected-source -",
        input=example_text["EN"],
    )
    assert result.exit_code == 0, f"exit: {result.exit_code}\n {result.output}"
    assert example_text["DE"] in result.output
    assert "Detected source" in result.output


@needs_real_server
def test_text_preserve_formatting(runner):
    result = runner.invoke(
        deepl.__main__, 'text --to DE --preserve-formatting "proton beam"'
    )
    assert result.exit_code == 0, f"exit: {result.exit_code}\n {result.output}"
    assert example_text["DE"].lower() in result.output


def test_text_split_sentences(runner):
    result = runner.invoke(
        deepl.__main__,
        '-vv text --to DE --split-sentences nonewlines "proton beam"',
    )
    assert result.exit_code == 0, f"exit: {result.exit_code}\n {result.output}"
    # Check split_sentences parameter is sent in HTTP request
    regex = re.compile("Request details.*split_sentences.*nonewlines.*")
    assert any(
        regex.match(line) is not None for line in result.output.split("\n")
    ), f"output:\n{result.output}"


def test_text_tags(runner):
    result = runner.invoke(
        deepl.__main__,
        '-vv text --to DE --tag-handling xml --splitting-tags split --ignore-tags a,b --ignore-tags c --ignore-tags d "proton beam"',
    )
    assert result.exit_code == 0, f"exit: {result.exit_code}\n {result.output}"
    # Check ignore_tags parameter is sent in HTTP request
    regex = re.compile("Request details.*'ignore_tags': 'a,b,c,d'")
    assert any(
        regex.match(line) is not None for line in result.output.split("\n")
    ), f"output:\n{result.output}"
    # Check splitting_tags parameter is sent in HTTP request
    regex = re.compile("Request details.*'splitting_tags': 'split'")
    assert any(
        regex.match(line) is not None for line in result.output.split("\n")
    ), f"output:\n{result.output}"


def test_document(runner, tmpdir):
    tmpdir = pathlib.Path(tmpdir)
    output_dir = tmpdir / "output"
    input_document = tmpdir / "document.txt"
    input_document.write_text(example_text["EN"])
    output_document = output_dir / "document.txt"

    result = runner.invoke(
        deepl.__main__, f"-vv document --to DE {input_document} {output_dir}"
    )
    assert result.exit_code == 0, f"exit: {result.exit_code}\n {result.output}"
    assert example_text["DE"] == output_document.read_text()


def test_document_occupied_output(runner, tmpdir):
    tmpdir = pathlib.Path(tmpdir)
    output_dir = tmpdir / "output"
    input_document = tmpdir / "document.txt"
    input_document.write_text(example_text["EN"])
    # Create a file in place of the output directory
    output_dir.touch()

    result = runner.invoke(
        deepl.__main__, f"-vv document --to DE {input_document} {output_dir}"
    )
    assert result.exit_code == 1, f"exit: {result.exit_code}\n {result.output}"
    assert "already exists" in result.output


def test_invalid_document(runner, tmpdir):
    tmpdir = pathlib.Path(tmpdir)
    output_dir = tmpdir / "output"
    input_document = tmpdir / "document.xyz"
    input_document.write_text(example_text["EN"])

    result = runner.invoke(
        deepl.__main__, f"-vv document --to DE {input_document} {output_dir}"
    )
    assert result.exit_code == 1, f"exit: {result.exit_code}\n {result.output}"
    assert "Invalid file" in result.output
