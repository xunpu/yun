import apsw
import time
import json
from datetime import datetime
from datetime import timedelta

import slowdown.cgi

import yun
import yun.runtime
import yun.runtime.verifiers
from yun.runtime import tokenizer
from yun.runtime import get_userdb_by_id, create_table_if_not_exists
from yun.account import default_expires_hours


def POST(rw):
    form = slowdown.cgi.Form(rw)
    phone = form['phone'].strip()
    errmsg = []
    match = \
        yun.captcha.verify(
            text=form['text'],
            token=form['token']
        )
    if yun.captcha.MISMATCH == match:
        errmsg.append('验证码不匹配')
    elif yun.captcha.INVALID == match:
        errmsg.append('验证码已失效')
    elif not phone:
        errmsg.append('手机号为空')
    if errmsg:
        data = json.dumps({
            'code': 1,
            'msg': errmsg[0],
            'data': json.dumps(errmsg)
        })
        return rw.send_response_and_close(headers=[('Content-Type', 'application/json')],
                                          content=bytes(data, 'utf-8'))

    match = yun.runtime.verifiers.is_china_phone(form['phone'])
    if match:
        phone = match.groups()[0]
        password_salt = form.get('password_salt', '')
        password_hash = form.get('password_hash', '')
        try:
            db = yun.runtime.get_users_db()
            db.cursor().execute(
                (
                    'INSERT INTO users (password_salt, password_hash, '
                    'phone)'
                    'VALUES (?, ?, ?)'
                ),
                (password_salt, password_hash, phone)
            )
        except apsw.ConstraintError:
            errmsg.append('该手机已被使用，请尝试登录')
    else:
        errmsg.append('暂不支持该手机')

    if errmsg:
        data = json.dumps({
            'code': 1,
            'msg': errmsg[0],
            'data': json.dumps(errmsg)
        })
    else:
        db = yun.runtime.get_users_db()
        row = db.cursor().execute(
            'SELECT id FROM users WHERE phone=?', (phone,)).fetchone()
        user_db = get_userdb_by_id(row[0])
        create_table_if_not_exists(user_db)
        expries = datetime.now() + timedelta(hours=default_expires_hours)
        token = tokenizer.pack(f'{phone}&{expries}')
        data = json.dumps({
            'code': 0,
            'msg': 'ok',
            'data': {'phone': phone, 'token': token}
        })

    return rw.send_response_and_close(headers=[('Content-Type', 'application/json')],
                                      content=bytes(data, 'utf-8'))
