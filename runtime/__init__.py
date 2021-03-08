import json
import apsw
import time
import xxhash
import marshal
import os.path
import collections
import http.cookies
import urllib.parse
import Crypto.Random

import slowdown.token
import slowdown.lrucache

session_cookie_name = '_SESS'
default_session_expires = 0x5000000
token_keys_file = 'token-keys.bin'


def create_table_if_not_exists(db):
    exe = db.cursor().execute
    exe(
        'CREATE TABLE IF NOT EXISTS fs ('
        'id               INTEGER       PRIMARY KEY,'
        'creator          INTEGER,'
        'phone            NVARCHAR (64),'
        'state            INTEGER,'
        'type             INTEGER,'
        'name             NVARCHAR (64),'
        'extension        NVARCHAR (6),'
        'mime             NVARCHAR (64),'
        'size             INTEGER,'
        'thumb            LONGBLOB,'
        'blob             LONGBLOB,'
        'uuid             NVARCHAR (32),'
        'create_time      DATETIME,'
        'modify_time      DATETIME,'
        'path             NVARCHAR (128),'
        'parent           INTEGER'
        ');'
    )
    exe(
        'CREATE TABLE IF NOT EXISTS card ('
        'id               INTEGER       PRIMARY KEY,'
        'creator          INTEGER,'
        'uuid             NVARCHAR (32),'
        'phone            NVARCHAR (64),'
        'state            INTEGER,'
        'type             INTEGER,'
        'name             NVARCHAR (64),'
        'title            NVARCHAR (128),'
        'desc             NVARCHAR (1024),'
        'img              NVARCHAR (32),'
        'link             NVARCHAR (512),'
        'create_time      DATETIME,'
        'modify_time      DATETIME'
        ');'
    )
    exe(
        'CREATE TABLE IF NOT EXISTS article ('
        'id               INTEGER       PRIMARY KEY,'
        'creator          INTEGER,'
        'uuid             NVARCHAR (32),'
        'phone            NVARCHAR (64),'
        'state            INTEGER,'
        'type             INTEGER,'
        'name             NVARCHAR (64),'
        'title            NVARCHAR (128),'
        'desc             NVARCHAR (1024),'
        'img              NVARCHAR (32),'
        'content          NVARCHAR,'
        'create_time      DATETIME,'
        'modify_time      DATETIME'
        ');'
    )


def get_userspace_by_permission(p_lv):
    conn = apsw.Connection(users_db_path)
    row = conn.cursor().execute(
            'SELECT id FROM users WHERE permission=?', (p_lv, )
        ).fetchone()
    if row is None:
        return None
    else:
        return get_userdb_by_id(row[0]), row[0]


def get_userspace_by_phone(phone):
    conn = apsw.Connection(users_db_path)
    row = conn     \
        . cursor() \
        . execute(
            'SELECT id FROM users WHERE phone=?',
            (phone, )
        ) \
        . fetchone()
    if row is None:
        return None
    else:
        return get_userspace_by_id(row[0]), row[0]


def get_userspace_by_id(id):
    digest = xxhash.xxh32_hexdigest(b'%x' % id)
    base_dir = \
        os.path.join(
            userspace_dir,
            digest[0:2],
            digest[2:4],
            digest
        )
    if not fs.os.path.exists(base_dir):
        fs.os.makedirs(base_dir)
    return base_dir


def get_userdb_by_phone(phone):
    conn = apsw.Connection(users_db_path)
    row = conn     \
        . cursor() \
        . execute(
            'SELECT id FROM users WHERE phone=?',
            (phone, )
        ) \
        . fetchone()
    if row is None:
        return None
    else:
        return get_userdb_by_id(row[0]), row[0]


def get_userdb_by_id(id):
    digest = xxhash.xxh32_hexdigest(b'%x' % id)
    base_dir = \
        os.path.join(
            userspace_dir,
            digest[0:2],
            digest[2:4],
            digest
        )
    db_path = os.path.join(base_dir, digest)
    try:
        return apsw.Connection(db_path)
    except apsw.CantOpenError:
        fs.os.makedirs(base_dir)
    return apsw.Connection(db_path)


def get_users_db():
    return apsw.Connection(users_db_path)


def get_session(rw):
    cookie = rw.cookie
    if cookie is None:
        return None
    morsel = cookie.get(session_cookie_name)
    if morsel is None:
        return None
    return tokenizer.unpack(morsel.value)


def set_session(data, path='/', expires=default_session_expires):
    serialized = tokenizer.pack(data)
    cookie = http.cookies.SimpleCookie()
    cookie[session_cookie_name] = serialized
    if expires is not None:
        cookie[session_cookie_name]['Expires'] = expires
    if path is not None:
        cookie[session_cookie_name]['Path'] = path
    return cookie


def del_session(path='/'):
    cookie = http.cookies.SimpleCookie()
    cookie[session_cookie_name] = ''
    cookie[session_cookie_name]['Expires'] = -1
    if path is not None:
        cookie[session_cookie_name]['Path'] = path
    return cookie


def initialize(application):
    fs = application.fs
    var_dir = os.path.join(application.opts.home, 'var')
    pyforce_dir = os.path.join(var_dir, 'yun')
    runtime_dir = os.path.join(pyforce_dir, '_')
    userspace_dir = os.path.join(runtime_dir, 'userspace')
    users_db_path = os.path.join(runtime_dir, 'users.db')
    if not fs.os.path.isdir(userspace_dir):
        fs.os.makedirs(userspace_dir)
    token_keys_path = os.path.join(runtime_dir, token_keys_file)
    if fs.os.path.isfile(token_keys_path):
        with open(token_keys_path, 'rb') as file:
            serialized = file.read()
        aes_key, rc4_key = marshal.loads(serialized)
    else:
        aes_key = Crypto.Random.get_random_bytes(16)
        rc4_key = Crypto.Random.get_random_bytes(8)
        serialized = marshal.dumps((aes_key, rc4_key))
        with open(token_keys_path, 'wb') as file:
            file.write(serialized)
    tokenizer = slowdown.token.AES_RC4(aes_key, rc4_key)

    conn = apsw.Connection(users_db_path)
    user_table = conn     \
        . cursor() \
        . execute(
            'SELECT name FROM sqlite_master WHERE '
            'type="table" AND name="users"'
        ) \
        . fetchone()
    if user_table is None:
        conn.cursor().execute(
            'CREATE TABLE IF NOT EXISTS users ('
            'id             INTEGER       PRIMARY KEY,'
            'password_salt  NVARCHAR( 32)            ,'
            'password_hash  NVARCHAR( 64)            ,'
            'phone          NVARCHAR( 64) UNIQUE     ,'
            'email          NVARCHAR(128) UNIQUE     ,'
            'username       NVARCHAR( 64) UNIQUE     ,'
            'status         NVARCHAR( 64)            ,'
            'avatar         LONGBOLB                 ,'
            'permission     INTEGER                   '
            ');'
        )
    runtime = globals()
    runtime['application'] = application
    runtime['fs'] = fs
    runtime['var_dir'] = var_dir
    runtime['runtime_dir'] = runtime_dir
    runtime['userspace_dir'] = userspace_dir
    runtime['users_db_path'] = users_db_path
    runtime['tokenizer'] = tokenizer


ALLOW_METHODS = ['POST', 'GET']
JSON_HEADER = [('Content-Type', 'application/json')]
_404_NOT_FOUND = bytes(json.dumps({
    'code': -1,
    'msg': 'unknow path'
}), 'utf-8')
_200_OK = bytes(json.dumps({
    'code': 0,
    'msg': 'OK'
}), 'utf-8')


def json_resp(rw, text='200 OK', headers=JSON_HEADER, content=_200_OK):
    rw.send_response_and_close(text, headers=headers, content=content)


def json_resp_404(rw):
    json_resp(rw, '404 NOT FOUND', JSON_HEADER, _404_NOT_FOUND)


def API(method='POST'):
    def decorator(func):
        def __API__(*args, **kwargs):
            if method not in ALLOW_METHODS:
                json_resp_404(*args, **kwargs)
            return func(*args, **kwargs)
        return __API__
    return decorator
