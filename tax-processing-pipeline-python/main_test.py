# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unit tests for the file upload handling in main.py"""

import io
import os
import tempfile
import unittest
from unittest.mock import patch

from werkzeug.datastructures import FileStorage

import main


def make_file(filename, content=b"%PDF-1.4", mimetype="application/pdf"):
    """Build an uploaded file as Flask would hand it to the app"""
    return FileStorage(
        stream=io.BytesIO(content), filename=filename, content_type=mimetype
    )


def is_inside(path, directory):
    """True if path resolves to a location inside directory"""
    directory = os.path.realpath(directory)
    return os.path.realpath(path).startswith(directory + os.sep)


class TestSaveFilesToTempDirectory(unittest.TestCase):
    """Tests for save_files_to_temp_directory"""

    def setUp(self):
        # pylint: disable=consider-using-with
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        # A directory outside temp_dir that a malicious filename aims at.
        # pylint: disable=consider-using-with
        self.outside_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.outside_dir.cleanup)

    def save(self, files):
        """Save files and check every returned path is inside temp_dir"""
        saved = main.save_files_to_temp_directory(files, self.temp_dir)
        for path, _ in saved:
            self.assertTrue(is_inside(path, self.temp_dir.name), path)
        return saved

    def test_normal_filename(self):
        """A plain upload is saved under its own name"""
        saved = self.save([make_file("w2.pdf", b"W2")])
        self.assertEqual(len(saved), 1)
        path, mimetype = saved[0]
        self.assertEqual(os.path.basename(path), "w2.pdf")
        self.assertEqual(mimetype, "application/pdf")
        with open(path, "rb") as file:
            self.assertEqual(file.read(), b"W2")

    def test_path_traversal_filenames_stay_in_temp_dir(self):
        """Absolute paths and ../ sequences cannot write outside temp_dir"""
        target = os.path.join(self.outside_dir.name, "pwned.pdf")
        relative = os.path.relpath(target, self.temp_dir.name)
        filenames = [
            target,
            relative,
            "../" * 20 + target.lstrip("/"),
            relative.replace("/", "\\"),
            "C:\\Windows\\System32\\pwned.pdf",
            "/home/appuser/.local/lib/python3.11/site-packages/pwned.pth",
        ]
        saved = self.save([make_file(name, b"payload") for name in filenames])
        self.assertEqual(len(saved), len(filenames))
        self.assertFalse(os.path.exists(target))
        self.assertEqual(os.listdir(self.outside_dir.name), [])

    def test_filenames_without_a_usable_name(self):
        """Names that sanitize to nothing are kept under a fallback name"""
        filenames = ["..", "../", "/", "納税申告書"]
        saved = self.save([make_file(name) for name in filenames])
        self.assertEqual(len(saved), len(filenames))
        for path, _ in saved:
            self.assertEqual(os.path.basename(path), "document")
            self.assertTrue(os.path.isfile(path))

    def test_colliding_names_do_not_overwrite(self):
        """Uploads whose sanitized names match are saved separately"""
        files = [
            make_file("w2.pdf", b"first"),
            make_file("w2.pdf", b"second"),
            make_file("연말정산.pdf", b"third"),
            make_file("원천징수.pdf", b"fourth"),
        ]
        saved = self.save(files)
        paths = [path for path, _ in saved]
        self.assertEqual(len(set(paths)), len(files))
        contents = []
        for path in paths:
            with open(path, "rb") as file:
                contents.append(file.read())
        self.assertEqual(contents, [b"first", b"second", b"third", b"fourth"])

    def test_invalid_mimetype_and_empty_filename_are_skipped(self):
        """Files with a disallowed type or no name are not saved"""
        files = [
            make_file("notes.txt", mimetype="text/plain"),
            make_file(""),
            make_file("w2.pdf"),
        ]
        saved = self.save(files)
        self.assertEqual([os.path.basename(p) for p, _ in saved], ["w2.pdf"])


class TestFileUploadRoute(unittest.TestCase):
    """Tests for POST /file_upload through the Flask test client"""

    def setUp(self):
        main.app.config["TESTING"] = True
        self.client = main.app.test_client()
        # pylint: disable=consider-using-with
        self.outside_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.outside_dir.cleanup)

    @patch("main.run_docai_pipeline")
    def test_malicious_filename_does_not_escape_temp_dir(self, mock_pipeline):
        """A crafted multipart filename cannot write outside the temp dir"""
        target = os.path.join(self.outside_dir.name, "pwned.pdf")
        seen = []

        def record_paths(local_files, _collection):
            for path, _ in local_files:
                with open(path, "rb") as file:
                    seen.append((path, file.read()))
            return []

        mock_pipeline.side_effect = record_paths
        data = {
            "files": [
                (io.BytesIO(b"absolute"), target, "application/pdf"),
                (io.BytesIO(b"relative"), "../../../" + target, "application/pdf"),
                (io.BytesIO(b"normal"), "w2.pdf", "application/pdf"),
            ]
        }
        response = self.client.post(
            "/file_upload", data=data, content_type="multipart/form-data"
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(os.path.exists(target))
        self.assertEqual(os.listdir(self.outside_dir.name), [])
        self.assertEqual(
            [content for _, content in seen], [b"absolute", b"relative", b"normal"]
        )
        self.assertEqual(os.path.basename(seen[2][0]), "w2.pdf")
        # The per-request temp directory is removed after the response.
        for path, _ in seen:
            self.assertFalse(os.path.exists(path))


if __name__ == "__main__":
    unittest.main()
