import time
import collections
import Crypto.Random

import slowdown.token
import slowdown.captcha
import slowdown.lrucache

default_expiration_time        = 180
default_used_tokens_cache_size = 1000
default_retries_cache_size     = 2000

class Captcha(object):

    VERIFIED = True
    MISMATCH = False
    INVALID  = None

    def __init__(self, expiration_time=-1, used_tokens_cache_size=-1,
                 retries_cache_size=-1):
        if -1 == expiration_time:
            self.expiration_time = default_expiration_time
        else:
            self.expiration_time = expiration_time
        self.captcha = \
            slowdown.captcha.Captcha(
                     cache_size=90,
                expiration_time=self.expiration_time
            )
        self.tokenizer = \
            slowdown.token.AES_RC4(
                aes_key=Crypto.Random.get_random_bytes(16),
                rc4_key=Crypto.Random.get_random_bytes( 8)
            )
        self.used_tokens = \
            slowdown.lrucache.LRUCache(
                size=default_used_tokens_cache_size
                     if -1 == used_tokens_cache_size
                     else
                     used_tokens_cache_size
            )
        self.retries = \
            slowdown.lrucache.LRUCache(
                size=default_retries_cache_size
                     if -1 == retries_cache_size
                     else
                     retries_cache_size
            )

    def new(self, rw=None):
        if   rw is None or \
           self.retries.get(rw.environ['REMOTE_ADDR'], 0) > 0:
            expiration_time = int(time.time() + self.expiration_time)
            media = self.captcha.new()
            token = self.tokenizer.pack((media.text, expiration_time))
            return Result(media, token)
        else:
            return None

    def verify(self, text, token, rw=None):
        if   rw is  not None and \
           self.retries.get(rw.environ['REMOTE_ADDR'], 0) < 1:
            return self.VERIFIED
        if  not isinstance(token, str) or \
           self.used_tokens.get(token):
            return self.INVALID
        try:
            data = self.tokenizer.unpack(token)
        except slowdown.token.VerificationError:
            return self.INVALID
        except ValueError:
            return self.INVALID
        text2, expiration_time = data
        if int(time.time()) > expiration_time:
            return self.INVALID
        self.used_tokens[token] = 0
        if text2.lower() == text.strip().lower():
            return self.VERIFIED
        else:
            return self.MISMATCH

    def note_success(self, rw):
        self.retries.pop  (rw.environ['REMOTE_ADDR'])

    def note_failed (self, rw):
        ip               = rw.environ['REMOTE_ADDR']
        retries          = self.retries.get(ip, 0)
        self.retries[ip] = retries + 1

Result = collections.namedtuple('Result', ['media', 'token'])