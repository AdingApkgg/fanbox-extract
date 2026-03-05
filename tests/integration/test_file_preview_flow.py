import os
import tempfile
import unittest
from fanbox_extractor.web_ui_core import build_tree_nodes
from fanbox_extractor.web_ui_core import rewrite_markdown_links


class FilePreviewIntegrationTest(unittest.TestCase):
    def test_build_tree_nodes_and_icons(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = os.path.join(tmp, "downloads")
            os.makedirs(os.path.join(root, "post"), exist_ok=True)
            with open(os.path.join(root, "post", "README.md"), "w", encoding="utf-8") as f:
                f.write("# t")
            with open(os.path.join(root, "post", "cover.png"), "w", encoding="utf-8") as f:
                f.write("x")
            nodes = build_tree_nodes(root)
            self.assertEqual(nodes[0]["label"], "post")
            self.assertEqual(nodes[0]["icon"], "folder")
            children = {n["label"]: n["icon"] for n in nodes[0]["children"]}
            self.assertEqual(children["README.md"], "description")
            self.assertEqual(children["cover.png"], "image")

    def test_rewrite_links_only_inside_downloads(self):
        with tempfile.TemporaryDirectory() as tmp:
            downloads = os.path.join(tmp, "downloads")
            post = os.path.join(downloads, "creator", "post")
            os.makedirs(post, exist_ok=True)
            markdown_path = os.path.join(post, "README.md")
            escaped = rewrite_markdown_links("[x](../../../secret.txt)", markdown_path, downloads)
            self.assertEqual(escaped, "[x](../../../secret.txt)")


if __name__ == "__main__":
    unittest.main()
