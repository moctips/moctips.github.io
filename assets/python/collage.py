import flickrapi

import random

import logging
import functools
import json

import urllib.request
from PIL import Image
from io import BytesIO

import os
import pathlib


random.seed(1234)  # reproducible images


# Flickr api access key
flickr = flickrapi.FlickrAPI(
    'e358383789f8d18e68d4fa0bc1990e47', '1c28595375ef2fce', cache=True)


def safe_name(filename):
    """
    Generate a safe file name from a string
    """
#     return "".join([c for c in filename if c.isalpha() or c.isdigit() or c==' ']).rstrip()
    return filename.replace('/', '')


def max_resolution(labels):
    """
    Pick the best resolution from available resolutions:
    Choose from best options like:
    ['Square', 'Large Square', 'Thumbnail', 'Small', 'Small 320', 'Small 400', 'Medium', 'Medium 640', 'Medium 800', 'Large', 'Large 1600', 'Large 2048']
    """
    original_label = 'Original'
    if original_label in labels:
        return original_label

    def sort_by_size(labels, size='Large'):
        labels_by_size = filter(lambda label: size in label and any(
            char.isdigit() for char in label), labels)
        # Extract dimension (second string in label) for sorting
        try:
            return sorted(labels_by_size, key=lambda label: int(label.split(" ")[1]), reverse=True)
        except Exception as e:
            # fall back to unsorted
            return labels

    large = sort_by_size(labels, 'Large')
    medium = sort_by_size(labels, 'Medium')
    small = sort_by_size(labels, 'Small')

    best_to_worst_resolution = large + medium + small
    return best_to_worst_resolution[0]


@functools.lru_cache()
def get_nsid(**kwargs):
    """
    lookup user NSID by username. NSID is required for other API operations
    under the people submodule.
    """
    if 'username' not in kwargs:
        raise Exception(f'expected `username` in kwargs')
    username = kwargs['username']
    response = json.loads(
        flickr.people.findByUsername(username=username, format='json')
    )

    # In case of API failure, such as {'stat': 'fail', 'code': 1, 'message': 'User not found'}
    if 'code' in response and response['code'] == 1:
        raise Exception(response)

    return response['user']['nsid']


@functools.lru_cache()
def get_photo_url(photo_id):
    response = json.loads(flickr.photos.getSizes(
        photo_id=photo_id, format='json'))
    sizes = response['sizes']['size']
    size_labels = [size['label'] for size in sizes]
    max_resolution_label = max_resolution(size_labels)

    max_resolution_sizes = [
        size for size in sizes if size['label'] == max_resolution_label]
    max_resolution_size = max_resolution_sizes[0]
    return max_resolution_size['source']


@functools.lru_cache()
def get_photo_urls_from_gallery(gallery_id):
    response = json.loads(flickr.galleries.getPhotos(
        gallery_id=gallery['id'], format='json'))
    photo_urls = list(map(lambda photo: get_photo_url(
        photo['id']), response['photos']['photo']))
    return photo_urls


@functools.lru_cache()
def load_photo_from_url(url):
    response = urllib.request.urlopen(url)
    f = BytesIO(response.read())
    return Image.open(f)


def square_crop(image):
    width, height = image.size   # Get dimensions
    min_dim = min(width, height)

    left = (width - min_dim)/2
    top = (height - min_dim)/2
    right = (width + min_dim)/2
    bottom = (height + min_dim)/2

    return image.crop((left, top, right, bottom))


def create_collage(urls, rows=4, cols=5, img_size=500):
    # make collage fit cols first, then rows
    cols = min(cols, len(urls))
    rows = min(rows, len(urls)//cols)

    if cols*rows > len(urls):
        print(
            f'Warning: Not enough images to fit desired dimensions. {len(url) - rows*cols} images will be lost.')

    urls = urls[:rows*cols]  # grab however many photos will fit in the collage

    images = map(lambda url: load_photo_from_url(url), urls)
    square_images = map(lambda image: square_crop(image), images)
    resized_images = map(lambda image: image.resize(
        (img_size, img_size)), square_images)

    grid = Image.new('RGB', size=(cols*img_size, rows*img_size))

    for i, image in enumerate(resized_images):
        grid.paste(image, box=(i % cols*img_size, i//cols*img_size))

    return grid


if __name__ == '__main__':
    # get galleries
    response = json.loads(
        flickr.galleries.getList(
            user_id=get_nsid(username='alex_mocs'),
            format='json'
        ))

    galleries = response['galleries']['gallery']
    for gallery in galleries:
        gallery_id = gallery['id']
        gallery_name = gallery['title']['_content']

        # make a folder to save output images
        output_folder = 'gallery_previews'
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        photo_urls = get_photo_urls_from_gallery(gallery_id)

        # prevent photos from largely coming from the same person
        random.shuffle(photo_urls)

        print(f'Saving {len(photo_urls)} images to {gallery_name}')

        collage = create_collage(photo_urls)
        collage.save(f'{output_folder}/{gallery_name}.jpg')
