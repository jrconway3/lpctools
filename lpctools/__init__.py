import sys
import textwrap

from .utils import *


# # https://mike.depalatis.net/blog/simplifying-argparse.html
# def subcommand(args=[], parent=subparsers):
#     def decorator(func):
#         parser = parent.add_parser(func.__name__, description=func.__doc__)
#         for arg in args:
#             parser.add_argument(*arg[0], **arg[1])
#         parser.set_defaults(func=func)
#     return decorator

# def argumenwt(*name_or_flags, **kwargs):
#     return ([*name_or_flags], kwargs)


# if __name__ == "__main__":
#     args = cli.parse_args()
#     if args.subcommand is None:
#         cli.print_help()
#     else:
#         args.func(args)


# @subcommand([argument("-d", help="Debug mode", action="store_true")])
# def test(args):
#     print(args)


# @subcommand([argument("-f", "--filename", help="A thing with a filename")])
# def filename(args):
#     print(args.filename)


# @subcommand([argument("name", help="Name")])
# def name(args):
#     print(args.name)

def main(argv=None):

	def main_colors(argv, ns=None):

		parser = argparse.ArgumentParser(description='Utilities for recoloring images', prog='lpctools colors')
		subparsers = parser.add_subparsers(dest='command', title='subcommands', required=True, 
			description='Use %(prog)s SUBCOMMAND --help for more detailed help.')

		parser.add_argument('--verbose', '-v', action='count', dest='verbose', default=0)

		# RECOLORING SUBCOMMANDS
		# ----------------------


		mapping_help = dedent("""\
			A "color mapping" is a mapping between one "source" palette and one or more
			"target" palettes. Each color in the "source" palette should correspond to one 
			color in each "target" palette. 

			Working with mappings may be more convenient than palettes when you have one set
			of images that needs to be recolored into many palettes.  

			Mappings can be written as JSON files or as RGBA PNG images:
			- As an image, each palette (including the source palette) is one row of pixels;
			  the source palette is the first row of pixels
			- As a JSON file, each palette is under a separate key, as an array of RGB(A) hex 
			  colors. The source palette is in a key called "source".

			  Example:

			  { "source": ["#000000", "#cccccc", "#ffffff"],
			    "reds":   ["#000000", "#cc0000", "#ff0000"],
			    "blues":  ["#000000", "#0000cc", "#0000ff"] }

			  This mapping encodes three palettes: "source", "reds", and "blues". For an image
			  recolored from "source" to "blues", '#ffffff' (white) would become '#0000ff' 
			  (blue), '#cccccc' (gray) would become '#0000cc' (dark blue), and '#000000' 
			  would be unchanged.
			""")
		palette_help = dedent("""\
			Supported palette formats: 
			- PNG image (unique colors will be identified from left-to-right, top-to-bottom, 
			- GIMP palette format (.gpl)
			- JSON: should contain a single array of RGB(A) hexadecimal color strings
			""")

		pattern_help = dedent("""\
			By default, the engine will create one folder for each INPUT image, and within
			that folder, will write one image named PALETTE.png for each target palette:

			Example:
			$ %(prog)s recolor --input IMAGE1.png IMAGE2.png --from SOURCE --to PALETTE.png PALETTE2.png
				IMAGE1/
				  PALETTE1.png
				  PALETTE2.png
				  ...
				IMAGE2/
				  PALETTE1.png
				  ...

			However, you can change this arrangement by specifying an --output PATTERN.
			Use these placeholder symbols:

			- %%i : path to the input image file, without file extension
			- %%p : name of the palette
			- %%e : file extension of the input image
			- %%I : full path to the image, including file extension (='%%i.%%e')
			- %%b : basename of the input image, without extension
			- %%B : basename of the input image, including extension (='%%b.%%e')
			- %%%% : literal %% sign

			Example: write input images like INPUT-PALETTE.png:
			--output %%i-%%p.%%e
			""")


		# colors RECOLOR subcommand
		# ------------------
		parser_recolor = subparsers.add_parser('recolor', help='Recolor an image',
			formatter_class=argparse.RawTextHelpFormatter,

			epilog=dedent(f"""\
				Recolor an image to one or more palettes. 

				Either specify individual palettes with --from and --to , or give several palettes 
				at once with --mapping .

				PALETTES
				{palette_help}


				MAPPINGS
				{mapping_help}


				FILE NAMING
				{pattern_help}


				MULTIPLE MAPPINGS
				Multiple mappings can be given, either by multiple --mapping flags, or by multiple
				--from/--to flags. You can control the behavior in this case with --combine:

				--combine sum (default): each mapping is applied separately to each input image. 
				This is equivalent to running the command multiple times, once with each mapping. 

				--combine product: generate all combinations of palettes from the given mappings. 
				That is, apply the first mapping to generate a set of N recolored images, 
				then apply the second mapping to EACH of those N images, generating N * M recolored 
				images, then apply the third mapping (if given) to EACH of those N * M images to 
				generate N * M * K images, and so on. 

				--combine product is useful if the mappings specify different materials, for 
				instance if MAPPING1 gives colors of fabric and MAPPING2 gives colors of metal 
				buttons. 
				""")
			)
		parser_recolor.add_argument('--input', dest='input', action='extend', nargs='+',
							help='input filename(s)', required=True)

		parser_recolor.add_argument('--output', dest='output', action='store', nargs='+', #action=ExtendActionOverwriteDefault, nargs='+',
							default=['%i/%p.%e'],
							help='How should output files be named? (default: %(default)s)')
		# parser_recolor.add_argument('--output-dir', dest='output_dir')
		parser_recolor.add_argument('--from', dest='source', action='append', default=[], nargs='+', help="source palette(s)")
		parser_recolor.add_argument('--to',  dest='target', action='append', default=[], nargs='+', help="destination palette(s)")

		parser_recolor.add_argument('--mapping', dest='mapping', default=[], action='append', help="color mapping(s); create mapping from palettes with create-mapping")
		parser_recolor.add_argument('--palette-names', dest='palettes', default=[], action='append', nargs='+', 
			help=dedent("""\
			specify or override the names for palettes given in MAPPING. If 
			"MAPPING is an image, you must specify palette names here, or 
			recolored images will be named 1.png, 2.png, etc."""))

		parser_recolor.add_argument('--combine', dest='mode', choices=['sum','product'], default='sum', help='how to combine multiple mappings, if specified')
		parser_recolor.add_argument('--output-mapping-image', dest='mapping_output', help="Write an image representation of the palette mapping to this path, if given")

		# convertpalette subcommand
		parser_palette = subparsers.add_parser('convert-palette', help='Convert a color palette between formats',
			description='Convert a color palette between formats',
			formatter_class=argparse.RawTextHelpFormatter,
			epilog=dedent(f"""\
				{palette_help}
				""")
			)
		parser_palette.add_argument('--input', help='input color palette; format will be inferred from file extension')
		parser_palette.add_argument('--output', help='output color palette; format will be inferred from file extension')
		parser_palette.add_argument('--sort', help='sorts the palette by alpha, then luminosity', action='store_const', const='auto')

		# convertmapping subcommand
		parser_convertmapping = subparsers.add_parser('convert-mapping', 
			help='Convert a color mapping between formats',
			description='Convert a color mapping (created with `lpctools colors create-mapping`) between formats.')	
		parser_convertmapping.add_argument('--input', help='input color mapping; format will be inferred from file extension')
		parser_convertmapping.add_argument('--output', help='output color mapping; format will be inferred from file extension')
		parser_convertmapping.add_argument('--palette-names', dest='names', default=[], action='extend', nargs='+', 
			help=dedent("""\
			specify or override the names for palettes given in INPUT. If 
			"INPUT is an image, you must specify palette names here, or 
			recolored images will be named 1.png, 2.png, etc."""))
		parser_convertmapping.add_argument('--sort', help='sorts the mapping by alpha, then luminosity of the source palette', action='store_const', const='auto')

		# createmapping subcommand
		parser_mapping = subparsers.add_parser('create-mapping', help='Construct a color mapping from palette(s)',
			formatter_class=argparse.RawTextHelpFormatter,
			description=dedent(f"""\
				Create a color mapping from two or more palettes.

				{mapping_help}
				""")
			)	
		# parser_mapping.add_argument('--source')
		# parser_mapping.add_argument('--target', action='extend', nargs='+')
		parser_mapping.add_argument('--from', dest='source', help="path to source palette")
		parser_mapping.add_argument('--to',  dest='target',  action='extend', nargs='+', 
			help="path(s) to target palette(s); target palettes can be named by writing NAME=PATH")
		parser_mapping.add_argument('--output', help='Filename to save the output mapping; format will be inferred from extension')


		# parser_concat_mappings = subparsers.add_parser('concat-mappings', help='Concatenates one or more mappings',
		# 	formatter_class=argparse.RawTextHelpFormatter
		# 	)	
		# parser_concat_mappings.add_argument('--mapping', dest='mapping', help="path to source mapping(s)")
		# parser_concat_mappings.add_argument('--from', dest='source', help="path to new source palette")
		# parser_concat_mappings.add_argument('--to',  dest='target',  action='extend', nargs='+', 
		# 	help="path(s) to additional target palette(s); target palettes can be named by writing NAME=PATH")
		# parser_concat_mappings.add_argument('--output', help='Filename to save the output mapping; format will be inferred from extension')
		# parser_concat_mappings.add_argument('--sort', help='sorts the mapping by alpha, then luminosity of the source palette', action='store_const', const='auto')
		# parser_concat_mappings.add_argument('--filter', action='extend', nargs='+', help='filter the mapping to only include the listed palettes')
		# parser_concat_mappings.add_argument('--drop', action='extend', nargs='+', help='filter the mapping to NOT include the listed palettes')


		args = parser.parse_args(argv, ns)

		from .recolor import main_recolor, main_convertpalette, main_convertmapping, main_create_mapping, main_concat_mappings
		sub_commands = {
			'recolor': main_recolor,
			'convert-palette': main_convertpalette,
			'convert-mapping': main_convertmapping,
			'create-mapping': main_create_mapping
			# ,'concat-mappings': main_concat_mappings
		}

		sub_commands[args.command](args)


	def main_arrange(argv, ns=None):
		
		from .arrange import layouts, distribute_layers, IMAGE_FRAME_PATTERN, main_pack, main_unpack, main_repack, main_distribute

		parser = argparse.ArgumentParser(description='Utilities for arranging and combining images', prog='lpctools arrange')
		subparsers = parser.add_subparsers(dest='command', title='subcommands', required=True, 
			description='Use %(prog)s SUBCOMMAND --help for more detailed help.')

		parser.add_argument('--verbose', '-v', action='count', dest='verbose', default=0, help='Print diagnostic messages. Repeat for higher verbosity.')

		pattern_help = dedent("""\
			Patterns are specified using these characters: 
			- %n = name of the animation (e.g. cast, thrust, shoot)'
			- %d = direction of the animation (e.g. n = north, s = south, etc.)
			- %f = the frame number
			""")

		layouts_help = ("Available layouts:\n" +
			"\n".join(f"- {layout_name}" for layout_name in layouts))



		parser_pack = subparsers.add_parser('pack', 
			help='Packs images, one per animation frame, into a spritesheet',
			formatter_class=argparse.RawTextHelpFormatter,
			epilog=dedent(f"""\
			{pattern_help}

			{layouts_help}
			""")
			)
		parser_pack.add_argument('--input', action='extend',nargs='+', required=True, help='Images to pack, one per frame')
		parser_pack.add_argument('--output', required=True, help='Packed image')
		parser_pack.add_argument('--layout', default='universal', help='Name of the layout')
		parser_pack.add_argument('--pattern',default=IMAGE_FRAME_PATTERN, 
				help="How are images named? See details below (default: '%(default)s)'")


		parser_unpack = subparsers.add_parser('unpack', help='Unpacks a spritesheet into images, one for each animation frame',
			formatter_class=argparse.RawTextHelpFormatter,
			epilog=dedent(f"""\
			{pattern_help}

			Patterns can contain subdirectories, which will be created, e.g. %n/%d-%f.png
			will create `thrust/n-1.png`, `thrust/n-2.png`, etc.

			If --output-dir is given as well, images and subdirectories will be created within.
			OUTPUT_DIR will be created


			{layouts_help}
			""")
			)
		parser_unpack.add_argument('--input',required=True, help='Packed image')
		parser_unpack.add_argument('--pattern',default=IMAGE_FRAME_PATTERN, 
			help="How should frame images be named? See details below (default: '%(default)s)'")
		parser_unpack.add_argument('--output-dir',dest='output_dir', default='.', 
			help='Directory where the frame images should be placed')
		parser_unpack.add_argument('--layout', default='universal')


		parser_repack = subparsers.add_parser('repack', help='Re-packs animation frames from one spritesheet layout to other(s)',
			formatter_class=argparse.RawTextHelpFormatter,
			epilog=dedent(f"""\
			If multiple input images are provided, then multiple FROM layouts must be provided, one per image. All frames will be merged 
			together and used to pack the resulting TO layout(s). If the same frame appears in multiple images, the last occurrance will
			be used. 

			Will create one image per TO layout.

			{layouts_help}
			""")
			)

		parser_repack.add_argument('--input',required=True, help='Packed image', action='extend', nargs='+')
		parser_repack.add_argument('--from', dest='from_layouts', default=['universal'], help='Layout(s) of the original spritesheet images', nargs='+')
		parser_repack.add_argument('--to', dest='to_layouts', default=['cast','thrust','walk','slash','shoot','hurt'], nargs='+', help='New layout(s) to create')
		parser_repack.add_argument('--output-dir',dest='output_dir', default='.', 
			help='Directory where the repacked spritesheet(s) should be placed (default: %(default)s)')

		layers_help = '\n'.join(wrap_fill(f"- {layer_name} : {layer['help']}", width=79) for layer_name, layer in distribute_layers.items() )

		mask_colors_help = '\n'.join(
			f"- {', '.join(c for c in layer['mask_colors'])}-colored pixels in the mask image will be removed from the {layer_name} layer" for layer_name, layer in distribute_layers.items())

		parser_distribute = subparsers.add_parser('distribute', 
			help='Distributes images across many animations',
			description=wrap_fill(
				'Takes a small set of objects and distributes them across all animation '
				'frames in a layout. Useful for objects that are similar for many '
				'animation frames (e.g. hair, hats, shields). Can optionally offset '
				'and/or create cutout masks for certain frames.'),
			formatter_class=argparse.RawTextHelpFormatter,
			epilog=dedent(f"""\
			ALGORITHM
			- INPUT images are collected as below
			- for each group of INPUT images
			  - INPUT image names are used to determine which animation frame(s) and layer
			    each image belongs to
			  - for each layer:
			    - INPUT images are arranged according to the OFFSET image
			    - the MASK image is used to cutout certain pixels from each frame
			    - animation frames are packed into a LAYOUT
			  - layer images are composited together
			  - the assembled image is written to the corresponding OUTPUT file

			INPUT IMAGES
			Each --input flag defines an INPUT image group. All images in the group
			will be used to make one OUTPUT image. 

			1) --input IMAGE1 IMAGE2 ... --output OUTPUT
				Will load all provided images and use to create one OUTPUT image
			2) --input DIRECTORY1 --output OUTPUT1 --input DIRECTORY2 --output OUTPUT2
				Will load all images in DIRECTORY1 and use to create OUTPUT1,
				then load all images in DIRECTORY2 and use to create OUTPUT2, etc.
			3) --input IMAGE_A1 IMAGE_A2 ... --output OUTPUT_A --input IMAGE_B1 IMAGE_B2 --output OUTPUT_B
				Will load IMAGE_A1, IMAGE_A2, etc. and use to create OUTPUT_A
				then load IMAGE_B1, IMAGE_B2, etc. and use to create OUTPUT_B.

			The number of --input flags should be the same as the number of --output flags. 
			INPUT image groups correspond to OUTPUT images by order.


			IMAGE NAMING
			The parser uses image names to determine for which frame(s) and in which 
			layer(s) the image should be used. Images should be named: 

			`[PREFIX-]D[-FRAMES].png`, where:

			* `D` is the direction the character is facing: `n`, `s`, `e`, or `w`.
			* `PREFIX-` is an optional layer name. If specified, this is either `bg-` or `behindbody-`.
			* `-FRAMES` is optional; if given, it is a dash-separated list specifying 
			  one or more animations or animation frames for which the image should be used. 

			Examples:
			- n.png will be used for all north-facing frames
			- s-shoot.png will be used for all south-facing frames in the `shoot` animation
			- s-shoot-hurt1.png will be used for all south-facing frames in the `shoot` 
			  animation, and for frame 1 of the south-facing `hurt` animation. 

			More specific images will take precedence over less specific ones (e.g. 
			s-shoot1.png > s-shoot.png > s.png)
			

			LAYERS
			The engine generates three layers:

			{layers_help}

			Each of these layers is masked (see below), then the three layers are 
			composited together in order. These cannot be modified from the command line 
			interface, but can be modified using the Python API.  


			OFFSETS
			An OFFSETS image can be provided, which should have the same LAYOUT as the 
			OUTPUT image(s). For each frame in the OFFSETS image, the input frame image 
			will be placed such that the middle pixel lines up with the first (top-most
			and left-most) black pixel in the OFFSETS frame. Only one OFFSETS image can 
			be given. 


			MASKS
			A MASK image can be provided, which should have the same LAYOUT as the OUTPUT 
			image(s). The MASK image is used to remove or cutout certain pixels from each 
			layer of input image(s). Only one MASK image can be given---the colors 
			determine which pixels are masked in each layer: 

			{mask_colors_help}

			LAYOUTS
			{layouts_help}
			""")
			)
		parser_distribute.add_argument('--input', required=True, action='append', nargs='+', 
			help='Input image(s) or directories')
		parser_distribute.add_argument('--output', required=True, action='extend', nargs='+',
			help='Path where the complete spritesheet(s) should be placed')
		parser_distribute.add_argument('--layout', default='universal')
		parser_distribute.add_argument('--offsets', '--offset', required=True, 
			help='Path to image specifying the x/y coordinate for each frame')
		parser_distribute.add_argument('--masks', '--mask', required=True, 
			help='Path to image specifying the cutouts/masks for each layer')


		args = parser.parse_args(argv, ns)		
		sub_commands = {
			'unpack':main_unpack,
			'repack':main_repack,
			'pack':main_pack,
			'distribute':main_distribute
		}

		sub_commands[args.command](args)


	import argparse

	commands = {
		'colors': main_colors,
		'arrange': main_arrange
	}

	parser = argparse.ArgumentParser(description='Utilities for manipulating pixel art', 
		add_help=False, 
		epilog='Use %(prog)s SUBCOMMAND -h for more detailed help.'
		# ,exit_on_error=False
		)
	parser.add_argument('-h','--help', action='store_const', const=True)
	parser.add_argument('--pdb', action='store_const',const=True)
	parser.add_argument('command', choices = list(commands.keys()) + ['help'], nargs='?', default='help', help='Subcommand to execute')

	# try:
		# ns, argv_rest = parser.parse_known_args(argv)
	# except argparse.ArgumentError as err:
		# parser.print_help()

	ns, argv_rest = parser.parse_known_args(argv)

	if ns.pdb:
		import pdb; pdb.set_trace()

	if ns.command == 'help':
		parser.print_help()
		sys.exit(1)
	if ns.command != 'help' and ns.help:
		argv_rest.append('--help')

	commands[ns.command](argv_rest, ns)
