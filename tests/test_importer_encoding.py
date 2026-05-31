import os
from unittest.mock import patch

import importer.convert_dbase as conv


def test_dbf_encoding_defaults_to_latin1():
    with patch.dict(os.environ, {}, clear=True):
        assert conv.get_dbf_encoding() == "latin-1"


def test_dbf_encoding_reads_env():
    with patch.dict(os.environ, {"DBF_ENCODING": "cp850"}):
        assert conv.get_dbf_encoding() == "cp850"
