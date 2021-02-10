import json
import hashlib
from datetime import datetime
from datetime import timedelta

import slowdown.cgi

import yun
import yun.runtime
import yun.runtime.verifiers
from yun.runtime import tokenizer
from yun.account import default_expires_hours


def POST(rw):
    form = slowdown.cgi.Form(rw)
    phone = form['phone'].strip()
    errmsg = []

    match = yun.captcha.verify(
        text=form.get('text'),
        token=form.get('token'),
        rw=rw
    )
    if yun.captcha.MISMATCH == match:
        errmsg.append('验证码不匹配')
    elif yun.captcha.INVALID == match:
        errmsg.append('验证码已失效')
    if not phone:
        errmsg.append('手机号为空')
    if errmsg:
        yun.captcha.note_failed(rw)
        data = json.dumps({
            'code': 1,
            'msg': errmsg[0],
            'data': json.dumps(errmsg)
        })
        return rw.send_response_and_close(headers=[('Content-Type', 'application/json')],
                                          content=bytes(data, 'utf-8'))

    password_salt2 = form.get('password_salt2', '')
    password_hash2 = form.get('password_hash2', '')
    new_password_salt = form.get('new_password_salt', '')
    new_password_hash = form.get('new_password_hash', '')

    conn = yun.runtime.get_users_db()
    row = conn.cursor().execute(
        'SELECT password_hash, password_salt FROM users WHERE phone=?', (phone,)).fetchone()
    password_hash1 = row[0]
    if password_hash2 != hashlib.sha256(
        (password_salt2 + password_hash1).encode()
    ).hexdigest():
        errmsg.append('旧密码不符')
    if errmsg:
        yun.captcha.note_failed(rw)
        data = json.dumps({
            'code': 1,
            'msg': errmsg[0],
            'data': json.dumps(errmsg)
        })
        return rw.send_response_and_close(headers=[('Content-Type', 'application/json')],
                                          content=bytes(data, 'utf-8'))
    conn.cursor().execute(
        'UPDATE users SET password_salt=?, password_hash=? WHERE '
                                    'phone=?',
        (new_password_salt, new_password_hash, phone)
    )
    yun.captcha.note_success(rw)
    data = json.dumps({
        'code': 0,
        'msg': '修改成功',
        'data': {}
    })
    rw.send_response_and_close(headers=[('Content-Type', 'application/json')],
                               content=bytes(data, 'utf-8'))
