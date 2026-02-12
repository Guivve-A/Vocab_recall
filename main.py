"""
VocabRecall — Entry point
==========================
Launch the application.
"""

import sys
import os

# Ensure project root is on the path so absolute imports work when running
# directly with `python main.py`.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.app import VocabRecallApp


def main() -> None:
    app = VocabRecallApp()
    app.mainloop()


if __name__ == "__main__":
    main()
