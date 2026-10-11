import io
import secrets
import warnings
from pathlib import Path
from flask import Blueprint,current_app,g,jsonify,request,send_file
from PIL import Image,ImageOps,UnidentifiedImageError
from pillow_heif import register_heif_opener
register_heif_opener()
from werkzeug.exceptions import BadRequest,NotFound,Conflict
from .core import login_required,rate_limit,payload,boolean
from .db import get_db,atomic
from .listings import fetch_listing,SENSITIVE
bp=Blueprint('media',__name__)


def normalize_image(stream):
    raw=stream.read(8*1024*1024+1)
    if len(raw)>8*1024*1024: raise BadRequest('Image must be at most 8 MB')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                if image.format not in ('JPEG','PNG','WEBP','HEIF'): raise BadRequest('JPEG, PNG, WebP, or HEIC required')
                if image.width*image.height>40_000_000: raise BadRequest('Image exceeds 40 megapixels')
                image.load();image=ImageOps.exif_transpose(image).convert('RGB');image.thumbnail((2000,2000))
                # Reconstruct pixels so EXIF, embedded thumbnails and metadata are not retained.
                clean=Image.new('RGB',image.size);clean.paste(image)
                output=io.BytesIO();clean.save(output,'JPEG',quality=88)
                return output.getvalue(),clean.width,clean.height
    except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError,Image.DecompressionBombWarning):
        raise BadRequest('Invalid or oversized image')


@bp.post('/api/listings/<int:listing_id>/images')
@login_required
def upload(listing_id):
    rate_limit('upload',40)
    row=fetch_listing(listing_id,True)
    if row['status']!='OPEN': raise Conflict('Only OPEN reports accept new images')
    if 'image' not in request.files: raise BadRequest('multipart/form-data field image is required')
    raw,width,height=normalize_image(request.files['image'].stream)
    name=secrets.token_hex(24)+'.jpg';path=Path(current_app.config['UPLOAD_DIR'])/name
    path.write_bytes(raw)
    try:
        with atomic() as db:
            row=fetch_listing(listing_id,True)
            if row['status']!='OPEN': raise Conflict('Report is no longer OPEN')
            if db.execute('SELECT COUNT(*) FROM images WHERE listing_id=?',(listing_id,)).fetchone()[0]>=5: raise BadRequest('Maximum five images per report')
            image_id=db.execute('INSERT INTO images(listing_id,storage_name,width,height) VALUES(?,?,?,?)',(listing_id,name,width,height)).lastrowid
            db.execute('UPDATE listings SET version=version+1 WHERE id=?',(listing_id,))
    except BaseException:
        path.unlink(missing_ok=True);raise
    return jsonify(id=image_id,url=f'/api/images/{image_id}',is_public=False,width=width,height=height),201


@bp.get('/api/images/<int:image_id>')
@login_required
def view(image_id):
    row=get_db().execute('''SELECT i.*,l.creator_id,l.visibility FROM images i JOIN listings l ON l.id=i.listing_id WHERE i.id=?''',(image_id,)).fetchone()
    if not row or not (row['creator_id']==g.user['id'] or (row['visibility']=='PUBLIC' and row['is_public'])): raise NotFound('Image not found')
    return send_file(Path(current_app.config['UPLOAD_DIR'])/row['storage_name'],mimetype='image/jpeg',conditional=False)


@bp.patch('/api/images/<int:image_id>')
@login_required
def visibility(image_id):
    public=boolean(payload().get('is_public'),'is_public')
    with atomic() as db:
        row=db.execute('SELECT * FROM images WHERE id=?',(image_id,)).fetchone()
        if not row: raise NotFound('Image not found')
        listing=fetch_listing(row['listing_id'],True)
        if listing['category'] in SENSITIVE and public: raise BadRequest('Sensitive item photos must remain private')
        db.execute('UPDATE images SET is_public=? WHERE id=?',(int(public),image_id))
    return jsonify(id=image_id,is_public=public)


@bp.delete('/api/images/<int:image_id>')
@login_required
def delete(image_id):
    payload()
    with atomic() as db:
        row=db.execute('SELECT * FROM images WHERE id=?',(image_id,)).fetchone()
        if not row: raise NotFound('Image not found')
        listing=fetch_listing(row['listing_id'],True)
        if listing['status']!='OPEN': raise Conflict('Only OPEN report images may be removed')
        db.execute('DELETE FROM images WHERE id=?',(image_id,))
        db.execute('UPDATE listings SET version=version+1 WHERE id=?',(listing['id'],))
    (Path(current_app.config['UPLOAD_DIR'])/row['storage_name']).unlink(missing_ok=True)
    return jsonify(message='Image deleted')
