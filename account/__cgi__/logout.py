import json

from slowdown.cgi import Form

import yun.runtime
from yun.runtime import tokenizer
from yun.account import default_expires_hours

def POST(rw):
    # cookie = yun.runtime.del_session()
    form = Form(rw)
    # data = tokenizer.unpack(form['token'])
    # phone, stime = data.split('&')
    data = json.dumps({
        'code': 0,
        'msg': '登出成功',
        'data': {
            'token': ''
        }
    })
    rw.send_response_and_close(headers=[('Content-Type', 'application/json')],
                               content=bytes(data, 'utf-8'))
