"""Recognize raster images served by blob storage as generic binary data."""

def raster_type(data):
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if data.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if data.startswith((b'GIF87a', b'GIF89a')):
        return 'image/gif'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return 'image/webp'
    if data[4:8] == b'ftyp' and data[8:12] in (b'avif', b'avis'):
        return 'image/avif'
    return ''


def image_content_type(header, data):
    declared = (header or '').split(';')[0].strip().lower()
    if declared.startswith('image/'):
        return declared
    if declared in ('', 'application/octet-stream', 'binary/octet-stream'):
        return raster_type(data)
    return ''
