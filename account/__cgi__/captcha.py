import json
import yun

def GET(rw):
    captcha = yun.captcha.new(rw)
    if captcha:
        data = json.dumps({
            'data': {
                'src': captcha.media.img_src,
                'token': captcha.token
            }
        })
        rw.send_response_and_close(
            headers=[('Content-Type', 'application/json')], content=bytes(data, 'utf-8'))
    else:
        rw.send_html_and_close(content='')
