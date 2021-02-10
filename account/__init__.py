import apsw
import xxhash
import os.path
import yun.runtime

default_expires_hours = 24 * 7


def create_userspace(id, phone, username):
    db = yun.runtime.get_userspace_db_by_id(id)
    cr = db.cursor()
    cr.execute(
        'CREATE TABLE IF NOT EXISTS user ('
        'id               INTEGER       PRIMARY KEY,'
        'phone            NVARCHAR (64),'
        'username         NVARCHAR (64),'
        'avatar           LONGBLOB'
        ');'
    )
    cr.execute(
        'INSERT INTO user (phone) VALUES (?)',
        (phone,)
    )


# def get_users():
#     pass


# def initialize(application):
#     var_dir = os.path.join(application.opts.home, 'var')
#     pyforce_dir = os.path.join(var_dir, 'yun')
#     runtime_dir = os.path.join(pyforce_dir, '_')
#     users_db_path = os.path.join(runtime_dir, 'users.db')
