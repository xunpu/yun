from uuid import uuid4
from datetime import datetime

from slowdown.cgi import Form
from slowdown.token import VerificationError

import yun.runtime
from yun.runtime import API, get_users_db, \
    get_userdb_by_id, get_userspace_by_id, \
    get_userdb_by_phone, get_userspace_by_phone
from yun.api import DATA_OK, DATA_INVALID_TOKEN

FILE_SIZE_BOUNDARY = 1024 * 1024 * 2
SELECT_LIMIT = 20
ROOT = 'root'


@API()
def view(rw):
    form = Form(rw)
    token = form['token']
    uuid = form['uuid']
    try:
        code = yun.runtime.tokenizer.unpack(token)
    except VerificationError:
        return DATA_INVALID_TOKEN
    else:
        phone = code.split('&')[0]
        mydb, user_id = get_userdb_by_phone(phone)

    card = mydb.cursor().execute(
        'SELECT * FROM card WHERE state=0 AND creator=? AND uuid=?', (user_id, uuid)).fetchone()
    return {'code': 0, 'msg': 'ok', 'data': [card]}


@API()
def ls(rw):
    form = Form(rw)
    token = form['token']
    try:
        code = yun.runtime.tokenizer.unpack(token)
    except VerificationError:
        return DATA_INVALID_TOKEN
    else:
        phone = code.split('&')[0]
        mydb, user_id = get_userdb_by_phone(phone)

    page = (int(form.get('page', 1)) - 1) * SELECT_LIMIT
    cards = mydb.cursor().execute(
        ('SELECT * FROM (SELECT * FROM card WHERE state=0 AND creator=? '
         ' ORDER BY create_time DESC)'
         ' LIMIT ? OFFSET ?'), (user_id, SELECT_LIMIT, page)).fetchall()
    return {'code': 0, 'msg': 'ok', 'data': cards}


@API()
def modify(rw):
    form = Form(rw)
    name = form['name']
    title = form['title']
    desc = form['desc']
    img = form['img']
    link = form['link']
    token = form['token']
    uuid = form['uuid']
    if not (name and title and desc and link and img):
        return {'code': 121, 'msg': '缺少必要参数', 'data': []}
    try:
        data = yun.runtime.tokenizer.unpack(token)
    except VerificationError:
        return DATA_INVALID_TOKEN
    else:
        phone = data.split('&')[0]
        mydb, user_id = get_userdb_by_phone(phone)

    cr = mydb.cursor()
    pid = cr.execute('SELECT parent FROM fs WHERE uuid=?',
                     (uuid,)).fetchone()[0]
    exsit = cr.execute(
        ('SELECT COUNT(*) FROM fs WHERE state=0 '
         'AND creator=? AND name=? AND parent=? AND uuid!=?'),
        (user_id, name, pid, uuid)).fetchone()[0]
    if exsit > 0:
        return {'code': 122, 'msg': '卡片已存在', 'data': []}

    modify_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S %f')
    cr.execute('UPDATE fs SET name=?, modify_time=? WHERE uuid=?',
               (name, modify_time, uuid))
    cr.execute('UPDATE card SET name=?, title=?, desc=?, img=?, link=?, modify_time=? WHERE uuid=?',
               (name, title, desc, img, link, modify_time, uuid))
    return DATA_OK


@API()
def create(rw):
    form = Form(rw)
    name = form['name']
    title = form['title']
    desc = form['desc']
    img = form['img']
    link = form['link']
    token = form['token']
    pid = form['pid'] or ROOT
    if not (name and title and desc and link and img):
        return {'code': 111, 'msg': '缺少必要参数', 'data': []}
    pid = form.get('pid') or ROOT
    path = '/'
    try:
        data = yun.runtime.tokenizer.unpack(token)
    except VerificationError:
        return DATA_INVALID_TOKEN
    else:
        phone = data.split('&')[0]
        mydb, user_id = get_userdb_by_phone(phone)

    cr = mydb.cursor()
    exsit = cr.execute(
        'SELECT COUNT(*) FROM fs WHERE state=0 AND creator=? AND name=? AND parent=?',
        (user_id, name, pid)).fetchone()[0]
    if exsit > 0:
        return {'code': 112, 'msg': '卡片已存在', 'data': []}
    if pid != ROOT:
        path = cr.execute('SELECT path FROM fs WHERE state=0 AND uuid=?',
                          (pid,)).fetchone()[0]
        if path == '/':
            path = '{}{}'.format(path, pid)
        else:
            path = '{}/{}'.format(path, pid)
    create_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S %f')
    uuid_ = uuid4().hex
    cr.execute(
        ('INSERT INTO fs (creator, phone, state, type, name, '
            ' uuid, create_time, modify_time, parent, path) '
            ' VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'),
        (user_id, phone, 0, 3, name, uuid_, create_time, create_time, pid, path))
    cr.execute(
        ('INSERT INTO card (creator, uuid, phone, state, type, '
         ' name, title, desc, img, link, create_time, modify_time) '
         ' VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'),
        (user_id, uuid_, phone, 0, 1, name, title, desc, img, link, create_time, create_time))
    return DATA_OK
