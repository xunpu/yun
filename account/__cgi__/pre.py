import json
import apsw
import xxhash
import os.path
import Crypto.Random

import yun.runtime
from yun.runtime import tokenizer

from slowdown.cgi import Form, multipart
from slowdown.token import VerificationError

def HTTP(rw):
    return json_resp(rw)


class JsonResponse:

    limit = 20

    def __call__(self, rw):
        try:
            tail = rw.environ['locals.path_info'].lstrip('/')
            path = tail.split('/')
            method = getattr(self, path[0])
        except AttributeError:
            data = json.dumps({
                'code': -1,
                'msg': 'unknow path'
            })
            rw.send_response_and_close('404 Not Found',
                                       headers=[('Content-Type', 'application/json')], content=bytes(data, 'utf-8'))
        else:
            self.rw = rw
            return method(rw)

    def living(self, rw):
        form = Form(rw)
        token = form['token']
        try:
            data = tokenizer.unpack(token)
        except VerificationError:
            data = json.dumps({
                'code': 1,
                'msg': 'Invalid token'
            })
        except:
            data = json.dumps({
                'code': -1,
                'msg': 'Error'
            })
        else:
            phone = data.split('&')[0]
            data = json.dumps({
                'code': 0,
                'msg': 'ok',
                'data': {
                    'phone': phone,
                }
            })
        return rw.send_response_and_close(
            headers=[('Content-Type', 'application/json')], content=bytes(data, 'utf-8'))

    def captcha(self, rw):
        tail = rw.environ['locals.path_info'].lstrip('/')
        is_assert = tail.split('/')[-1]
        if is_assert == 'assert':
            captcha = yun.captcha.new()
        else:
            captcha = yun.captcha.new(rw)
        if captcha:
            data = json.dumps({
                'code': 0,
                'msg': 'ok',
                'data': {
                    'src': captcha.media.img_src,
                    'token': captcha.token
                }
            })
        else:
            data = json.dumps({
                'code': 1,
                'msg': 'valid',
            })
        rw.send_response_and_close(
            headers=[('Content-Type', 'application/json')], content=bytes(data, 'utf-8'))

    def salt(self, rw):
        tail = rw.environ['locals.path_info'].lstrip('/')
        phone = tail.split('/')[-1]
        conn = yun.runtime.get_users_db()
        row = conn.cursor().execute(
            'SELECT password_salt FROM users WHERE phone=?',
            (phone,)).fetchone()
        if row is None:
            password_salt = xxhash.xxh32_hexdigest(fakesalt + phone.encode())
        else:
            password_salt = row[0]
        # self.rw.send_response_and_close(
        #     headers=[('Content-Type', 'text/plain')],
        #     content=password_salt.encode()
        # )
        data = json.dumps({
            'code': 0,
            'msg': 'ok',
            'data': password_salt
        })
        self.rw.send_response_and_close(
            headers=[('Content-Type', 'application/json')], content=bytes(data, 'utf-8'))

    def avatar(self, rw):
        form = Form(rw)
        phone = form['phone']
        db = yun.runtime.get_users_db()
        row = db.cursor().execute(
            'SELECT id FROM users WHERE phone=?', (phone,)).fetchone()
        buf = None
        if row is None:
            return rw.not_found()
        try:
            blob = db.blobopen('main', 'users', 'avatar', row[0], 1)
            buf = blob.read()
            blob.close()
        except apsw.SQLError:
            return rw.not_found()
        else:
            headers = [('Content-Type', 'image/png'),
                       ('Content-Length', '{}'.format(len(buf)))]
            return rw.send_response_and_close('200 OK', headers, buf)

    def modify_avatar(self, rw):
        filename = None
        buf = None
        for reader in multipart(
                rw, filename_encoding='utf-8'):
            if 'file' == reader.name:
                filename = reader.filename
                buf = reader.read()
            else:
                token = reader.read()
                try:
                    data = tokenizer.unpack(token)
                except VerificationError:
                    data = json.dumps({
                        'code': 1,
                        'msg': 'Invalid token'
                    })
                else:
                    phone = data.split('&')[0]
            reader.close()
        if len(buf) > 0 and phone:
            db = yun.runtime.get_users_db()
            zero_blob = apsw.zeroblob(len(buf))
            db.cursor().execute(
                'UPDATE users SET avatar=? WHERE phone=?', (zero_blob, phone))
            row = db.cursor().execute(
                'SELECT id FROM users WHERE phone=?', (phone,)).fetchone()
            blob = db.blobopen("main", "users", "avatar", row[0], 1)
            blob.write(buf)
            blob.close()
        data = json.dumps({
            'code': 0,
            'msg': 'ok',
            'data': ''
        })
        self.rw.send_response_and_close(
            headers=[('Content-Type', 'application/json')], content=bytes(data, 'utf-8'))

    def upload(self, rw):
        filename = None
        buf = None
        for reader in multipart(
                rw, filename_encoding='utf-8'):
            if 'file' == reader.name:
                filename = reader.filename
                buf = reader.read()
            else:
                token = reader.read()
                try:
                    data = tokenizer.unpack(token)
                except VerificationError:
                    data = json.dumps({
                        'code': 1,
                        'msg': 'Invalid token'
                    })
                else:
                    phone = data.split('&')[0]
            reader.close()
        if len(buf) > 0 and phone:
            db = yun.runtime.get_userspace_db_by_phone(phone)
            cr = db.cursor()
            cr.execute(
                'CREATE TABLE IF NOT EXISTS user ('
                'id               INTEGER       PRIMARY KEY,'
                'phone            NVARCHAR( 64),'
                'username         NVARCHAR( 64),'
                'avatar           LONGBLOB'
                ');'
            )
            zero_blob = apsw.zeroblob(len(buf))
            db.cursor().execute(
                'UPDATE user SET avatar=? WHERE phone=?', (zero_blob, phone))
            blob = db.blobopen("main", "user", "avatar", 1, 1)
            blob.write(buf)
            blob.close()
        data = json.dumps({
            'code': 0,
            'msg': 'ok',
            'data': ''
        })
        self.rw.send_response_and_close(
            headers=[('Content-Type', 'application/json')], content=bytes(data, 'utf-8'))

    def list(self, rw):
        form = Form(rw)
        page = int(form['p'])
        db = yun.runtime.get_users_db()
        data = pagination(db, 'users', page, self.limit,
                          ('id', 'phone', 'username'))
        data = json.dumps({
            'code': 0,
            'msg': 'ok',
            'data': data
        })
        self.rw.send_response_and_close(
            headers=[('Content-Type', 'application/json')], content=bytes(data, 'utf-8'))


def pagination(db, table, page, limit, fields):
    if page == -1:
        return {
            'data': [],
            'next': -1
        }
    count = db.cursor().execute(
        'SELECT COUNT(*) FROM {}'.format(table)).fetchone()[0]
    offset = page * limit
    if len(fields) < 1:
        fields_str = '*'
    else:
        fields_str = ','.join(fields)
    sql_str = 'SELECT {} FROM {} ORDER BY id LIMIT ? OFFSET ?'.format(fields_str, table).format(*fields)
    rows = db.cursor().execute(sql_str, (limit, offset)).fetchall()
    if count > limit * (page + 1):
        next = page + 1
    else:
        next = -1
    return {
        'data': rows,
        'next': next
    }


json_resp = JsonResponse()
fakesalt = Crypto.Random.get_random_bytes(8)
