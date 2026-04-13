import os
import sys

PROJECT_HOME = os.path.dirname(__file__)
if PROJECT_HOME not in sys.path:
    sys.path.insert(0, PROJECT_HOME)

from webhook_hq10 import application
