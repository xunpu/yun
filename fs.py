import apsw
import os.path
import filetype
from PIL import Image
from io import BytesIO
from uuid import uuid4
from datetime import datetime

from slowdown.fs import FS
from slowdown.cgi import Form, multipart
from slowdown.token import VerificationError

import yun.runtime
from yun.runtime import API, get_users_db, \
    get_userdb_by_id, get_userspace_by_id, \
    get_userdb_by_phone, get_userspace_by_phone
from yun.api import DATA_OK, DATA_INVALID_TOKEN


fs = FS()

FILE_SIZE_BOUNDARY = 1024 * 1024 * 2
SELECT_LIMIT = 20
ROOT = 'root'


@API()
def view(rw):
    form = Form(rw)
    path = rw.environ['locals.api_info'].lstrip('/').split('/')
    if len(path) == 1:
        is_thumb = False
        id_ = path[0].split('.')[0]
    else:
        is_thumb = True
        id_ = path[1].split('.')[0]
    user_id = int(form['id'])
    mydb = get_userdb_by_id(user_id)
    try:
        fileobj = mydb.cursor().execute(
            'SELECT uuid, name, mime, size, blob, thumb FROM fs WHERE uuid=?',
            (id_,)).fetchone()
    except:
        return rw.not_found()
    else:
        if is_thumb:
            return rw.send_response_and_close(
                headers=[('Content-Type', fileobj[2])],
                content=fileobj[-1])
        else:
            if fileobj[-3] <= FILE_SIZE_BOUNDARY:
                return rw.send_response_and_close(
                    headers=[('Content-Type', fileobj[2])],
                    content=fileobj[-2])
            else:
                # token = form['token']
                # try:
                #     code = yun.runtime.tokenizer.unpack(token)
                # except VerificationError:
                #     return DATA_INVALID_TOKEN
                # else:
                #     phone = code.split('&')[0]
                #     userspace = get_userspace_by_id(user_id)
                userspace = get_userspace_by_id(user_id)
                path = os.path.join(userspace,
                                    fileobj[0][:2], fileobj[0][2:4], fileobj[0])
                f = fs.open(path)
                rw.start_chunked(headers=[('Content-Type', fileobj[2])])
                while True:
                    data = f.read(8192)
                    rw.write(data)
                    rw.flush()
                    if not data:
                        break
                f.close()
                rw.close()


@ API()
def ls(rw):
    form = Form(rw)
    token = form['token']
    range = form.get('range')
    try:
        code = yun.runtime.tokenizer.unpack(token)
    except VerificationError:
        return DATA_INVALID_TOKEN
    else:
        phone = code.split('&')[0]
        mydb, user_id = get_userdb_by_phone(phone)

    filetype = form.get('type', '')
    if filetype:
        filetype = 'AND type={}'.format(filetype)

    ext = tuple(filter(None, set(form.get('ext', '').split(','))))
    if len(ext) > 1:
        ext_str = 'AND extension IN {}'.format(ext)
    elif len(ext) == 1:
        ext_str = 'AND extension IN ("{}")'.format(ext[0])
    else:
        ext_str = ''

    pid = rw.environ['locals.api_info'].lstrip('/') or ROOT
    if range == 'all':
        pid_str = ''
    else:
        pid_str = 'AND parent="{}"'.format(pid)

    page = (int(form.get('page', 1)) - 1) * SELECT_LIMIT
    files = mydb.cursor().execute(
        ('SELECT creator, phone, name, type, extension, size,'
         ' parent, path, uuid, create_time, modify_time, creator'
         ' FROM (SELECT * FROM fs WHERE state=0 AND creator=? '
         ' {} {} {} '
         ' ORDER BY create_time DESC)'
         ' LIMIT ? OFFSET ?').format(filetype, ext_str, pid_str), (user_id, SELECT_LIMIT, page)).fetchall()
    return {'code': 0, 'msg': 'ok', 'data': files}


@ API()
def move(rw):
    form = Form(rw)
    pid = form['pid'] or ROOT
    token = form['token']
    ids_orig = form['ids'].split(',')
    ids = tuple(ids_orig)

    try:
        code = yun.runtime.tokenizer.unpack(token)
    except VerificationError:
        return DATA_INVALID_TOKEN
    else:
        phone = code.split('&')[0]
        mydb, user_id = get_userdb_by_phone(phone)

    if pid in ids:
        return {'code': 11, 'msg': '移动位置冲突', 'data': []}
    if len(ids) == 0:
        return {'code': 12, 'msg': '未选择文件', 'data': []}
    if len(ids) == 1:
        ids = '("{}")'.format(ids[0])

    cr = mydb.cursor()
    if pid != ROOT:
        path = cr.execute(
            'SELECT path FROM fs WHERE creator=? AND type=1 AND uuid=?', (user_id, pid,)).fetchone()[0]
        for id_ in list(filter(None, path.split('/'))):
            if id_ in ids:
                return {'code': 13, 'msg': '移动位置冲突', 'data': []}
    else:
        path = '/'
    res = cr.execute(
        'SELECT * FROM fs WHERE creator="{}" AND uuid IN {}'.format(user_id, ids)).fetchall()
    for data in res:
        parent = data[-1]
        path_ = data[-2]
        id_ = data[11]
        type_ = data[4]
        if parent == pid:
            break
        else:
            new_path = '{}/{}'.format(path, (pid !=
                                             ROOT and pid or '')).replace('//', '/')
            cr.execute('UPDATE fs SET path=?, parent=? WHERE creator=? AND uuid=?',
                       (new_path, pid, user_id, id_))
            if path_ == '/' and not new_path.endswith('/'):
                new_path += '/'
            if new_path == '/':
                new_path = ''
            if type_ == 1:
                like_path = '{}/{}'.format(path_, id_).replace('//', '/')
                cr.execute(('UPDATE fs SET path=replace(path, ?, ?) '
                            'WHERE creator=? AND uuid!=? AND path LIKE ?'),
                           (path_, new_path, user_id, id_, "%{}%".format(like_path)))
    return DATA_OK


@ API()
def remove(rw):
    form = Form(rw)
    token = form['token']
    ids_orig = form['ids'].split(',')
    ids = tuple(ids_orig)
    if len(ids) == 0:
        return {'code': 21, 'msg': '未选择文件', 'data': []}
    if len(ids) == 1:
        ids = '("{}")'.format(ids[0])
    try:
        code = yun.runtime.tokenizer.unpack(token)
    except VerificationError:
        return DATA_INVALID_TOKEN
    else:
        phone = code.split('&')[0]
        mydb, user_id = get_userdb_by_phone(phone)

    cr = mydb.cursor()
    for id_ in ids_orig:
        ids_ = cr.execute('SELECT uuid FROM fs WHERE state=0 AND creator="{}" AND path LIKE "%{}%"'.format(
            user_id, id_)).fetchall()
        for uid in ids_:
            cr.execute('UPDATE card SET state=1 WHERE uuid=?', (uid[0],))
            cr.execute('UPDATE article SET state=1 WHERE uuid=?', (uid[0],))
        cr.execute('UPDATE fs SET state=1 WHERE state=0 AND creator="{}" AND path LIKE "%{}%"'.format(
            user_id, id_))
    cr.execute('UPDATE card SET state=1 WHERE state=0 AND creator="{}" AND uuid IN {}'.format(
        user_id, ids))
    cr.execute('UPDATE article SET state=1 WHERE state=0 AND creator="{}" AND uuid IN {}'.format(
        user_id, ids))
    cr.execute('UPDATE fs SET state=1 WHERE state=0 AND creator="{}" AND uuid IN {}'.format(
        user_id, ids))
    return DATA_OK


@ API()
def delete(rw):
    pass


@ API()
def rename(rw):
    form = Form(rw)
    name = form['name']
    token = form['token']
    fid = form['fid']
    pid = form['pid'] or ROOT
    if not name:
        return {'code': 31, 'msg': '文件名错误', 'data': []}
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
        return {'code': 32, 'msg': '文件名已存在', 'data': []}
    cr.execute(
        'UPDATE fs SET name=? WHERE creator=? AND uuid=?', (name, user_id, fid))
    return DATA_OK


@ API()
def mkdir(rw):
    form = Form(rw)
    name = form['name']
    if not name:
        return {'code': 41, 'msg': '文件名错误', 'data': []}
    token = form['token']
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
        'SELECT COUNT(*) FROM fs WHERE type=1 AND state=0 AND creator=? AND name=? AND parent=?',
        (user_id, name, pid)).fetchone()[0]
    if exsit > 0:
        return {'code': 42, 'msg': '目录已存在', 'data': []}
    if pid != ROOT:
        path = cr.execute('SELECT path FROM fs WHERE state=0 AND uuid=?',
                          (pid,)).fetchone()[0]
        if path == '/':
            path = '{}{}'.format(path, pid)
        else:
            path = '{}/{}'.format(path, pid)
    create_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S %f')
    cr.execute(
        ('INSERT INTO fs (creator, phone, state, type, name '
            ', uuid, create_time, modify_time, parent, path) '
            ' VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'),
        (user_id, phone, 0, 1, name, uuid4().hex, create_time, create_time, pid, path))
    return DATA_OK


@ API()
def upload(rw):
    params = {}
    for part in multipart(rw, filename_encoding='utf-8'):
        if 'file' == part.name:
            return real_upload(params, part)
        else:
            params[part.name] = part.read().decode()
            part.close()


def real_upload(params, fileobj):
    try:
        data = yun.runtime.tokenizer.unpack(params['token'])
    except VerificationError:
        return DATA_INVALID_TOKEN
    else:
        phone = data.split('&')[0]
        mydb, user_id = get_userdb_by_phone(phone)
        userspace = get_userspace_by_phone(phone)[0]

    cr = mydb.cursor()
    pid = params['pid'] or ROOT
    if not user_id or fileobj is None:
        return {'code': 51, 'msg': '上传错误', 'data': []}
    create_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S %f')
    filename = fileobj.filename
    res = cr.execute(
        ('SELECT COUNT(*) FROM fs WHERE state=0 '
         'AND name="{}" AND parent="{}"').format(filename, pid))
    if res.fetchone()[0] > 0:
        time_str = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        filename = '{}-{}'.format(time_str, filename)
    buf = BytesIO()
    while True:
        data = fileobj.read1(8192)
        buf.write(data)
        if buf.tell() > FILE_SIZE_BOUNDARY:
            break
        elif not data:
            fileobj.close()
            break
    if buf.tell() <= 0:
        return {'code': 52, 'msg': '上传错误', 'data': []}
    uuid_ = uuid4().hex
    path = '/'
    if pid != ROOT:
        path = cr.execute(
            'SELECT path FROM fs WHERE state=0 AND uuid=?', (pid,)).fetchone()[0]
        if path == '/':
            path = '{}{}'.format(path, pid)
        else:
            path = '{}/{}'.format(path, pid)

    if buf.tell() <= FILE_SIZE_BOUNDARY:
        zero_blob = apsw.zeroblob(buf.tell())
        hash_name = ''
    else:
        zero_blob = apsw.zeroblob(0)

    typeguess = filetype.guess(buf.getvalue())
    extension, mime = '', ''
    if typeguess is None:
        if len(filename.split('.')) >= 2:
            extension = filename.split('.')[-1]
            mime = 'application/{}'.format(extension)
    else:
        mime = typeguess.mime
        extension = typeguess.extension

    is_image, thumb_zero_blob = False, apsw.zeroblob(0)
    if buf.tell() <= FILE_SIZE_BOUNDARY:
        if filetype.is_image(buf.getvalue()):
            is_image = True
            thumb_bytes = BytesIO()
            im = Image.open(buf)
            im.thumbnail((750, 750), Image.ANTIALIAS)
            im.save(thumb_bytes, 'png')
            thumb_zero_blob = apsw.zeroblob(len(thumb_bytes.getvalue()))
    else:
        os_path = os.path.join(userspace, uuid_[:2], uuid_[2:4])
        try:
            fs.os.makedirs(os_path)
        except FileExistsError:
            pass
        os_path = os.path.join(os_path, uuid_)
        f = fs.open(os_path, 'w+b')
        f.write(buf.getvalue())
        while True:
            data = fileobj.read1(8192)
            f.write(data)
            if not data:
                fileobj.close()
                break
        f.seek(0)
        bytesio = BytesIO(f.read())
        if filetype.is_image(bytesio.read(64)):
            is_image = True
            thumb_bytes = BytesIO()
            im = Image.open(bytesio)
            im.thumbnail((750, 750), Image.ANTIALIAS)
            im.save(thumb_bytes, 'png')
            thumb_zero_blob = apsw.zeroblob(len(thumb_bytes.getvalue()))
        f.close()

    cr.execute(
        ('INSERT INTO fs (creator, phone, state, type, name, extension, mime,'
            ' size, blob, thumb, uuid, create_time, modify_time, parent, path)'
            ' VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'),
        (user_id, phone, 0, 2, filename, extension, mime,
         buf.tell(), zero_blob, thumb_zero_blob, uuid_,
         create_time, create_time, pid, path))
    fid_ = None
    if is_image:
        fid_ = cr.execute(
            ('SELECT id FROM fs WHERE uuid="{}"'.format(uuid_))).fetchone()[0]
        blob = mydb.blobopen("main", "fs", "thumb", fid_, 1)
        blob.write(thumb_bytes.getvalue())
        blob.close()
    if buf.tell() <= FILE_SIZE_BOUNDARY:
        if not fid_:
            fid_ = cr.execute(
                ('SELECT id FROM fs WHERE uuid="{}"'.format(uuid_))).fetchone()[0]
        blob = mydb.blobopen("main", "fs", "blob", fid_, 1)
        blob.write(buf.getvalue())
        blob.close()
    else:
        pass
    return DATA_OK
