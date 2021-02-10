import json
import apsw
import xxhash
import os.path
import Crypto.Random
from datetime import datetime

import yun
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

    def create(self, rw):
        form = Form(rw)
        actors = []
        if form['actor']:
            actors = list(int(x) for x in form['actor'].split(','))
        data = tokenizer.unpack(form['token'])
        phone = data.split('&')[0]
        db = yun.runtime.get_users_db()
        cr = db.cursor()
        creator_id = cr.execute(
            'SELECT id FROM users WHERE phone=?', (phone,)).fetchone()[0]
        if creator_id not in actors:
            actors.append(creator_id)
        create_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S %f')
        cr.execute(
            ('INSERT INTO job(creator, phone, title, start_time, end_time, actor, create_time, modify_time)'
                ' VALUES (?,?,?,?,?,?,?,?)'),
            (creator_id, phone, form['title'],
             form['start_time'], form['end_time'], form['actor'], create_time, create_time)
        )
        job_id = cr.execute(
            'select last_insert_rowid() from job').fetchone()[0]
        for actor_id in actors:
            cr.execute(
                ('INSERT INTO job_user(job, actor, creator, create_time)'
                 'VALUES (?,?,?,?)'),
                (job_id, actor_id, creator_id, create_time)
            )
        data = json.dumps({
            'code': 0,
            'msg': 'ok',
            'data': {}
        })
        return rw.send_response_and_close(
            headers=[('Content-Type', 'application/json')], content=bytes(data, 'utf-8'))

    def list(self, rw):
        form = Form(rw)
        data = tokenizer.unpack(form['token'])
        phone = data.split('&')[0]
        db = yun.runtime.get_users_db()
        cr = db.cursor()
        user_id = cr.execute(
            'SELECT id FROM users WHERE phone=?', (phone,)).fetchone()[0]
        job_user = cr.execute(
            'SELECT job FROM job_user WHERE actor=? ORDER BY create_time DESC', (user_id,)).fetchall()
        job_user = tuple(x[0] for x in job_user)
        if len(job_user) == 1:
            job_user = '({})'.format(job_user[0])
        data = cr.execute(
            'SELECT * FROM job WHERE id IN {}'.format(job_user)).fetchall()
        data.reverse()
        data = json.dumps({
            'code': 0,
            'msg': 'ok',
            'data': data
        })
        return rw.send_response_and_close(
            headers=[('Content-Type', 'application/json')], content=bytes(data, 'utf-8'))


json_resp = JsonResponse()
