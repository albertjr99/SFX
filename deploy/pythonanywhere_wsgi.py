# Conteúdo do arquivo WSGI do PythonAnywhere
# (aba "Web" → link "WSGI configuration file"). Apague tudo o que estiver lá e cole isto.
import os
import sys

projeto = os.path.expanduser("~/SFX")
if projeto not in sys.path:
    sys.path.insert(0, projeto)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(projeto, ".env"))

from wsgi import app as application  # noqa: E402,F401
