# numix-cursor-hidpi
A cursor theme taken from uloco/numix-cursor with modified build scripts to generate higher dpi cursors

## Requirements

- [Inkscape](https://inkscape.org/)
- [Python 3 ](https://python.org/)
- [Pillow](https://python-pillow.org/)
- [xcursorgen](https://www.x.org/releases/current/doc/man/man1/xcursorgen.1.xhtml)


## Building

Build the cursor theme by running the included python build script.
The theme is output in the `dist` directory.

```shell
git clone https://github.com/tmacro/numix-cursor-hidpi.git
cd numix-cursor-hidpi
./build.py
```


## Installation

Copy the built theme to `~/.icons/`

```shell
cp -r dist/Numix-HiDPI ~/.icons/
```

For desktop environments that read from ~/.Xresources add the following

```
Xcursor.theme: Numix-HIDPI
Xcursor.size: 16
```
