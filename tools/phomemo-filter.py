#! /usr/bin/python3

"""Send the picture to a printer."""

import argparse
import os
import sys

from PIL import Image

# Printer model configurations
PRINTER_MODELS = {
    "m02": {
        "width_dots": 384,
        "bytes_per_line": 48,
        "max_block_lines": 255,
        "protocol": "m02",
    },
    "t02": {
        "width_dots": 384,
        "bytes_per_line": 48,
        "max_block_lines": 255,
        "protocol": "m02",
    },
    "m110": {
        "width_dots": 344,
        "bytes_per_line": 43,
        "max_block_lines": None,
        "protocol": "m110",
    },
    "m120": {
        "width_dots": 344,
        "bytes_per_line": 43,
        "max_block_lines": None,
        "protocol": "m110",
    },
    "m220": {
        "width_dots": 560,
        "bytes_per_line": 70,
        "max_block_lines": None,
        "protocol": "m110",
    },
    "m421": {
        "width_dots": 576,
        "bytes_per_line": 72,
        "max_block_lines": None,
        "protocol": "m110",
    },
}

# Media type mapping for M110 protocol
MEDIA_TYPES = {
    "gaps": 10,       # 0x0a - Label With Gaps (default)
    "continuous": 11, # 0x0b - Continuous
    "marks": 38,      # 0x26 - Label With Marks
}


# =============================================================================
# M02 Protocol Functions
# =============================================================================

def print_header_m02():
    """Print M02 header: initialize printer, center justification, media init."""
    with os.fdopen(sys.stdout.fileno(), "wb", closefd=False) as stdout:
        stdout.write(b'\x1b\x40')           # ESC @: initialize printer
        stdout.write(b'\x1b\x61\x01')       # ESC a: select justification (centered)
        stdout.write(b'\x1f\x11\x02\x04')   # Media type/mode initialization


def print_marker_m02(lines=0x100):
    """Print M02 block marker for raster image data."""
    with os.fdopen(sys.stdout.fileno(), "wb", closefd=False) as stdout:
        stdout.write(b'\x1d\x76\x30')       # GS v 0: print raster bit image
        stdout.write(b'\x00')               # mode: normal
        stdout.write((48).to_bytes(2, 'little'))  # bytes per line
        stdout.write((lines).to_bytes(2, 'little'))  # number of lines


def print_footer_m02():
    """Print M02 footer: feed lines and finalize."""
    with os.fdopen(sys.stdout.fileno(), "wb", closefd=False) as stdout:
        stdout.write(b'\x1b\x64\x02')       # ESC d: print and feed 2 lines
        stdout.write(b'\x1b\x64\x02')       # ESC d: print and feed 2 lines
        stdout.write(b'\x1f\x11\x08')
        stdout.write(b'\x1f\x11\x0e')
        stdout.write(b'\x1f\x11\x07')
        stdout.write(b'\x1f\x11\x09')


def print_line_m02(image, line):
    """Print a single line of image data for M02 (with 0x0a workaround)."""
    with os.fdopen(sys.stdout.fileno(), "wb", closefd=False) as stdout:
        for x in range(int(image.width / 8)):
            byte = 0
            for bit in range(8):
                if image.getpixel((x * 8 + bit, line)) == 0:
                    byte |= 1 << (7 - bit)
            # 0x0a breaks the rendering
            # 0x0a alone is processed like LineFeed by the printer
            if byte == 0x0a:
                byte = 0x14
            stdout.write(byte.to_bytes(1, 'little'))


def print_image_m02(image):
    """Print image using M02 protocol with 255-line block chunking."""
    remaining = image.height
    line = 0
    print_header_m02()
    while remaining > 0:
        lines = min(remaining, 256)
        print_marker_m02(lines)
        remaining -= lines
        for _ in range(lines):
            print_line_m02(image, line)
            line += 1
    print_footer_m02()


# =============================================================================
# M110 Protocol Functions (also used by M120, M220, M421)
# =============================================================================

def print_header_m110(speed=5, density=10, media_type=10):
    """Print M110 header: speed, density, and media type settings."""
    with os.fdopen(sys.stdout.fileno(), "wb", closefd=False) as stdout:
        # Print Speed: ESC N 0x0d <speed>
        stdout.write(b'\x1b\x4e\x0d')
        stdout.write(speed.to_bytes(1, 'little'))
        # Print Density: ESC N 0x04 <density>
        stdout.write(b'\x1b\x4e\x04')
        stdout.write(density.to_bytes(1, 'little'))
        # Media Type: 0x1f 0x11 <type>
        stdout.write(b'\x1f\x11')
        stdout.write(media_type.to_bytes(1, 'little'))


def print_marker_m110(bytes_per_line, lines):
    """Print M110 block marker for raster image data."""
    with os.fdopen(sys.stdout.fileno(), "wb", closefd=False) as stdout:
        stdout.write(b'\x1d\x76\x30')       # GS v 0: print raster bit image
        stdout.write(b'\x00')               # mode: normal
        stdout.write(bytes_per_line.to_bytes(2, 'little'))
        stdout.write(lines.to_bytes(2, 'little'))


def print_footer_m110():
    """Print M110 footer."""
    with os.fdopen(sys.stdout.fileno(), "wb", closefd=False) as stdout:
        stdout.write(b'\x1f\xf0\x05\x00')
        stdout.write(b'\x1f\xf0\x03\x00')


def print_image_m110(image, bytes_per_line, speed=5, density=10, media_type=10):
    """Print image using M110 protocol (single block, no chunking)."""
    print_header_m110(speed, density, media_type)
    print_marker_m110(bytes_per_line, image.height)
    with os.fdopen(sys.stdout.fileno(), "wb", closefd=False) as stdout:
        stdout.write(image.tobytes())
    print_footer_m110()


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s image.png > /dev/rfcomm0              # M02 via Bluetooth
  %(prog)s -m m110 image.png > /dev/usb/lp0      # M110 via USB
  %(prog)s -m m110 --speed 3 --density 12 image.png > /dev/rfcomm0
  %(prog)s -m m110 --media-type continuous image.png > /dev/usb/lp0
"""
    )
    parser.add_argument("file", help="Image file to print")
    parser.add_argument("--model", "-m",
                        choices=list(PRINTER_MODELS.keys()),
                        default="m02",
                        help="Printer model (default: m02)")
    parser.add_argument("--no-rotate", action="store_true",
                        help="Disable auto-rotation of the image")

    # M110-specific options
    parser.add_argument("--speed", "-s", type=int, default=5,
                        choices=range(1, 6), metavar="1-5",
                        help="Print speed, 1=slow 5=fast (M110 only, default: 5)")
    parser.add_argument("--density", "-d", type=int, default=10,
                        choices=range(1, 16), metavar="1-15",
                        help="Print density (M110 only, default: 10)")
    parser.add_argument("--media-type", "-t",
                        choices=list(MEDIA_TYPES.keys()),
                        default="gaps",
                        help="Media type (M110 only, default: gaps)")

    args = parser.parse_args()

    # Load image
    try:
        image = Image.open(args.file)
    except Exception as e:
        print(f"Cannot open file {args.file}: {e}", file=sys.stderr)
        parser.print_usage(sys.stderr)
        sys.exit(2)

    # Get model configuration
    model_config = PRINTER_MODELS[args.model]
    width_dots = model_config["width_dots"]

    # Auto-rotate landscape images to portrait
    if not args.no_rotate:
        if image.width > image.height:
            image = image.transpose(Image.ROTATE_90)

    # Resize to printer width
    image = image.resize(size=(width_dots, int(image.height * width_dots / image.width)))

    # Convert to black & white with dithering
    image = image.convert(mode='1')

    # Print using the appropriate protocol
    if model_config["protocol"] == "m02":
        print_image_m02(image)
    else:
        media_type = MEDIA_TYPES[args.media_type]
        print_image_m110(
            image,
            bytes_per_line=model_config["bytes_per_line"],
            speed=args.speed,
            density=args.density,
            media_type=media_type
        )


if __name__ == "__main__":
    main()
