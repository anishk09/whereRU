"""Sign into the running local API and inspect your reports. Cookies stay in memory."""
import http.cookiejar
import json
import urllib.request
import urllib.error


def main():
    base='http://127.0.0.1:5001'
    client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def call(path,body=None,csrf=None):
        headers={'Content-Type':'application/json'}
        if csrf:headers['X-CSRF-Token']=csrf
        req=urllib.request.Request(base+path,data=None if body is None else json.dumps(body).encode(),headers=headers)
        with client.open(req,timeout=15) as r:return json.load(r)
    try:
        email=input('Email (demo: owner@example.com): ').strip() or 'owner@example.com'
        print(call('/api/auth/request-code',{'email':email}))
        code=input('Code from the Flask terminal (or email if SMTP enabled): ').strip()
        logged=call('/api/auth/verify-code',{'email':email,'code':code});csrf=logged['csrf_token']
        print('Signed in:',logged['user']['email'])
        for path in ('/api/me/listings','/api/matches','/api/notifications','/api/maps/density'):
            print('\n'+path);print(json.dumps(call(path),indent=2))
        print(call('/api/auth/logout',{},csrf))
    except urllib.error.HTTPError as error:
        print('API error:',error.code,error.read().decode())
    except urllib.error.URLError:
        print('Cannot connect. Run python app.py in another terminal first.')


if __name__=='__main__':main()
