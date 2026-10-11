from whereru import create_app
from pathlib import Path
from flask import send_from_directory
from werkzeug.exceptions import NotFound
app=create_app()
dist=Path(__file__).resolve().parents[1]/'dist'

@app.get('/')
def index():
    return send_from_directory(dist,'index.html')

@app.get('/<path:path>')
def frontend(path):
    if path.startswith('api/'):raise NotFound('API route not found')
    candidate=(dist/path).resolve()
    if not candidate.is_relative_to(dist.resolve()):raise NotFound()
    if candidate.is_file():return send_from_directory(dist,path)
    raise NotFound('Page or asset not found')

if __name__=='__main__':
    from whereru.expiry import start_expiry_worker
    start_expiry_worker(app)
    app.run(host='0.0.0.0' if app.config['DEMO_LAN_ALLOWED'] else '127.0.0.1',port=5003,debug=False,threaded=True)
