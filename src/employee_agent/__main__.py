import ssl
import urllib3
import os
import warnings

warnings.filterwarnings("ignore", category=ResourceWarning)

os.environ["ANONYMIZED_TELEMETRY"] = "false"
os.environ["PYTHONHTTPSVERIFY"] = "0"
os.environ["LITELLM_LOG"] = "ERROR"

ssl._create_default_https_context = ssl._create_unverified_context
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import requests as _req
_orig_req = _req.Session.request
def _no_verify(self, *a, **kw):
    kw["verify"] = False
    return _orig_req(self, *a, **kw)
_req.Session.request = _no_verify

import httpx as _httpx
_orig_client = _httpx.Client.__init__
def _httpx_no_verify(self, *a, **kw): kw["verify"] = False; _orig_client(self, *a, **kw)
_httpx.Client.__init__ = _httpx_no_verify
_orig_async = _httpx.AsyncClient.__init__
def _httpx_async_no_verify(self, *a, **kw): kw["verify"] = False; _orig_async(self, *a, **kw)
_httpx.AsyncClient.__init__ = _httpx_async_no_verify

import asyncio
from employee_agent.main import main

if __name__ == "__main__":
    asyncio.run(main())
