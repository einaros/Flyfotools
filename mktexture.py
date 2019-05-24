#!ENV/bin/python
# -*- coding: utf-8 -*-
import sys, gdal, math, os, time
import requests, requests_cache
from gdalconst import GA_ReadOnly
from PIL import Image

requests_cache.install_cache('cache', backend='sqlite', expire_after=300)

def tmpfile():
  return '%s/%s.png'%(tmp_dir, str(time.time()).replace('.', ''))

max_h_res = 3000
max_v_res = 3000
#tile_size_x = 579784.3874127793 - 579319.941611998 
#print(1405 / tile_size_x)
crs_to_px_h = 3 # px per crs unit
#tile_size_y = 6634915.342022805 - 6634727.580304055
crs_to_px_v = 3 # px per crs unit
tmp_dir = os.path.dirname(os.path.realpath(__file__)) + '/tmp'

url_base = """
curl -s 'https://agsservices.norgeibilder.no/arcgis/rest/services/ortofoto/ImageServer/exportImage?token={token}&f=image&format=jpgpng&mosaicRule=%7B%22mosaicMethod%22%3A%22esriMosaicAttribute%22%2C%22where%22%3A%22nib_project_id%20IN%20({project})%22%2C%22sortField%22%3A%22lowps%22%2C%22sortValue%22%3A%220%22%2C%22ascending%22%3Atrue%2C%22mosaicOperation%22%3A%22MT_FIRST%22%7D&bbox={minx}%2C{miny}%2C{maxx}%2C{maxy}&imageSR=258{utm}&bboxSR=258{utm}&size={resx}%2C{resy}' -H 'Referer: https://norgeibilder.no/?level=18&utm={utm}&projects=2361&layers=&plannedOmlop=0&plannedGeovekst=0' -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.103 Safari/537.36' -H 'DNT: 1' --compressed -o {filename}
"""

def get_token():
  req = requests.get('https://norgeibilder.no/?level=17&utm=32&projects=2361&layers=&plannedOmlop=0&plannedGeovekst=0')
  text = req.text
  token_pos = text.index('nibToken') + 11
  return text[token_pos:text.index('\'', token_pos)]

def merge(images, width):
  images = [item for sublist in images for item in sublist]
  height = len(images) / width
  loaded_imgs = [Image.open(i) for i in images]
  widthpx = 0
  heightpx = 0
  for i in range(width):
    w,h = loaded_imgs[i].size
    widthpx += w
  for i in range(0, len(images), width):
    w,h = loaded_imgs[i].size
    heightpx += h
  new_im = Image.new('RGB', (widthpx, heightpx))
  for i, im in enumerate(loaded_imgs):
    x = int(i%width)
    y = int(i/width)
    new_im.paste(im, (x * int(widthpx/width), int((height-1-y) * int(heightpx/height))))
  return new_im

def main(in_path, out_path, project=2229, utm=32):
  project = int(project)
  utm = int(utm)
  token = get_token()
  data = gdal.Open(in_path, GA_ReadOnly)
  geoTransform = data.GetGeoTransform()
  minx = geoTransform[0]
  maxy = geoTransform[3]
  maxx = minx + geoTransform[1] * data.RasterXSize
  miny = maxy + geoTransform[5] * data.RasterYSize
  print('bbox: %s'%([minx, miny, maxx, maxy]))
  dx = maxx - minx
  dy = maxy - miny
  img_width = dx * crs_to_px_h
  img_height = dy * crs_to_px_v
  print('total img size: %sx%s'%(img_width, img_height))
  ntx = math.ceil(img_width / max_h_res)
  nty = math.ceil(img_height / max_v_res)
  print('tiles: %sx%s'%(ntx, nty))
  tiles = []
  for iy in range(nty):
    tile_row = []
    for ix in range(ntx):
      bbox = [
        minx + ix * max_h_res / crs_to_px_h,
        miny + iy * max_v_res / crs_to_px_v,
        minx + (1+ix) * max_h_res / crs_to_px_h,
        miny + (1+iy) * max_v_res / crs_to_px_v,
      ]
      imagepath = tmpfile()
      tile_row.append(imagepath)
      url = url_base.format(
        token = token,
        project = project,
        minx = bbox[0],
        miny = bbox[1],
        maxx = bbox[2],
        maxy = bbox[3],
        utm = utm,
        resx = max_h_res,
        resy = max_v_res,
        filename = imagepath
      )
      print(url)
      os.system(url)
    tiles.append(tile_row)
  im = merge(tiles, ntx)
  im_w,im_h = im.size
  im = im.crop((0, im_h - img_height, img_width, im_h))
  tmp_output = tmpfile()
  im.save(tmp_output)
  os.system('gdal_translate -of GTiff -a_ullr {minx} {maxy} {maxx} {miny} -a_srs EPSG:258{utm} {tmp} {output}'.format(
    minx = minx, 
    maxx = maxx, 
    miny = miny, 
    maxy = maxy, 
    utm = utm,
    tmp = tmp_output,
    output = out_path
  ))
  data = None

if __name__ == '__main__':
  sys.exit(main(*sys.argv[1:]))
