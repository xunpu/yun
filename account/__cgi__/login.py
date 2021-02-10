import json
import hashlib
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
    match = yun.runtime.verifiers.is_china_phone(phone)
    if match:
        phone = match.groups()[0]
        conn = yun.runtime.get_users_db()
        row = conn.cursor().execute(
            'SELECT password_hash FROM users WHERE phone=?', (phone,)).fetchone()
        if row is None:
            errmsg.append('手机号或密码错误')  # 用户不存在
        else:
            password_hash1 = row[0]
            if password_hash2 != \
                    hashlib.sha256(
                        (password_salt2 + password_hash1).encode()
                    ).hexdigest():
                errmsg.append('手机号或密码错误')  # 密码错误
    else:
        errmsg.append('手机号或密码错误')  # 手机格式错误
    if errmsg:
        yun.captcha.note_failed(rw)
        data = json.dumps({
            'code': 1,
            'msg': errmsg[0],
            'data': json.dumps(errmsg)
        })
        return rw.send_response_and_close(headers=[('Content-Type', 'application/json')],
                                          content=bytes(data, 'utf-8'))

    db = yun.runtime.get_users_db()
    row = db.cursor().execute(
        'SELECT id FROM users WHERE phone=?', (phone,)).fetchone()
    user_db = get_userdb_by_id(row[0])
    create_table_if_not_exists(user_db)

    yun.captcha.note_success(rw)
    # cookie = yun.runtime.set_session(phone)
    expries = datetime.now() + timedelta(hours=default_expires_hours)
    token = tokenizer.pack(f'{phone}&{expries}')
    data = json.dumps({
        'code': 0,
        'msg': '登录成功',
        'data': {'phone': phone, 'token': token}
    })
    rw.send_response_and_close(headers=[('Content-Type', 'application/json')],
                               content=bytes(data, 'utf-8'))
