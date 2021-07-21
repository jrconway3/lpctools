import os
import os.path
from glob import glob

from PIL import Image
import collections.abc
import numpy as np

# for a sheet:
# 	for each animation:
#		for each animation_layer:
#			assemble frames from images
#			offset each frame according to template
#			mask each frame according to template
#		combine all layers for each frame
#	concatenate animations
# 

from .recolor import Color
from .utils import *


COLOR_TRANSPARENT = Color(255,255,255,0)

class AnimationTemplate():

	# number of frames
	# frame size
	# offset for each frame
	def __init__(self, offsets=None, masks=None, frame_size=(64,64)):

		if offsets is None and masks is None:
			raise Exception('Must set `masks`, `offsets`, or both!')
		elif offsets is None and masks is not None:
			nframes = len(masks)
			self.masks = masks
			self.offsets = [(0,0)] * nframes
		elif offsets is not None and masks is None:
			self.offsets = offsets
			self.masks = []*len(offsets) # TODO
		else:
			self.offsets = offsets
			self.masks = masks
			# if nframes != len(self.offsets): 
			# 	raise Exception('If both `nframes` and `offsets` are provided, `nframes` must equal `len(offsets)`')

		self.frame_size = frame_size

	@property
	def nframes(self): return len(self.offsets)

	def apply(self, images):
		imgs = []
		transparent_img = Image.new(mode='RGBA', size=self.frame_size)
		tmp_img = Image.new(mode='RGBA',size=self.frame_size,color=COLOR_TRANSPARENT)
		box_whole = (0,0, self.frame_size[0], self.frame_size[1])

		for img, offset, mask in zip(images, self.offsets, self.masks):
			# (a, b, c, d, e, f)
			# (x, y) = (ax+by+c, dx+ey+f)
			# img.transform(img.size, Image.AFFINE, (1,0,offset[0],1,0,offset[1]))

			# box = offset + (
			# 	min(offset[0]+img.size[0], self.frame_size[0]), 
			# 	min(offset[1]+img.size[1], self.frame_size[1]))
			# box = offset
			tmp_img.paste(COLOR_TRANSPARENT, box=box_whole)

			if img is not None:
				# offset coordinates are w/r/t the middle of img
				box = (offset[0] - img.size[0]//2, 
					   offset[1] - img.size[1]//2)

			# image = Image.new(mode='RGBA',size=self.frame_size,color=COLOR_TRANSPARENT).paste(img, box=box, mask=mask)
			# new_img = Image.new(mode='RGBA',size=self.frame_size,color=COLOR_TRANSPARENT)

			# might be None if `pick_image` didn't find any images for this layer
			
				tmp_img.paste(img, box=box)
			# new_img.paste(img, box=box)
			# imgs.append(Image.composite(transparent_img, new_img, mask))
			imgs.append(Image.composite(transparent_img, tmp_img, mask))

			# yield image
			# imgs.append(new_img)

		return imgs

	@staticmethod
	def from_images(offsets=None, masks=None, mask_colors=['#ffffff'], **kwargs):
		_offsets = None
		if offsets is not None:
			_offsets = [img.getbbox()[:2] for img in offsets]

		_masks = None
		if masks is not None:
			mask_colors = [Color(mask_color).to_array() for mask_color in mask_colors]  #[np.newaxis, np.newaxis, :]
			# _masks = [Image.fromarray((np.array(img) == mask_color).all(axis=-1) * 255, mode='L') for img in masks]
			# _masks = [Image.fromarray( np.logical_not( (np.array(img) == mask_color).all(axis=-1) ) * 255, mode='L') for img in masks]
			# 
			# _masks = [Image.fromarray( ((np.array(img) == mask_color).all(axis=-1).astype('uint8') * 255) , mode='L') for img in masks]
			
			_masks = []
			for img in masks:
				arr = np.logical_or.reduce( [(np.array(img) == mask_color).all(axis=-1) for mask_color in mask_colors] )
				_masks.append(Image.fromarray( (arr.astype('uint8') * 255) , mode='L'))


			# for img in masks:
			# 	assert not (np.array(img) == mask_color).all(axis=-1).any()

		return AnimationTemplate(_offsets, _masks, **kwargs)



def pick_image(afi, images, verbose=False):
	""" picks the best image corresponding to (animation_name, direction, frame)
	"""
	# if afi in images:
	# 	if verbose: print(f"PICK {afi} --> {afi}")
	# 	return images[afi]

	choices = [afi, (afi[0], afi[1], None), (None, afi[1], afi[2]), (None, afi[1], None), (None, None, None)]
	for c in choices:
		if c in images:
			if verbose: print(f"PICK {afi} --> {c}  '{images[c].filename}'")
			return images[c]

	# c = 
	# if c in images:
	# 	if verbose: print(f"PICK {afi} --> {c}")
	# 	return images[c]

	# c = (None, None, None)
	# if c in images:
	# 	if verbose: print(f"PICK {afi} --> {c}")
	# 	return images[c]
	
	if verbose: print(f"miss {afi}")

def get_animation_templates(animations, offsets_image, masks_image, layout, verbose=False, **kwargs):
	offsets_images = layout.unpack_images(offsets_image)
	masks_images = layout.unpack_images(masks_image)

	templates = []
	for animation in animations:
		templates.append(
			AnimationTemplate.from_images(
				offsets = [pick_image(afi, offsets_images, verbose=verbose) for afi in animation.frames],
				masks = [pick_image(afi, masks_images, verbose=verbose) for afi in animation.frames],
				**kwargs
			)
		)
	return templates


def distribute_images_to_animations(animations, templates, images, verbose=False):
	"""take some set of base images and expand them to create a full set of animations

	animations: iterable of Animation
	templates: iterable of (AnimationTemplate | None)
	images: dict of (animation_name | None, direction | None, frame | None) : PIL.Image

	returns: dict of Animation : (list of images)
	"""

	output = {}
	for animation, template in zip(animations, templates):

		# identify the best image for each frame
		animation_images = [pick_image(afi, images, verbose=verbose) for afi in animation.frames]

		# apply offset(s) and masking
		if template is not None:
			output[animation] = template.apply(animation_images)
		else: 
			output[animation] = animation_images

	return output


def distribute_images_via_layout(images, layout, offsets_image, masks_image, animations=None, verbose=False):
	if animations is None: 
		animations = layout.get_animations()
	templates = get_animation_templates(animations, offsets_image = offsets_image, masks_image = masks_image, layout = layout)

	# { Animation(name,direction,N) : [ img1, img2, ... imgN], ... }
	animation_images = distribute_images_to_animations(animations, templates, images, verbose=verbose)
	images_distributed = {}
	for animation, imgs in animation_images.items():
		for afi, img in zip(animation.frames, imgs):
			images_distributed[afi] = img

	# assert False
	return layout.pack_images(images_distributed)


class Animation(collections.namedtuple('_AnimationTuple',['name','direction','nframes'])):
	@property
	def frames(self):
		for i in range(self.nframes):
			yield AnimationFrameID(self.name, self.direction, i)

	@staticmethod
	def make_directions(name, nframes, directions=['n','w','s','e']):
		return {direction: Animation(name,nframes,direction) for direction in directions}

animations = {
	'cast': Animation.make_directions('cast',7),
	'thrust': Animation.make_directions('thrust',8),
	'walk': Animation.make_directions('walk',9),
	'slash': Animation.make_directions('slash',6),
	'shoot': Animation.make_directions('shoot',13),
	'hurt': Animation.make_directions('hurt',6,['s']),
	'grab': Animation.make_directions('grab',3),
	'push': Animation.make_directions('push',9),
}

# class AnimationLayer():

# 	def __init__(self, template, images):
# 		pass


# class Animation():
# 	def __init__(self, layers)
# 		pass

# class AnimationsSheet():
# 	def __init__(self, animations):
# 		pass


# _AnimationFrameID = 

class AnimationFrameID(collections.namedtuple('_AnimationFrameID',['name','direction','frame'])):
	__slots__ = ()

	def __new__(cls, name=None,direction=None,frame=None):
		if frame is not None: frame = int(frame)
		return super().__new__(cls, name, direction, frame)

	def format(self,pattern):
		return format_placeholders(pattern,{
			'%n':self.name,
			'%d':self.direction,
			'%f':self.frame
		})

	@staticmethod
	def from_dict(d):
		return AnimationFrameID(
			d['name'] if 'name' in d else d['n'], 
			d['direction'] if 'direction' in d else d['d'], 
			d['frame'] if 'frame' in d else d['f'])


class AnimationLayout():
	def __init__(self, animation_positions, size=None, frame_size=(64,64)):
		assert isinstance(animation_positions, collections.abc.Mapping)

		self.inverse_positions = { tuple(pos) : AnimationFrameID(*afi) for pos, afi in animation_positions.items() }
		self.positions = { AnimationFrameID(*afi): tuple(pos) for pos, afi in reversed(animation_positions.items()) }

		assert (len(pos) == 2 for pos in self.positions.values())

		# zip acts like transpose; +1 because if len(x) == i, largest index should be i-1 
		xs, ys = zip(*self.positions.values())
		_size = np.array((max(xs)+1, max(ys)+1))

		# if size is given, check that no elements exceed the provided bounds
		if size is not None:
			size = np.array(size)
			if _size >= size:
				elems_out_of_range = [afi for afi, pos in self.items() if (np.array(pos) > size).any()]
				raise Exception(f"The following Animation Frames are out of the indicated size of {size}: {elems_out_of_range}")
		else:
			# otherwise, use calculated size
			size = _size
		self.size = tuple(size)
		self.frame_size = frame_size

	def __eq__(self, other):
		return (self.frame_size == other.frame_size) and (self.positions == other.positions)

	def get_animations(self):
		animations = collections.defaultdict(lambda: collections.defaultdict(int))
		afis = self.inverse_positions.values()

		for (name, direction, frame) in afis:
			animations[name][direction] = max(animations[name][direction], frame)

		print(animations)
		# return [Animation(name, direction, nframes) for nframes, direction in directions.items() for (name, directions) in animations.items()]
		anims_list = []
		for (name, directions) in animations.items():
			for direction, last_frame in directions.items():
				anims_list.append(Animation(name, direction, last_frame+1))

		return anims_list

	def get_pos(self, afi):
		return self.positions[afi]

	def get_pixel_pos(self, afi):
		pos = self.get_pos(afi)
		return (pos[0]*self.frame_size[0], 
				pos[1]*self.frame_size[1])

	@property
	def pixel_size(self):
		return (self.size[0] * self.frame_size[0],
				self.size[1] * self.frame_size[1])

	def pack_images(self, images, verbose=True):
		assert isinstance(images, collections.abc.Mapping)
		images = { AnimationFrameID(*afi): img for afi, img in images.items() }

		new_img = Image.new('RGBA',self.pixel_size, color=COLOR_TRANSPARENT)

		for pos, afi in self.inverse_positions.items():
			if afi not in images and verbose:
				print(f"Warning: missing {afi} for this layout")
			else:
				new_img.paste(images[afi], self.get_pixel_pos(afi))

		# for afi in images.keys():
		# 	if afi not in self.positions:
		# 		raise Exception(f"Do not know how to place animation '{afi}' in this layout")


		# for afi, img in images.items():
		# 	new_img.paste(img, self.get_pixel_pos(afi))

		return new_img

	def unpack_images(self, img, verbose=True):
		assert img.size == self.pixel_size, f"Image is not same size as layout; Image size: {img.size}, layout size: {self.pixel_size}"

		output = {}
		for afi, pos in self.positions.items():
			(x, y) = self.get_pixel_pos(afi)
			bbox = (x, y, x+self.frame_size[0], y+self.frame_size[0])
			sub_img = img.crop( bbox )
			output[afi] = sub_img

		return output

	def to_array(self):
		out = np.empty(shape=self.size, dtype='object')
		for afi, pos in self.positions.items():
			out[pos] = afi
		return out

	@staticmethod
	def from_array(arr):
		out = {}
		for i, row in enumerate(arr):
			for j, afi in enumerate(row):
				if afi is not None:
					# follow image convention, where (x = col, y = row)
					# out[afi] = (j, i) #(i, j)
					out[(j, i)] = afi  #(i, j)
		return AnimationLayout(out)

	@staticmethod
	def from_rows(rows):
		"""each row is a tuple (animation, direction, nframes); each row will be populated with [(animation, direction, 0), (animation, direction, 1), ... (animation, direction, nframes-1)] """
		# out_rows = [[(row[0], row[1], i) for i in range(row[2])] for row in rows]
		out_rows = []
		for row in rows:
			if (isinstance(row, tuple) and len(row) == 3) or (row is None):
				row = [row]
			
			out_row = []
			for c in row:
				if c is not None:
					assert len(c) == 3, "rows must be a list of lists of (3-length tuples) or None"

					if isinstance(c[2], collections.abc.Iterable):
						out_row.extend([ (c[0], c[1], i) for i in c[2] ])
					else:
						out_row.append(row)
				else: out_row
			out_rows.append(out_row)

		return AnimationLayout.from_array(out_rows)

	@staticmethod
	def from_animation(name, nframes, directions=['n','w','s','e']):
		return AnimationLayout.from_rows( [(name, direction, range(nframes)) for direction in directions] )

	# def from_animations(animations):
		# return AnimationLayout.from_rows( [(name, direction, range(nframes)) for direction in directions] )
		


layouts = {
	'universal': AnimationLayout.from_rows([
			('cast'   , 'n' , range(7))  ,
			('cast'   , 'w' , range(7))  ,
			('cast'   , 's' , range(7))  ,
			('cast'   , 'e' , range(7))  ,
			('thrust' , 'n' , range(8))  ,
			('thrust' , 'w' , range(8))  ,
			('thrust' , 's' , range(8))  ,
			('thrust' , 'e' , range(8))  ,
			('walk'   , 'n' , range(9))  ,
			('walk'   , 'w' , range(9))  ,
			('walk'   , 's' , range(9))  ,
			('walk'   , 'e' , range(9))  ,
			('slash'  , 'n' , range(6))  ,
			('slash'  , 'w' , range(6))  ,
			('slash'  , 's' , range(6))  ,
			('slash'  , 'e' , range(6))  ,
			('shoot'  , 'n' , range(13)) ,
			('shoot'  , 'w' , range(13)) ,
			('shoot'  , 's' , range(13)) ,
			('shoot'  , 'e' , range(13)) ,
			('hurt'   , 's' , range(6))
		]),
	'evert': AnimationLayout.from_rows([
			[('cast'   , 'n' , range(7))],
			[('cast'   , 'w' , range(7))],
			[('cast'   , 's' , range(7))],
			[('cast'   , 'e' , range(7))],

			[('thrust' , 'n' , range(8)), None, None, ('run' , 'n' , range(8))],
			[('thrust' , 'w' , range(8)), None, None, ('run' , 'w' , range(8))],
			[('thrust' , 's' , range(8)), None, None, ('run' , 's' , range(8))],
			[('thrust' , 'e' , range(8)), None, None, ('run' , 'e' , range(8))],
			[('walk'   , 'n' , range(9)), ('carry', 'n', range(9))],
			[('walk'   , 'w' , range(9)), ('carry', 'w', range(9))],
			[('walk'   , 's' , range(9)), ('carry', 's', range(9))],
			[('walk'   , 'e' , range(9)), ('carry', 'e', range(9))],
			[('slash'  , 'n' , range(6)), ('grab'  , 'n' , range(3)), ('push'  , 'n' , range(9))],
			[('slash'  , 'w' , range(6)), ('grab'  , 'w' , range(3)), ('push'  , 'w' , range(9))],
			[('slash'  , 's' , range(6)), ('grab'  , 's' , range(3)), ('push'  , 's' , range(9))],
			[('slash'  , 'e' , range(6)), ('grab'  , 'e' , range(3)), ('push'  , 'e' , range(9))],
			[('shoot'  , 'n' , range(13)), ('jump'  , 'n' , range(5))],
			[('shoot'  , 'w' , range(13)), ('jump'  , 'w' , range(5))],
			[('shoot'  , 's' , range(13)), ('jump'  , 's' , range(5))],
			[('shoot'  , 'e' , range(13)), ('jump'  , 'e' , range(5))],
			[('hurt'   , 's' , range(6))]
		]),
	'cast': AnimationLayout.from_animation('cast',7),
	'thrust': AnimationLayout.from_animation('thrust',8),
	'walk': AnimationLayout.from_animation('walk',9),
	'slash': AnimationLayout.from_animation('slash',6),
	'shoot': AnimationLayout.from_animation('shoot',13),
	'hurt': AnimationLayout.from_animation('hurt',6,['s']),
	'grab': AnimationLayout.from_animation('grab',3),
	'push': AnimationLayout.from_animation('push',9),
}


def load_layout(layout):
	if isinstance(layout, AnimationLayout):
		return layout

	if layout in layouts:
		return layouts[layout]
	else:
		raise Exception(f"Unknown layout {layout}")


IMAGE_FRAME_PATTERN = '%n-%d-%f'

def load_images(image_paths, pattern=IMAGE_FRAME_PATTERN, verbose=False):
	if not isinstance(pattern, re.Pattern):
		regex = re.compile(
			pattern_to_regex(pattern, placeholders={'f':r'\d+','d':r'\D+'})
		)
	else: 
		regex = pattern
		pattern = pattern.pattern
	if verbose: print(f"Searching pattern '{pattern}'")

	# if the pattern contains a path separator, apply the pattern to the full image path
	# otherwise, only apply the basename
	if not os.path.sep in pattern:
		image_names = (os.path.basename(f) for f in image_paths)
	else: image_names = image_paths

	# images = {AnimationFrameID.from_dict(regex.match(name).groupdict()) : Image.open(path) for name, path in zip(image_names, image_paths)}
	images = {}
	for name, path in zip(image_names, image_paths):
		m = regex.match(name)
		if m is None: 
			if verbose: print(f"- skip  {path} which does not fit pattern...")
			continue

		afi = AnimationFrameID.from_dict(m.groupdict())
		images[afi] = Image.open(path)
		if verbose:
			print(f"- FOUND {path} --> {afi}")

	return images

def pack_animations(image_paths, layout, output=None, pattern=IMAGE_FRAME_PATTERN):
	layout = load_layout(layout)

	images = load_images(image_paths, pattern)
	img = layout.pack_images(images)

	if output is not None:
		img.save(output)

	return img

def unpack_animations(image, layout, pattern='%n-%d-%f.png', output_dir='.'):
	img = Image.open(image)
	layout = load_layout(layout)

	images = layout.unpack_images(img)

	if pattern is not None:
		mkdirp(output_dir)
		for afi, img in images.items():
			img.save(output_dir + os.path.sep + afi.format(pattern))

	return images


def distribute(image_paths, offsets_image, masks_image, layout, output=None, 
	layers={
		'bg':         { 'pattern': re.compile(r'bg-(?P<d>[^\-]+)(?:-(?P<n>\D+)(?P<f>\d+)?)?.png'),                    'mask_colors':['#808080','#C0C0C0','#ffffff'] },
		'behindbody': { 'pattern': re.compile(r'behindbody-(?P<d>[^\-]+)(?:-(?P<n>\D+)(?P<f>\d+)?)?.png'),            'mask_colors':['#808080','#C0C0C0'] },
		'main':       { 'pattern': re.compile(r'(?P<d>(?!bg-)(?!behindbody-)[^\-]+)(?:-(?P<n>\D+)(?P<f>\d+)?)?.png'), 'mask_colors':['#ffffff'] },
	}, verbose=False):

	layout = load_layout(layout)

	# image_paths: (list of images) | (list of dirs) | (list of lists of images)
	# list of lists
	if all(isinstance(el, list) for el in image_paths):
		pass
	else:
		image_paths_are_dirs = [os.path.isdir(p) for p in image_paths]

		# list of directories
		if all(image_paths_are_dirs):
			image_paths = [ glob(os.path.join(d,'*.png')) for d in image_paths ]
		
		# mixture of images and directories (prohibited due to ambiguity)
		elif any(image_paths_are_dirs):
			raise NotImplementedError("image_paths must be either a list of lists, a list of directories, or a list of images; cannot mix directories and images.")
		
		# list of images
		else:
			image_paths = [ image_paths ]

	# output: str | list of str | None
	if isinstance(output, str) or output is None:
		output = [output]
	elif not isinstance(output, collections.abc.Iterable):
		raise ("output must be str, None, or list of same length as image_paths")
	if len(output) == 1:
		output = output * len(image_paths)
	elif len(output) != len(image_paths):
		raise Exception("Must give either one --output path or an equal number of --output paths to groups of images (--images).")

	animations = layout.get_animations()


	offsets_image = Image.open(offsets_image)
	masks_image = Image.open(masks_image)

	# construct animation templates for each layer; each layer needs a different 
	# template since it may use a different mask image and/or color. offsets could 
	# technically be different too
	layer_templates = {}
	for layer_name, layer_args in layers.items():

		# layer_templates[layer_name] = get_animation_templates(
		# 	animations, 
		# 	layout = layout,
		# 	**dict(
		# 		offsets_image = offsets_image,
		# 		masks_image = masks_image, 

		# 		# TODO: call Image.open on layer_args['offsets_image'], layer_args['mask_image']
		# 		**layer_args
		# 	))

		layer_templates[layer_name] = get_animation_templates(
			animations, 
			layout = layout,
			offsets_image = Image.open(layer_args['offsets_image']) if 'offsets_image' in layer_args else offsets_image,
			masks_image   = Image.open(layer_args['masks_image']) if 'masks_image' in layer_args else masks_image, 
			mask_colors   = layer_args['mask_colors'] if 'mask_colors' in layer_args else ['#ffffff']
			)


	output_imgs = []
	for image_group, group_output in zip(image_paths, output):
		if verbose: print(f"BEGIN GROUP '{image_group}'")

		img_layers = []
		for layer_name, layer_args in layers.items():
			if verbose: print(f"LAYER '{layer_name}'")

			images = load_images(image_group, layer_args['pattern'], verbose=verbose)

			# maybe there are no images for this layer; if so, save some loops
			if len(images) == 0: 
				if verbose: print('- found no images')
				continue

			animation_images = distribute_images_to_animations(animations, layer_templates[layer_name], images, verbose=verbose)
			# animation_images = { Animation(name,direction,N) : [ img1, img2, ... imgN], ... }
			# convert to dict of { AFI : img }, suitable for layout.pack_images
			images_distributed = {}
			for animation, imgs in animation_images.items():
				for afi, img in zip(animation.frames, imgs):
					images_distributed[afi] = img

			img_layers.append( layout.pack_images(images_distributed) )
			# assert False

		# import pdb;pdb.set_trace()
		img = composite_images(img_layers)

		if group_output is not None:
			mkdirpf(group_output)
			img.save(group_output)

		output_imgs.append(img)


	# img = distribute_images_via_layout(images, layout, 
	# 	offsets_image=Image.open(offsets_image), 
	# 	masks_image=Image.open(masks_image))
	# return img
	return output_imgs



# def distribute(image_paths, offsets_image, masks_image, layout, output=None, 
# 	pattern=re.compile(r'(?P<d>[^\-]+)(?:-(?P<n>\D+)(?P<f>\d+)?)?.png')
# 	):

# 	layout = load_layout(layout)

# 	# image_paths: (list of images) | (list of dirs) | (list of lists of images)
# 	# list of lists
# 	if all(isinstance(el, list) for el in image_paths):
# 		pass
# 	else:
# 		image_paths_are_dirs = [os.path.isdir(p) for p in image_paths]

# 		# list of directories
# 		if all(image_paths_are_dirs):
# 			image_paths = [ glob(os.path.join(d,'*.png')) for d in image_paths ]
		
# 		# mixture of images and directories (prohibited due to ambiguity)
# 		elif any(image_paths_are_dirs):
# 			raise NotImplementedError("image_paths must be either a list of lists, a list of directories, or a list of images; cannot mix directories and images.")
		
# 		# list of images
# 		else:
# 			image_paths = [ image_paths ]

# 	# output: str | list of str | None
# 	if isinstance(output, str) or output is None:
# 		output = [output]
# 	elif not isinstance(output, collections.abc.Iterable):
# 		raise ("output must be str, None, or list of same length as image_paths")
# 	if len(output) == 1:
# 		output = output * len(image_paths)
# 	elif len(output) != len(image_paths):
# 		raise Exception("Must give either one --output path or an equal number of --output paths to groups of images (--images).")

# 	animations = layout.get_animations()
# 	templates = get_animation_templates(animations, 
# 		offsets_image = Image.open(offsets_image), 
# 		masks_image = Image.open(masks_image), 
# 		layout = layout)

# 	output_imgs = []
# 	for image_group, group_output in zip(image_paths, output):
# 		images = load_images(image_group, pattern)

# 		# { Animation(name,direction,N) : [ img1, img2, ... imgN], ... }
# 		animation_images = distribute_images_to_animations(animations, templates, images)
# 		images_distributed = {}
# 		for animation, imgs in animation_images.items():
# 			for afi, img in zip(animation.frames, imgs):
# 				images_distributed[afi] = img

# 		# assert False
# 		img = layout.pack_images(images_distributed)

# 		if group_output is not None:
# 			mkdirpf(group_output)
# 			img.save(group_output)

# 		output_imgs.append(img)


# 	# img = distribute_images_via_layout(images, layout, 
# 	# 	offsets_image=Image.open(offsets_image), 
# 	# 	masks_image=Image.open(masks_image))
# 	# return img
# 	return output_imgs


