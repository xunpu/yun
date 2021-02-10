import re
import json
import apsw
import xxhash
import weakref
import os
import os.path
import Crypto.Random
from inspect import ismodule

from slowdown.cgi import Form
from slowdown.token import VerificationError

from yun import fs, card, article
from yun.runtime import json_resp, json_resp_404


def HTTP(rw):
    Api(rw)


class API:

    fs = fs
    card = card
    article = article

    def __init__(self):
        methods = list(filter(lambda m: not m.startswith('__') and not m.endswith(
            '__') and callable(getattr(self, m)), dir(self)))
        self.cgi = dict(list((fn, getattr(self, fn)) for fn in methods))
        del methods
        self.modules = list(filter(lambda m: not m.startswith(
            '__') and not m.endswith('__') and ismodule(getattr(self, m)), dir(self)))

    def __call__(self, rw):
        path_info = rw.environ['locals.path_info'].lstrip('/').rstrip('/')
        path = path_info.split('/')
        func = None
        for match, fn in self.cgi.items():
            if match(path_info) is not None:
                func = fn
                rw.environ['locals.api_info'] = match(path_info).groups()[0]
                break
        if path[0] in self.modules and len(path) > 1:
            module = getattr(self, path[0])
            found = find_cgi(path[1], path[2:], module)
            if found is None:
                func = None
            else:
                real_path_info = path_info.rstrip(found[1])
                match = re.compile(real_path_info + '(/?.*)').match
                self.cgi[match] = found[0]
                func, rw.environ['locals.api_info'] = found
        if func is None:
            json_resp_404(rw)
        else:
            data = func(rw)
            if data is not None:
                rw.send_response_and_close(
                    headers=[('Content-Type', 'application/json')],
                    content=bytes(json.dumps(data), 'utf-8'))


def find_cgi(name, path, module):
    try:
        func = getattr(module, name)
    except AttributeError:
        return None
    if callable(func) and func.__name__ == '__API__':
        return func, '/{}'.format('/'.join(path))
    elif ismodule(getattr(module, name)):
        return find_cgi(path[0], path[1:], getattr(module, name))
    else:
        return None


Api = API()
