#!/usr/bin/env python

from pathlib import PosixPath
from collections import OrderedDict, defaultdict
from tempfile import NamedTemporaryFile
from os import makedirs, system
import subprocess
from threading import Thread, Semaphore, Event
from queue import Queue
from time import sleep
import shlex
from PIL import Image, ImageDraw
import sys
from shutil import copyfile

RED = '\033[31m'
GREEN = '\033[32m'
BLUE = '\033[34m'
YELLOW = '\033[33m'
OFF = '\033[0m'

DIST_DIR = PosixPath('dist/Numix-HIDPI')
CURSOR_DIST = DIST_DIR.joinpath('cursors/')

BUILD_DIR = PosixPath('build/')
CURSOR_OUTPUT = BUILD_DIR.joinpath('cursor/')
ICON_OUTPUT = BUILD_DIR.joinpath('icons/')

CMD_TMPL = 'inkscape %s -o %s --export-dpi %s'

DPI = OrderedDict([
	(90,  24),
	(120, 30),
	(160, 40),
	(180, 45),
	(200, 50),
	(220, 55),
	(240, 60),
	(320, 80)
])



class WatchedProcess(Thread):
	"""
		A light wrapper around a Popen object

		all args are passed through to the Popen constructor

		2 additional keyword arguments are added
			on_exit
			on_error
		These should contain a callable object taking 1 arguement return_code
		on_exit will always be called when the process exits
		on_error will be called when the process exits with return_code != 0
	"""

	def __init__(self, *args, on_exit = None, on_error = None, **kwargs):
		super().__init__()
		self.daemon = True
		self._proc = None
		self._started = Event()
		self._args = args
		self._kwargs = kwargs
		self._on_exit = on_exit
		self._on_error = on_error
		self._proc = subprocess.Popen(*self._args, **self._kwargs)

	def __call__(self):
		"""for convenience return the popen object when called"""
		return self._proc

	def run(self):
		self._started.set()
		self._proc.wait()
		rc = self._proc.returncode
		if self._on_exit:
			self._on_exit(rc)
		if self._on_error and rc != 0:
			self._on_error(rc)

	def terminate(self):
		return self._proc.terminate()

	def kill(self):
		return self._proc.kill()

	@property
	def status(self):
		if self._proc:
			return self._proc.poll()

	def wait(self):
		self._started.wait()
		return self._proc.wait() if self._proc else None


def WatchProcess(*args, start = True, wait = False, **kwargs):
	wp = WatchedProcess(*args, **kwargs)
	if start:
		wp.start()
	if wait:
		return wp.wait()
	return wp


makedirs(DIST_DIR, exist_ok=True)
makedirs(CURSOR_DIST, exist_ok=True)
makedirs(BUILD_DIR, exist_ok=True)
makedirs(CURSOR_OUTPUT, exist_ok=True)
makedirs(ICON_OUTPUT, exist_ok=True)


def err(msg, **kwargs):
	print('%s%s%s'%(RED, msg, OFF), **kwargs)

def info(msg, **kwargs):
	print('%s:: :: %s%s%s'%(YELLOW, GREEN, msg, OFF), **kwargs)

def warn(msg, **kwargs):
	print('%s%s%s'%(YELLOW, msg, OFF), **kwargs)

def info_sub(msg, **kwargs):
	print('%s%s%s'%(BLUE, msg, OFF), **kwargs)


info('Discovering cursors... ', end = '')
cursors = [c for c in PosixPath('src/cursor/').glob('*.cursor')]
info_sub('Discovered %s icons'%len(cursors))

info('Discovering svgs... ', end = '')
svgs = {s.stem: s for s in PosixPath('src/svg/').glob('*.svg')}
info_sub('Discovered %s svgs'%len(svgs))

info('Discovering theme files... ', end = '')
theme = [p for p in PosixPath('src/theme').glob('*.theme')]

def load_cursor(path):
	icons = []
	with open(path) as f:
		for line in f:
			parts = line.split()
			if len(parts) == 4:
				size, hot_x, hot_y, name = parts
				delay = 0
			else:
				size, hot_x, hot_y, name, delay = parts
			icons.append((int(size), int(hot_x), int(hot_y), name, int(delay)))
	return icons

info('Loading cursors... ', end = '')
mapped_cursors = defaultdict(list)
for cur in cursors:
	icons = load_cursor(cur.resolve())
	mapped_cursors[cur] = icons
info_sub('Done')

def scale_hotpoints(orig_size, new_size, hot_x, hot_y):
	scale = new_size / orig_size
	return round(hot_x * scale), round(hot_y * scale)

info('Building cursor list... ', end = '')
master_cursor_list = defaultdict(list)
for cursor, icons in mapped_cursors.items():
	cursor_file_path = CURSOR_OUTPUT.joinpath(cursor.name)
	for dpi, scaled_size in DPI.items():
		for size, hot_x, hot_y, name, delay in icons:
			input_icon_path = svgs.get(name)
			if not input_icon_path:
				raise Exception('Unable to match %s to a discovered svg'%icon)
			sized_icon_output_path = ICON_OUTPUT.joinpath('%s_%s.png'%(name, dpi))
			scaled_x, scaled_y = scale_hotpoints(size, scaled_size, hot_x, hot_y)
			master_cursor_list[cursor_file_path].append((dpi, scaled_size,
														scaled_x, scaled_y,
														input_icon_path,
														sized_icon_output_path,
														delay))
info_sub('Done')

def build_cursor_line(args):
	line = '%s %s %s %s'%(*args[1:4], args[5])
	if args[6]:
		line = '%s %s'%(line, args[6])
	return line

info('Writing cursor files... ', end = '')
for cursor, icons in master_cursor_list.items():
	with open(cursor.resolve(), 'w') as cursor_file:
		lines = [build_cursor_line(icon) for icon in icons]
		cursor_file.write('\n'.join(lines))
info_sub('Done')

info('Building master conversion list...')
tasks = Queue()
for cursor, icons in master_cursor_list.items():
	for dpi, _, _, _,  input_path, output_path, _ in icons:
		if not output_path.exists():
			tasks.put((input_path, output_path, dpi))
		else:
			info_sub(':: :: Skipping %s, already exists'%output_path)
info('Done')

def converter(queue, sem):
	task = None
	sem.acquire()
	sleep(1)
	while True:
		try:
			task = queue.get(timeout = 5)
			args = shlex.split(CMD_TMPL%task)
			rc = WatchProcess(args, wait = True, stdout = subprocess.DEVNULL)
			if rc:
				raise Exception('Error converting svg')
				err('!! !! Error converting svg %s -> %s at %s'%task)
		except Exception as e:
			break
		info_sub(':: :: %s dpi %s -> %s'%(task[2], *task[:2]))
	sem.release()

if not tasks.empty():
	info('Converting svgs to pngs... ', end = '')
	info_sub('Preparing... ', end = '')
	sem = Semaphore(8)
	workers = [Thread(target=converter, args=(tasks, sem)) for x in range(8)]
	info_sub('Starting... ', end = '')
	for worker in workers:
		worker.start()
	info_sub('Started')
	sleep(1)
	x = 8
	while x > 0:
		sem.acquire()
		x -= 1
	info('Done converting svgs')
else:
	info('No svgs to covert, skipping.')

info('Building cursor theme... ', end = '')

built_cursors = dict()
for cursor in master_cursor_list.keys():
	output = CURSOR_DIST.joinpath(cursor.stem)
	cmd = 'xcursorgen %s %s'%(cursor.resolve().as_posix(), output.resolve().as_posix())
	if not WatchProcess(shlex.split(cmd), wait = True) == 0:
		err('Error building %s'%cursor.stem)
	else:
		built_cursors[cursor.stem] = output
info_sub('Done')

info('Loading aliases... ', end = '')
cursor_aliases = defaultdict(list)
with open('src/aliases') as f:
	for line in f:
		cursor, alias = line.split()
		cursor_aliases[cursor].append(alias)
info_sub('Done')

info('Building symbolic links...')
for cursor, aliases in cursor_aliases.items():
	if cursor not in built_cursors:
		err('Could not find cursor %s for alias %s'%(cursor, alias))
		continue
	for alias in aliases:
		link = CURSOR_DIST.joinpath(alias).symlink_to(built_cursors[cursor].stem)
info('Done')

info('Copying index... ', end = '')
for p in theme:
	copyfile(p.resolve().as_posix(), DIST_DIR.joinpath(p.name).resolve().as_posix())
info_sub('Done')
